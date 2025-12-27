"""
PEIT Modal Backend
==================
Modal.com serverless backend for PEIT Map Creator.
Provides REST API endpoints for geospatial processing with SSE progress streaming.

Endpoints:
    POST /api/process - Upload file and stream processing progress
    GET /api/download/{job_id} - Download result ZIP file
    GET /api/health - Health check

Usage:
    Development: modal serve modal_app.py
    Production: modal deploy modal_app.py
"""

import modal
from modal.exception import FunctionTimeoutError
import os

# Create Modal app
app = modal.App("peit-processor")

# Vercel Blob secret for uploading maps
vercel_blob_secret = modal.Secret.from_name("vercel-blob", required_keys=["BLOB_READ_WRITE_TOKEN"])

# Supabase secret for job tracking (optional - jobs work without it)
supabase_secret = modal.Secret.from_name("supabase-service", required_keys=["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"])

# Modal Dict for rate limiting (anonymous users - IP-based)
rate_limit_dict = modal.Dict.from_name("peit-rate-limits", create_if_missing=True)
MAX_RUNS_PER_DAY_ANONYMOUS = 2  # Anonymous users (IP-based)

# Modal Dict for authenticated user rate limiting (user_id-based)
user_rate_limit_dict = modal.Dict.from_name("peit-user-rate-limits", create_if_missing=True)
MAX_RUNS_PER_DAY_AUTHENTICATED = 20  # Authenticated users

# Modal Dict for tracking active jobs per IP
active_jobs_dict = modal.Dict.from_name("peit-active-jobs", create_if_missing=True)
MAX_CONCURRENT_JOBS_PER_IP = 3

# Modal Dict for global rate limit (across all users)
global_rate_limit_dict = modal.Dict.from_name("peit-global-rate-limit", create_if_missing=True)
MAX_GLOBAL_RUNS_PER_DAY = 50

# Maximum input geometry area in square miles
MAX_INPUT_AREA_SQ_MILES = 500

# Modal Volume for storing results temporarily
results_volume = modal.Volume.from_name("peit-results", create_if_missing=True)

# Define the container image with geospatial dependencies
peit_image = (
    modal.Image.micromamba()
    .apt_install("ca-certificates")  # System SSL certificates
    .micromamba_install(
        "gdal>=3.8",
        "geos>=3.12",
        "proj>=9.3",
        "fiona>=1.9",
        "pyproj>=3.6",
        "shapely>=2.0",
        "geopandas>=0.14",
        "ca-certificates",  # Conda SSL certificates
        channels=["conda-forge"]
    )
    .pip_install(
        "folium>=0.15.0",
        "requests>=2.31.0",
        "matplotlib>=3.8.0",
        "branca>=0.7.0",
        "jinja2>=3.1.0",
        "fpdf2>=2.8.0",
        "openpyxl>=3.1.0",
        "fastapi[standard]",
        "vercel>=0.3.5",
        "supabase>=2.10.0",
        "certifi",  # Python SSL certificates for httpx
        "httpx>=0.27.0",  # Async HTTP client for geocoding proxy
    )
    .run_commands("update-ca-certificates || true")  # Update system CA store
    # Add local directories to the container
    .add_local_dir("config", remote_path="/root/peit/config")
    .add_local_dir("core", remote_path="/root/peit/core")
    .add_local_dir("geometry_input", remote_path="/root/peit/geometry_input")
    .add_local_dir("utils", remote_path="/root/peit/utils")
    .add_local_dir("templates", remote_path="/root/peit/templates")
    .add_local_dir("static", remote_path="/root/peit/static")
    .add_local_dir("fonts", remote_path="/root/peit/fonts")
    .add_local_dir("images", remote_path="/root/peit/images")
)


def upload_to_vercel_blob(content: bytes, pathname: str, content_type: str) -> str:
    """Upload content to Vercel Blob and return public URL.

    Args:
        content: File content as bytes
        pathname: Path/filename in blob storage (e.g., "maps/{job_id}/index.html")
        content_type: MIME type (e.g., "text/html", "application/pdf")

    Returns:
        Public URL of the uploaded blob
    """
    from vercel.blob import BlobClient

    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if not token:
        raise ValueError("BLOB_READ_WRITE_TOKEN not configured")

    client = BlobClient(token=token)
    blob = client.put(
        pathname,
        content,
        access="public",
        content_type=content_type,
    )
    return blob.url


def get_supabase_client():
    """Create Supabase client with service role key (bypasses RLS).

    Returns None if credentials are not configured.
    Configures SSL certificates for containerized environments.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        return None

    try:
        import certifi

        # Set all SSL-related environment variables BEFORE importing supabase
        # httpx respects SSL_CERT_FILE when creating default SSL context
        cert_path = certifi.where()
        os.environ["SSL_CERT_FILE"] = cert_path
        os.environ["REQUESTS_CA_BUNDLE"] = cert_path
        os.environ["CURL_CA_BUNDLE"] = cert_path

        # Also configure httpx directly via its environment variable
        os.environ["HTTPX_SSL_CERT_FILE"] = cert_path

        from supabase import create_client
        return create_client(url, key)
    except Exception as e:
        print(f"Warning: Failed to create Supabase client: {e}")
        return None


@app.function(
    image=peit_image,
    timeout=600,
    volumes={"/results": results_volume},
    secrets=[vercel_blob_secret, supabase_secret]
)
def process_file_task(
    file_content: bytes,
    filename: str,
    job_id: str,
    user_id: str = None,
    project_name: str = "",
    project_id: str = "",
    buffer_distance_feet: int = 500,
    clip_buffer_miles: float = 0.2,
) -> dict:
    """
    Process a geospatial file and generate PEIT outputs.

    Returns a dict with status and paths to generated files.
    """
    import sys
    import json
    import zipfile
    import tempfile
    import shutil
    import time
    from datetime import datetime
    from pathlib import Path

    sys.path.insert(0, "/root/peit")

    # Import PEIT modules
    from config.config_loader import load_config, load_geometry_settings
    from core.layer_processor import process_all_layers
    from core.map_builder import create_web_map
    from geometry_input.pipeline import process_input_geometry
    from utils.logger import setup_logging, get_logger

    # Create temp directories
    temp_dir = Path(tempfile.mkdtemp())
    input_file = temp_dir / filename
    output_base = Path("/results") / job_id
    output_base.mkdir(parents=True, exist_ok=True)

    # Initialize Supabase client for job tracking
    supabase = get_supabase_client()

    # Insert job record (before processing starts)
    if supabase:
        try:
            supabase.table('jobs').insert({
                'id': job_id,
                'user_id': user_id if user_id else None,
                'filename': filename,
                'project_name': project_name if project_name else None,
                'project_id': project_id if project_id else None,
                'status': 'processing',
            }).execute()
        except Exception as db_error:
            # Log but don't fail - processing continues without job tracking
            print(f"Warning: Failed to insert job record: {db_error}")

    try:
        # Save uploaded file
        with open(input_file, "wb") as f:
            f.write(file_content)

        # Setup logging
        log_dir = temp_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        setup_logging(log_dir)
        logger = get_logger(__name__)

        logger.info(f"Processing job {job_id}: {filename}")

        # Load configuration
        config = load_config()

        # Override geometry settings with user parameters
        if "geometry_settings" not in config:
            config["geometry_settings"] = {}
        config["geometry_settings"]["buffer_distance_feet"] = buffer_distance_feet
        config["geometry_settings"]["clip_buffer_miles"] = clip_buffer_miles

        # Process input geometry
        geometry_settings = load_geometry_settings(config)
        polygon_gdf, input_geometry_metadata, original_gdf = process_input_geometry(
            str(input_file),
            buffer_distance_feet=geometry_settings["buffer_distance_feet"]
        )

        # Validate input geometry area against limit
        actual_area = None  # Will be set after geometry processing if available
        max_area = geometry_settings.get('max_input_area_sq_miles', MAX_INPUT_AREA_SQ_MILES)
        if input_geometry_metadata and input_geometry_metadata.get('buffer_area'):
            actual_area = input_geometry_metadata['buffer_area'].get('area_sq_miles_approx', 0)
            if actual_area > max_area:
                raise ValueError(
                    f"Input area ({actual_area:.1f} sq mi) exceeds maximum allowed ({max_area} sq mi). "
                    "Please use a smaller geometry or reduce buffer distance."
                )
            logger.info(f"Input geometry area: {actual_area:.1f} sq mi (limit: {max_area} sq mi)")

        input_filename = Path(filename).stem
        # Use project name for input layer display if provided, otherwise use filename
        input_layer_name = project_name if project_name else input_filename

        # Progress tracking file on Modal Volume
        progress_file = output_base / "progress.json"

        def emit_progress(
            stage: str,
            layer_name: str = None,
            completed: int = 0,
            total: int = 0,
            features: int = 0
        ):
            """Write progress update to volume file for SSE poller to read.

            Note: Does NOT commit volume - relies on Modal's internal caching.
            Final commit happens at task completion to persist all results.
            """
            progress_data = {
                'stage': stage,
                'layer_name': layer_name,
                'completed_layers': completed,
                'total_layers': total,
                'features_found': features,
                'timestamp': time.time()
            }
            try:
                with open(progress_file, 'w', encoding='utf-8') as f:
                    json.dump(progress_data, f)
                # No commit - Modal's volume caching allows SSE poller to read recent writes
                # Final commit at task completion ensures data persisted
            except Exception as e:
                # Don't fail processing if progress write fails
                logger.warning(f"Failed to write progress: {e}")

        # Stage 1: Geometry input (2%)
        # Emit progress at start and end for smooth increments
        emit_progress('geometry_input', completed=0, total=1)

        # Geometry processing happens here (pipeline.process_geometry already ran)
        # This stage represents validation and final geometry preparation

        emit_progress('geometry_input', completed=1, total=1)

        # Layer callback for progress tracking
        def layer_callback(name, completed, total, features):
            """Called after each layer completes."""
            emit_progress('layer_query', name, completed, total, features)

        # Process all layers with progress callback
        emit_progress('layer_querying', total=len(config['layers']))
        layer_results, metadata, clip_summary, clip_boundary = process_all_layers(
            polygon_gdf, config, progress_callback=layer_callback
        )

        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        xlsx_filename = f"PEIT_Report_{timestamp}.xlsx"
        pdf_filename = f"PEIT_Report_{timestamp}.pdf"

        # Generate output (temporarily to local temp)
        output_name = f"peit_map_{timestamp}"
        temp_output = temp_dir / output_name
        temp_output.mkdir(parents=True, exist_ok=True)

        # Stage 3: Map generation (2%)
        emit_progress('map_generation', completed=0, total=2)

        # Create web map (note: PDF/XLSX URLs will be added after blob upload)
        map_obj = create_web_map(
            polygon_gdf, layer_results, metadata, config, input_layer_name,
            project_name=project_name,
            xlsx_relative_path=None,  # Will be updated after blob upload
            pdf_relative_path=None,   # Will be updated after blob upload
            clip_boundary=clip_boundary,
            original_geometry_gdf=original_gdf
        )

        emit_progress('map_generation', completed=1, total=2)

        # Save map HTML temporarily
        map_file = temp_output / "index.html"
        map_obj.save(str(map_file))

        emit_progress('map_generation', completed=2, total=2)

        # Stage 4: Report generation (2%)
        emit_progress('report_generation', completed=0, total=2)

        # Generate reports
        from utils.xlsx_generator import generate_xlsx_report
        from utils.pdf_generator import generate_pdf_report

        generate_xlsx_report(
            layer_results, config, temp_output, timestamp, project_name, project_id, metadata=metadata
        )

        emit_progress('report_generation', completed=1, total=2)

        generate_pdf_report(
            layer_results, config, temp_output, timestamp, project_name, project_id, metadata=metadata
        )

        emit_progress('report_generation', completed=2, total=2)

        # Stage 5: Blob upload (1%)
        emit_progress('blob_upload', completed=0, total=3)

        # Upload reports to Vercel Blob
        pdf_blob_url = None
        xlsx_blob_url = None

        try:
            pdf_path = temp_output / pdf_filename
            if pdf_path.exists():
                pdf_content = pdf_path.read_bytes()
                pdf_blob_url = upload_to_vercel_blob(
                    pdf_content,
                    f"maps/{job_id}/{pdf_filename}",
                    "application/pdf"
                )
                logger.info(f"Uploaded PDF to blob: {pdf_blob_url}")

            emit_progress('blob_upload', completed=1, total=3)
            time.sleep(0.3)  # Allow SSE poller to catch this progress state

            xlsx_path = temp_output / xlsx_filename
            if xlsx_path.exists():
                xlsx_content = xlsx_path.read_bytes()
                xlsx_blob_url = upload_to_vercel_blob(
                    xlsx_content,
                    f"maps/{job_id}/{xlsx_filename}",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                logger.info(f"Uploaded XLSX to blob: {xlsx_blob_url}")

            emit_progress('blob_upload', completed=2, total=3)
            time.sleep(0.3)  # Allow SSE poller to catch this progress state
        except Exception as blob_error:
            # Log but don't fail - map will work without report links
            logger.warning(f"Report blob upload failed (non-fatal): {blob_error}")

        # Update map HTML with blob URLs if needed
        if pdf_blob_url or xlsx_blob_url:
            # Re-create map with blob URLs
            map_obj = create_web_map(
                polygon_gdf, layer_results, metadata, config, input_layer_name,
                project_name=project_name,
                xlsx_relative_path=xlsx_blob_url,
                pdf_relative_path=pdf_blob_url,
                clip_boundary=clip_boundary,
                original_geometry_gdf=original_gdf
            )
            # Re-save map HTML with updated URLs
            map_obj.save(str(map_file))

        # Save input polygon and layer GeoJSONs
        data_path = temp_output / "data"
        data_path.mkdir(exist_ok=True)

        polygon_file = data_path / "input_polygon.geojson"
        polygon_gdf.to_file(polygon_file, driver="GeoJSON")

        for layer_name, gdf in layer_results.items():
            safe_name = layer_name.replace(" ", "_").replace("/", "_").lower()
            layer_file = data_path / f"{safe_name}.geojson"
            gdf.to_file(layer_file, driver="GeoJSON")

        # Save metadata
        summary = {
            "generated_at": datetime.now().isoformat(),
            "job_id": job_id,
            "input_file": filename,
            "project_name": project_name,
            "project_id": project_id,
            "total_features": sum(m.get("feature_count", 0) for m in metadata.values() if isinstance(m, dict)),
            "layers_with_data": sum(1 for m in metadata.values() if isinstance(m, dict) and m.get("feature_count", 0) > 0),
        }

        if input_geometry_metadata:
            summary["input_geometry"] = input_geometry_metadata

        metadata_file = temp_output / "metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        # Create ZIP file
        zip_filename = f"peit_results_{job_id}.zip"
        zip_path = output_base / zip_filename

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path in temp_output.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(temp_output)
                    zipf.write(file_path, arcname)

        # Commit volume changes
        results_volume.commit()

        # Upload map HTML to Vercel Blob for live URL access
        # (PDF/XLSX already uploaded earlier before map generation)
        map_blob_url = None

        try:
            map_content = map_file.read_bytes()
            map_blob_url = upload_to_vercel_blob(
                map_content,
                f"maps/{job_id}/index.html",
                "text/html"
            )
            logger.info(f"Uploaded map to blob: {map_blob_url}")
        except Exception as blob_error:
            # Log but don't fail - ZIP download still works
            logger.warning(f"Map blob upload failed (non-fatal): {blob_error}")

        # Final progress update (completes blob_upload stage)
        emit_progress('blob_upload', completed=3, total=3)
        time.sleep(0.3)  # Allow SSE poller to catch 100% before completion event

        logger.info(f"Job {job_id} completed successfully")

        # Update job record with completion status
        if supabase:
            try:
                supabase.table('jobs').update({
                    'status': 'complete',
                    'completed_at': datetime.now().isoformat(),
                    'total_features': summary["total_features"],
                    'layers_with_data': summary["layers_with_data"],
                    'input_area_sq_miles': round(actual_area, 2) if actual_area else None,
                    'map_url': f'https://peit-map-creator.com/maps/{job_id}',
                    'pdf_url': pdf_blob_url,
                    'xlsx_url': xlsx_blob_url,
                    'zip_download_path': f'/api/download/{job_id}',
                }).eq('id', job_id).execute()
            except Exception as db_error:
                logger.warning(f"Failed to update job record: {db_error}")

        return {
            "success": True,
            "job_id": job_id,
            "zip_filename": zip_filename,
            "total_features": summary["total_features"],
            "layers_with_data": summary["layers_with_data"],
            "map_blob_url": map_blob_url,
            "pdf_blob_url": pdf_blob_url,
            "xlsx_blob_url": xlsx_blob_url,
        }

    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"

        # Update job record with error status
        if supabase:
            try:
                supabase.table('jobs').update({
                    'status': 'failed',
                    'completed_at': datetime.now().isoformat(),
                    'input_area_sq_miles': round(actual_area, 2) if actual_area else None,
                    'error_message': str(e)[:500],  # Truncate long errors
                }).eq('id', job_id).execute()
            except Exception as db_error:
                print(f"Warning: Failed to update job error: {db_error}")

        return {
            "success": False,
            "job_id": job_id,
            "error": str(e),
            "traceback": error_msg,
        }

    finally:
        # Cleanup temp directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


# Mount the FastAPI app to Modal
# All FastAPI imports and app creation happen inside this function
# so they only run in the Modal container, not on the local machine
@app.function(
    image=peit_image,
    timeout=600,  # 10 minutes (matches process_file_task timeout)
    volumes={"/results": results_volume},
    secrets=[supabase_secret, vercel_blob_secret],  # For account/job deletion endpoints
)
@modal.concurrent(max_inputs=10)
@modal.asgi_app()
def fastapi_app():
    """Create and return the FastAPI application."""
    import uuid
    import json
    import asyncio
    from pathlib import Path
    from datetime import datetime
    from typing import AsyncGenerator

    from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
    from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
    from fastapi.middleware.cors import CORSMiddleware
    from starlette.middleware.base import BaseHTTPMiddleware

    # Request size limit middleware - rejects oversized requests before reading body
    class LimitUploadSizeMiddleware(BaseHTTPMiddleware):
        """Reject requests with Content-Length exceeding limit."""

        def __init__(self, app, max_size: int = 6 * 1024 * 1024):
            super().__init__(app)
            self.max_size = max_size

        async def dispatch(self, request, call_next):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.max_size:
                return JSONResponse(
                    status_code=413,
                    content={"error": "Request too large", "max_size_mb": self.max_size // (1024 * 1024)}
                )
            return await call_next(request)

    web_app = FastAPI(title="PEIT Processor API")

    # Add request size limit middleware (before CORS)
    web_app.add_middleware(LimitUploadSizeMiddleware, max_size=6 * 1024 * 1024)  # 6MB with overhead

    # Add CORS middleware for frontend access
    web_app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://peit-map-creator.com",
            "https://www.peit-map-creator.com",
            "https://peit-map-creator.vercel.app",  # Keep temporarily for migration
            "https://peit-map-creator-*.vercel.app",  # Preview deployments
            "http://localhost:3000",  # Local development
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def check_anonymous_rate_limit(ip: str) -> bool:
        """Check if anonymous user (IP) has exceeded daily rate limit (4/day)."""
        key = f"{ip}:{datetime.now().strftime('%Y-%m-%d')}"
        try:
            count = rate_limit_dict.get(key, 0)
            if count >= MAX_RUNS_PER_DAY_ANONYMOUS:
                return False
            rate_limit_dict[key] = count + 1
            return True
        except Exception:
            # If Dict is unavailable, allow the request
            return True

    def get_anonymous_remaining_runs(ip: str) -> int:
        """Get remaining runs for anonymous user (IP) today."""
        key = f"{ip}:{datetime.now().strftime('%Y-%m-%d')}"
        try:
            count = rate_limit_dict.get(key, 0)
            return max(0, MAX_RUNS_PER_DAY_ANONYMOUS - count)
        except Exception:
            return MAX_RUNS_PER_DAY_ANONYMOUS

    def check_user_rate_limit(user_id: str) -> bool:
        """Check if authenticated user has exceeded daily rate limit (20/day)."""
        key = f"{user_id}:{datetime.now().strftime('%Y-%m-%d')}"
        try:
            count = user_rate_limit_dict.get(key, 0)
            if count >= MAX_RUNS_PER_DAY_AUTHENTICATED:
                return False
            user_rate_limit_dict[key] = count + 1
            return True
        except Exception:
            # If Dict is unavailable, allow the request
            return True

    def get_user_remaining_runs(user_id: str) -> int:
        """Get remaining runs for authenticated user today."""
        key = f"{user_id}:{datetime.now().strftime('%Y-%m-%d')}"
        try:
            count = user_rate_limit_dict.get(key, 0)
            return max(0, MAX_RUNS_PER_DAY_AUTHENTICATED - count)
        except Exception:
            return MAX_RUNS_PER_DAY_AUTHENTICATED

    def check_concurrent_limit(ip: str) -> bool:
        """Check if IP has too many active jobs. Returns True if allowed."""
        key = f"active:{ip}"
        try:
            active = active_jobs_dict.get(key, 0)
            if active >= MAX_CONCURRENT_JOBS_PER_IP:
                print(f"[RATE LIMIT] Concurrent limit hit for {ip}: {active} active jobs")
                return False
            active_jobs_dict[key] = active + 1
            print(f"[RATE LIMIT] Slot acquired for {ip}: {active + 1} active jobs")
            return True
        except Exception:
            # If Dict is unavailable, allow the request
            return True

    def release_job_slot(ip: str):
        """Release a job slot when processing completes."""
        key = f"active:{ip}"
        try:
            active = active_jobs_dict.get(key, 1)
            new_count = max(0, active - 1)
            active_jobs_dict[key] = new_count
            print(f"[RATE LIMIT] Slot released for {ip}: {new_count} active jobs")
        except Exception:
            pass

    def check_global_rate_limit() -> bool:
        """Check if global daily limit has been exceeded. Returns True if allowed."""
        key = f"global:{datetime.now().strftime('%Y-%m-%d')}"
        try:
            count = global_rate_limit_dict.get(key, 0)
            if count >= MAX_GLOBAL_RUNS_PER_DAY:
                return False
            global_rate_limit_dict[key] = count + 1
            return True
        except Exception:
            # If Dict is unavailable, allow the request
            return True

    def get_global_remaining_runs() -> int:
        """Get remaining global runs for today."""
        key = f"global:{datetime.now().strftime('%Y-%m-%d')}"
        try:
            count = global_rate_limit_dict.get(key, 0)
            return max(0, MAX_GLOBAL_RUNS_PER_DAY - count)
        except Exception:
            return MAX_GLOBAL_RUNS_PER_DAY

    @web_app.get("/api/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": "peit-processor"}

    @web_app.get("/api/reverse-geocode")
    async def reverse_geocode(lat: float, lon: float):
        """Proxy reverse geocoding to Nominatim.

        This endpoint proxies requests to Nominatim's reverse geocoding API
        to avoid CORS issues when calling from the browser. Nominatim's public
        API doesn't include CORS headers, so browser requests fail.

        Args:
            lat: Latitude coordinate
            lon: Longitude coordinate

        Returns:
            Nominatim response JSON or error message
        """
        import httpx

        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json",
            "addressdetails": 1
        }
        headers = {
            "User-Agent": "PEITMapCreator/1.0 (https://peit-map-creator.com)"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, headers=headers, timeout=10.0)
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"error": f"Nominatim returned status {response.status_code}"}
        except httpx.TimeoutException:
            return {"error": "Geocoding request timed out"}
        except Exception as e:
            return {"error": str(e)}

    @web_app.get("/api/rate-limit")
    async def get_rate_limit_endpoint(request: Request, user_id: str = None):
        """Get rate limit status. Pass user_id query param for authenticated user limits."""
        client_ip = request.client.host if request.client else "unknown"
        global_remaining = get_global_remaining_runs()

        if user_id:
            # Authenticated user - return user-based limits
            remaining = get_user_remaining_runs(user_id)
            max_runs = MAX_RUNS_PER_DAY_AUTHENTICATED
            limit_type = "per_user"
        else:
            # Anonymous user - return IP-based limits
            remaining = get_anonymous_remaining_runs(client_ip)
            max_runs = MAX_RUNS_PER_DAY_ANONYMOUS
            limit_type = "per_ip"

        return {
            "remaining_runs": remaining,
            "max_runs_per_day": max_runs,
            "limit_type": limit_type,
            "global_remaining_runs": global_remaining,
            "max_global_runs_per_day": MAX_GLOBAL_RUNS_PER_DAY,
            "resets_at": "midnight UTC",
        }

    # Stage weights for progress calculation (hardcoded for initial release)
    STAGE_WEIGHTS = {
        'upload': 1,  # Initial state (prevent 0% display)
        'geometry_input': 2,
        'layer_querying': 92,  # Increased to 92% (bulk of processing)
        'map_generation': 2,
        'report_generation': 2,
        'blob_upload': 1,
    }

    def calculate_weighted_progress(progress_data: dict) -> int:
        """Calculate progress percentage based on stage weights and layer completion."""
        stage = progress_data.get('stage', 'upload')

        # Stage order for calculating completed weight
        stage_order = ['upload', 'geometry_input', 'layer_querying', 'map_generation', 'report_generation', 'blob_upload']
        completed_weight = 0.0

        try:
            current_stage_idx = stage_order.index(stage)
        except ValueError:
            # Unknown stage - treat 'layer_query' same as 'layer_querying'
            if stage == 'layer_query':
                current_stage_idx = stage_order.index('layer_querying')
            else:
                return 5  # Default to 5% for unknown stages

        # Add weights of all completed stages
        for idx, s in enumerate(stage_order):
            if idx < current_stage_idx:
                completed_weight += STAGE_WEIGHTS.get(s, 0)

        # Add partial progress from current stage
        if stage in ['layer_querying', 'layer_query']:
            completed = progress_data.get('completed_layers', 0)
            total = progress_data.get('total_layers', 1)
            if total > 0:
                layer_progress = (completed / total) * STAGE_WEIGHTS['layer_querying']
                completed_weight += layer_progress
            else:
                # If total unknown, assume halfway through stage
                completed_weight += STAGE_WEIGHTS['layer_querying'] * 0.5
        elif stage in STAGE_WEIGHTS:
            # For other stages, check if we have completed/total info
            completed = progress_data.get('completed_layers', 0)
            total = progress_data.get('total_layers', 0)
            if total > 0:
                # Use actual progress within the stage
                stage_progress = (completed / total) * STAGE_WEIGHTS[stage]
                completed_weight += stage_progress
            else:
                # If no progress info, assume halfway through when stage starts
                completed_weight += STAGE_WEIGHTS[stage] * 0.5

        # Round to nearest integer for smoother display (no jumps >1%)
        # Cap at 100 (allow progress to reach 100% naturally through final stages)
        return min(round(completed_weight), 100)

    def format_progress_message(progress_data: dict) -> str:
        """Format user-friendly progress message based on stage."""
        stage = progress_data.get('stage')
        layer_name = progress_data.get('layer_name')
        completed = progress_data.get('completed_layers', 0)
        total = progress_data.get('total_layers', 0)

        if stage == 'upload':
            return 'File received, starting processing...'
        elif stage == 'geometry_input':
            return 'Processing input geometry...'
        elif stage in ['layer_querying', 'layer_query']:
            if layer_name:
                return f'Querying {layer_name}... ({completed}/{total} layers)'
            elif total > 0:
                return f'Querying environmental layers... ({completed}/{total})'
            else:
                return 'Querying environmental layers...'
        elif stage == 'map_generation':
            return 'Generating interactive map...'
        elif stage == 'report_generation':
            return 'Creating PDF and Excel reports...'
        elif stage == 'blob_upload':
            return 'Uploading to cloud storage...'
        else:
            return 'Processing...'

    @web_app.post("/api/process")
    async def process_endpoint(
        request: Request,
        file: UploadFile = File(...),
        user_id: str = Form(None),
        project_name: str = Form(""),
        project_id: str = Form(""),
        buffer_distance_feet: int = Form(500),
        clip_buffer_miles: float = Form(0.2),
    ):
        """
        Process a geospatial file and stream progress via SSE.

        Returns Server-Sent Events with progress updates, then final result.
        """
        client_ip = request.client.host if request.client else "unknown"

        # Global rate limit check (check FIRST, before per-IP)
        if not check_global_rate_limit():
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Service limit reached",
                    "message": "Daily processing limit reached for all users. Please try again tomorrow.",
                    "limit_type": "global",
                    "remaining_runs": 0,
                }
            )

        # Tiered rate limit check: authenticated users (20/day) vs anonymous (4/day)
        if user_id:
            # Authenticated user - check user-based limit (20/day)
            if not check_user_rate_limit(user_id):
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "message": f"Maximum {MAX_RUNS_PER_DAY_AUTHENTICATED} runs per day for authenticated users. Please try again tomorrow.",
                        "limit_type": "per_user",
                        "remaining_runs": 0,
                    }
                )
        else:
            # Anonymous user - check IP-based limit (4/day)
            if not check_anonymous_rate_limit(client_ip):
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "message": f"Maximum {MAX_RUNS_PER_DAY_ANONYMOUS} runs per day for anonymous users. Sign up for {MAX_RUNS_PER_DAY_AUTHENTICATED} runs per day.",
                        "limit_type": "per_ip",
                        "remaining_runs": 0,
                    }
                )

        # Validate file BEFORE acquiring concurrent job slot
        # This prevents slot leaks when validation fails
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        # Check file extension
        valid_extensions = {".shp", ".kml", ".kmz", ".gpkg", ".geojson", ".json", ".gdb", ".zip"}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in valid_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Supported: {', '.join(valid_extensions)}"
            )

        # Read file content
        file_content = await file.read()

        # Check file size (5MB limit)
        max_size = 5 * 1024 * 1024
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=400,
                detail="File too large. Maximum size: 5MB"
            )

        # Concurrent job limit check - AFTER validation to prevent slot leaks
        # If validation fails above, we don't consume a slot
        if not check_concurrent_limit(client_ip):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too many concurrent jobs",
                    "message": f"Maximum {MAX_CONCURRENT_JOBS_PER_IP} simultaneous jobs. Please wait for current jobs to complete.",
                }
            )

        # Generate job ID (16 chars for security - prevents URL enumeration)
        job_id = str(uuid.uuid4()).replace("-", "")[:16]

        async def event_generator() -> AsyncGenerator[str, None]:
            """Generate SSE events for progress updates."""

            # Get Supabase client for database updates on timeout
            supabase = get_supabase_client()

            # Send initial event
            yield f"data: {json.dumps({'stage': 'upload', 'message': 'File received, starting processing...', 'progress': 1, 'job_id': job_id})}\n\n"

            # Spawn the processing task (non-blocking)
            try:
                handle = process_file_task.spawn(
                    file_content=file_content,
                    filename=file.filename,
                    job_id=job_id,
                    user_id=user_id,
                    project_name=project_name,
                    project_id=project_id,
                    buffer_distance_feet=buffer_distance_feet,
                    clip_buffer_miles=clip_buffer_miles,
                )

                # Poll for completion with progress file reads
                poll_interval = 1.0  # Poll every 1 second (faster than old 3s)
                last_progress_data = None

                # Fake progress for upload/geometry stages (provides smooth UX during file processing)
                # These emits happen on poller side (zero task overhead), real progress from task overrides
                progress_file_path = Path(f"/results/{job_id}/progress.json")
                fake_progress_stages = [
                    (0.5, {'stage': 'upload', 'message': 'Uploading file...', 'progress': 1}),
                    (1.0, {'stage': 'upload', 'message': 'File received, validating...', 'progress': 2}),
                    (1.5, {'stage': 'geometry_input', 'message': 'Processing input geometry...', 'progress': 3}),
                    (2.0, {'stage': 'geometry_input', 'message': 'Validating geometry...', 'progress': 4}),
                ]

                import time
                start_time = time.time()
                fake_idx = 0

                while True:
                    await asyncio.sleep(0.1)  # Small sleep to allow checking both fake and real progress

                    # Emit fake progress if real progress hasn't started yet
                    elapsed = time.time() - start_time
                    if fake_idx < len(fake_progress_stages) and not progress_file_path.exists():
                        delay, fake_event = fake_progress_stages[fake_idx]
                        if elapsed >= delay:
                            yield f"data: {json.dumps(fake_event)}\n\n"
                            fake_idx += 1
                        continue  # Skip to next iteration

                    # Real progress started or all fake progress emitted - switch to normal polling
                    if fake_idx >= len(fake_progress_stages) or progress_file_path.exists():
                        break

                # Normal polling loop (1 second intervals)
                while True:
                    await asyncio.sleep(poll_interval)

                    # Check if task is done (non-blocking check)
                    try:
                        result = handle.get(timeout=0)
                        # Task completed - release job slot
                        release_job_slot(client_ip)
                        if result["success"]:
                            # Build completion response with blob URLs
                            completion_data = {
                                'stage': 'complete',
                                'message': 'Processing complete!',
                                'progress': 100,
                                'job_id': job_id,
                                'download_url': f'/api/download/{job_id}',
                                'map_url': f'https://peit-map-creator.com/maps/{job_id}',
                                'map_blob_url': result.get('map_blob_url'),
                                'pdf_url': result.get('pdf_blob_url'),
                                'xlsx_url': result.get('xlsx_blob_url'),
                            }
                            yield f"data: {json.dumps(completion_data)}\n\n"
                        else:
                            yield f"data: {json.dumps({'stage': 'error', 'message': result.get('error', 'Unknown error'), 'progress': 0, 'error': result.get('error')})}\n\n"
                        break
                    except FunctionTimeoutError as e:
                        # Modal cancelled the task due to execution timeout (~10 minutes)
                        print(f"[TIMEOUT] Job {job_id} exceeded execution time limit: {str(e)}")

                        # Release concurrent job slot
                        release_job_slot(client_ip)

                        # Update database to failed status (with error handling)
                        if supabase:
                            try:
                                from datetime import datetime, timezone
                                supabase.table('jobs').update({
                                    'status': 'failed',
                                    'completed_at': datetime.now(timezone.utc).isoformat(),
                                    'error_message': 'Processing exceeded the 10-minute time limit. Try a smaller area or simpler geometry.',
                                }).eq('id', job_id).execute()
                            except Exception as db_err:
                                print(f"Warning: Failed to update database for timed-out job {job_id}: {db_err}")

                        # Emit SSE error event to frontend
                        yield f"data: {json.dumps({'stage': 'error', 'message': 'Processing exceeded the 10-minute time limit. This usually happens with very large or complex areas. Try a smaller area, simpler geometry, or contact support.', 'progress': 0, 'error': 'timeout'})}\n\n"
                        break
                    except TimeoutError:
                        # Task still running - read progress file
                        try:
                            results_volume.reload()
                            progress_file_path = Path(f"/results/{job_id}/progress.json")

                            if progress_file_path.exists():
                                with open(progress_file_path, 'r', encoding='utf-8') as f:
                                    progress_data = json.load(f)

                                # Only emit if progress changed (avoid duplicate events)
                                if progress_data != last_progress_data:
                                    last_progress_data = progress_data

                                    # Calculate weighted progress
                                    progress_percent = calculate_weighted_progress(progress_data)

                                    # Format message
                                    message = format_progress_message(progress_data)

                                    # Build SSE event
                                    event_data = {
                                        'stage': progress_data.get('stage', 'processing'),
                                        'message': message,
                                        'progress': progress_percent,
                                        'layer_name': progress_data.get('layer_name'),
                                        'currentLayer': progress_data.get('completed_layers'),
                                        'totalLayers': progress_data.get('total_layers'),
                                        'features_found': progress_data.get('features_found'),
                                    }

                                    yield f"data: {json.dumps(event_data)}\n\n"
                            # else: No progress file yet, wait for next poll

                        except Exception as e:
                            # Progress file read failed - log but continue polling
                            print(f"Warning: Failed to read progress file for {job_id}: {e}")

            except asyncio.CancelledError:
                # Client disconnected (closed browser tab) - release job slot
                print(f"[SSE] Client disconnected for job {job_id}, releasing slot for {client_ip}")
                release_job_slot(client_ip)
                raise  # Must re-raise CancelledError to properly close the generator
            except Exception as e:
                # Release job slot on error
                release_job_slot(client_ip)
                yield f"data: {json.dumps({'stage': 'error', 'message': str(e), 'progress': 0, 'error': str(e)})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            }
        )

    @web_app.get("/api/download/{job_id}")
    async def download_result(job_id: str):
        """Download the result ZIP file for a completed job."""
        # Reload volume to see recent writes from other containers
        results_volume.reload()

        zip_filename = f"peit_results_{job_id}.zip"
        zip_path = Path("/results") / job_id / zip_filename

        if not zip_path.exists():
            raise HTTPException(status_code=404, detail="Result not found or expired")

        return FileResponse(
            path=str(zip_path),
            filename=zip_filename,
            media_type="application/zip"
        )

    @web_app.post("/api/claim-jobs")
    async def claim_jobs(request: Request):
        """Claim unclaimed jobs for a newly authenticated user.

        This allows anonymous users who just signed up to associate
        their previously created jobs with their new account.

        Body:
            user_id: str - The authenticated user's ID
            job_ids: list[str] - Array of job IDs to claim

        Returns:
            claimed_count: int - Number of jobs successfully claimed
        """
        try:
            body = await request.json()
            user_id = body.get("user_id")
            job_ids = body.get("job_ids", [])

            if not user_id:
                raise HTTPException(status_code=400, detail="user_id is required")

            if not job_ids or not isinstance(job_ids, list):
                raise HTTPException(status_code=400, detail="job_ids must be a non-empty array")

            # Validate job_ids are valid format (16 hex chars)
            import re
            valid_job_ids = [
                jid for jid in job_ids
                if isinstance(jid, str) and re.match(r'^[a-f0-9]{16}$', jid)
            ]

            if not valid_job_ids:
                return {"claimed_count": 0, "message": "No valid job IDs provided"}

            supabase = get_supabase_client()
            if not supabase:
                raise HTTPException(status_code=500, detail="Database not configured")

            # Update jobs where id is in the list AND user_id is NULL
            # This prevents claiming jobs that already belong to another user
            claimed_count = 0
            for job_id in valid_job_ids:
                try:
                    # Check if job exists and is unclaimed
                    result = supabase.table('jobs').update({
                        'user_id': user_id
                    }).eq('id', job_id).is_('user_id', 'null').execute()

                    # Count successful updates
                    if result.data and len(result.data) > 0:
                        claimed_count += 1
                except Exception as e:
                    # Log but continue with other jobs
                    print(f"Warning: Failed to claim job {job_id}: {e}")

            return {
                "success": True,
                "claimed_count": claimed_count,
                "message": f"Successfully claimed {claimed_count} job(s)"
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @web_app.delete("/api/account")
    async def delete_account(request: Request):
        """Delete a user account and all associated data.

        Requires user_id in JSON body. This endpoint:
        1. Deletes all jobs associated with the user from Supabase
        2. Deletes the user account from Supabase Auth
        """
        try:
            body = await request.json()
            user_id = body.get("user_id")

            if not user_id:
                raise HTTPException(status_code=400, detail="user_id is required")

            supabase = get_supabase_client()
            if not supabase:
                raise HTTPException(status_code=500, detail="Database not configured")

            # Delete user's jobs from database
            try:
                supabase.table('jobs').delete().eq('user_id', user_id).execute()
            except Exception as e:
                # Log but continue - user deletion is more important
                print(f"Warning: Failed to delete jobs for user {user_id}: {e}")

            # Delete user account using Supabase Admin API
            try:
                supabase.auth.admin.delete_user(user_id)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to delete user account: {str(e)}"
                )

            return {"success": True, "message": "Account deleted successfully"}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @web_app.delete("/api/jobs/{job_id}")
    async def delete_job(job_id: str, request: Request):
        """Delete a job and all associated storage (Supabase, Modal Volume, Vercel Blob).

        Requires user_id in JSON body. Only the job owner can delete their job.
        """
        import re
        import shutil
        from vercel.blob import BlobClient

        # Validate job_id format (16 hex chars)
        if not re.match(r'^[a-f0-9]{16}$', job_id):
            raise HTTPException(status_code=400, detail="Invalid job ID format")

        try:
            body = await request.json()
            user_id = body.get("user_id")

            if not user_id:
                raise HTTPException(status_code=400, detail="user_id is required")

            supabase = get_supabase_client()
            if not supabase:
                raise HTTPException(status_code=500, detail="Database not configured")

            # Verify job exists and belongs to user
            result = supabase.table('jobs').select('*').eq('id', job_id).single().execute()
            if not result.data:
                raise HTTPException(status_code=404, detail="Job not found")
            if result.data.get('user_id') != user_id:
                raise HTTPException(status_code=403, detail="Not authorized to delete this job")

            deleted_items = {"database": False, "volume": False, "blobs": []}

            # Delete from Modal Volume
            try:
                results_volume.reload()
                job_dir = Path("/results") / job_id
                if job_dir.exists():
                    shutil.rmtree(job_dir)
                    results_volume.commit()
                    deleted_items["volume"] = True
            except Exception as e:
                print(f"Warning: Failed to delete volume files for job {job_id}: {e}")

            # Delete from Vercel Blob using official SDK
            token = os.environ.get("BLOB_READ_WRITE_TOKEN")
            if token:
                try:
                    client = BlobClient(token=token)
                    # List all blobs with job prefix
                    listing = client.list_objects(prefix=f"maps/{job_id}/")
                    blob_urls = [blob.url for blob in listing.blobs]
                    if blob_urls:
                        client.delete(blob_urls)
                        deleted_items["blobs"] = [blob.pathname for blob in listing.blobs]
                except Exception as e:
                    print(f"Warning: Failed to delete blobs for job {job_id}: {e}")

            # Delete from Supabase
            try:
                supabase.table('jobs').delete().eq('id', job_id).execute()
                deleted_items["database"] = True
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to delete job record: {e}")

            return {"success": True, "message": "Job deleted successfully", "deleted": deleted_items}

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return web_app


# Scheduled cleanup job - runs daily at 3 AM UTC
@app.function(
    image=peit_image,
    volumes={"/results": results_volume},
    secrets=[vercel_blob_secret],
    schedule=modal.Cron("0 3 * * *"),  # 3 AM UTC daily
)
def cleanup_old_results():
    """Delete result folders and Vercel Blob files older than 7 days."""
    from pathlib import Path
    from datetime import datetime, timedelta, timezone
    import shutil

    results_path = Path("/results")
    cutoff = datetime.now() - timedelta(days=7)
    cutoff_utc = datetime.now(timezone.utc) - timedelta(days=7)
    deleted_count = 0
    blob_deleted_count = 0

    # Clean up Modal Volume
    if results_path.exists():
        for job_dir in results_path.iterdir():
            if job_dir.is_dir():
                try:
                    # Check modification time
                    mtime = datetime.fromtimestamp(job_dir.stat().st_mtime)
                    if mtime < cutoff:
                        shutil.rmtree(job_dir)
                        deleted_count += 1
                except Exception as e:
                    print(f"Error cleaning up {job_dir}: {e}")

    results_volume.commit()
    print(f"Volume cleanup: deleted {deleted_count} expired job folders")

    # Clean up Vercel Blob using official SDK
    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if token:
        try:
            from vercel.blob import BlobClient

            client = BlobClient(token=token)
            # List all blobs with "maps/" prefix
            listing = client.list_objects(prefix="maps/")
            urls_to_delete = []

            for blob in listing.blobs:
                try:
                    # Check blob upload date
                    if blob.uploaded_at:
                        if blob.uploaded_at < cutoff_utc:
                            urls_to_delete.append(blob.url)
                            blob_deleted_count += 1
                except Exception as e:
                    print(f"Error checking blob {blob.pathname}: {e}")

            # Batch delete expired blobs
            if urls_to_delete:
                client.delete(urls_to_delete)

            print(f"Blob cleanup: deleted {blob_deleted_count} expired blobs")
        except Exception as e:
            print(f"Blob cleanup error: {e}")
    else:
        print("Blob cleanup skipped: BLOB_READ_WRITE_TOKEN not configured")

    return {
        "volume_deleted": deleted_count,
        "blob_deleted": blob_deleted_count,
        "cutoff_date": cutoff.isoformat()
    }


# Entry point for modal serve/deploy
if __name__ == "__main__":
    print("Use 'modal serve modal_app.py' for development")
    print("Use 'modal deploy modal_app.py' for production")
