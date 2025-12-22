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
import os

# Create Modal app
app = modal.App("peit-processor")

# Vercel Blob secret for uploading maps
vercel_blob_secret = modal.Secret.from_name("vercel-blob", required_keys=["BLOB_READ_WRITE_TOKEN"])

# Supabase secret for job tracking (optional - jobs work without it)
supabase_secret = modal.Secret.from_name("supabase-service", required_keys=["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"])

# Modal Dict for rate limiting
rate_limit_dict = modal.Dict.from_name("peit-rate-limits", create_if_missing=True)
MAX_RUNS_PER_DAY = 20

# Modal Dict for tracking active jobs per IP
active_jobs_dict = modal.Dict.from_name("peit-active-jobs", create_if_missing=True)
MAX_CONCURRENT_JOBS_PER_IP = 3

# Modal Dict for global rate limit (across all users)
global_rate_limit_dict = modal.Dict.from_name("peit-global-rate-limit", create_if_missing=True)
MAX_GLOBAL_RUNS_PER_DAY = 50

# Maximum input geometry area in square miles
MAX_INPUT_AREA_SQ_MILES = 5000

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
    clip_buffer_miles: float = 1.0,
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
        polygon_gdf, input_geometry_metadata = process_input_geometry(
            str(input_file),
            buffer_distance_feet=geometry_settings["buffer_distance_feet"]
        )

        # Validate input geometry area against limit
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

        # Process all layers
        layer_results, metadata, clip_summary, clip_boundary = process_all_layers(polygon_gdf, config)

        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        xlsx_filename = f"PEIT_Report_{timestamp}.xlsx"
        pdf_filename = f"PEIT_Report_{timestamp}.pdf"

        # Generate output (temporarily to local temp)
        output_name = f"peit_map_{timestamp}"
        temp_output = temp_dir / output_name
        temp_output.mkdir(parents=True, exist_ok=True)

        # Generate reports BEFORE creating web map so we can get blob URLs
        from utils.xlsx_generator import generate_xlsx_report
        from utils.pdf_generator import generate_pdf_report

        generate_xlsx_report(layer_results, config, temp_output, timestamp, project_name, project_id)
        generate_pdf_report(layer_results, config, temp_output, timestamp, project_name, project_id)

        # Upload reports to Vercel Blob BEFORE creating web map
        # This way we can embed the actual blob URLs in the map HTML
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

            xlsx_path = temp_output / xlsx_filename
            if xlsx_path.exists():
                xlsx_content = xlsx_path.read_bytes()
                xlsx_blob_url = upload_to_vercel_blob(
                    xlsx_content,
                    f"maps/{job_id}/{xlsx_filename}",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                logger.info(f"Uploaded XLSX to blob: {xlsx_blob_url}")
        except Exception as blob_error:
            # Log but don't fail - map will work without report links
            logger.warning(f"Report blob upload failed (non-fatal): {blob_error}")

        # Create web map with blob URLs for PDF/XLSX links
        map_obj = create_web_map(
            polygon_gdf, layer_results, metadata, config, input_layer_name,
            project_name=project_name,
            xlsx_relative_path=xlsx_blob_url,  # Use blob URL instead of filename
            pdf_relative_path=pdf_blob_url,    # Use blob URL instead of filename
            clip_boundary=clip_boundary
        )

        # Save map HTML
        map_file = temp_output / "index.html"
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

        logger.info(f"Job {job_id} completed successfully")

        # Update job record with completion status
        if supabase:
            try:
                supabase.table('jobs').update({
                    'status': 'complete',
                    'completed_at': datetime.now().isoformat(),
                    'total_features': summary["total_features"],
                    'layers_with_data': summary["layers_with_data"],
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

    def check_rate_limit(ip: str) -> bool:
        """Check if IP has exceeded daily rate limit."""
        key = f"{ip}:{datetime.now().strftime('%Y-%m-%d')}"
        try:
            count = rate_limit_dict.get(key, 0)
            if count >= MAX_RUNS_PER_DAY:
                return False
            rate_limit_dict[key] = count + 1
            return True
        except Exception:
            # If Dict is unavailable, allow the request
            return True

    def get_remaining_runs(ip: str) -> int:
        """Get remaining runs for today."""
        key = f"{ip}:{datetime.now().strftime('%Y-%m-%d')}"
        try:
            count = rate_limit_dict.get(key, 0)
            return max(0, MAX_RUNS_PER_DAY - count)
        except Exception:
            return MAX_RUNS_PER_DAY

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

    @web_app.get("/api/rate-limit")
    async def get_rate_limit_endpoint(request: Request):
        """Get rate limit status for the requesting IP."""
        client_ip = request.client.host if request.client else "unknown"
        remaining = get_remaining_runs(client_ip)
        global_remaining = get_global_remaining_runs()
        return {
            "remaining_runs": remaining,
            "max_runs_per_day": MAX_RUNS_PER_DAY,
            "global_remaining_runs": global_remaining,
            "max_global_runs_per_day": MAX_GLOBAL_RUNS_PER_DAY,
            "resets_at": "midnight UTC",
        }

    @web_app.post("/api/process")
    async def process_endpoint(
        request: Request,
        file: UploadFile = File(...),
        user_id: str = Form(None),
        project_name: str = Form(""),
        project_id: str = Form(""),
        buffer_distance_feet: int = Form(500),
        clip_buffer_miles: float = Form(1.0),
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

        # Per-IP rate limit check
        if not check_rate_limit(client_ip):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {MAX_RUNS_PER_DAY} runs per day. Please try again tomorrow.",
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

        def get_progress_message(progress: int) -> str:
            """Get appropriate progress message based on progress percentage."""
            if progress <= 15:
                return "Processing input geometry..."
            elif progress <= 40:
                return "Querying environmental layers..."
            elif progress <= 70:
                return "Processing layer results..."
            elif progress <= 85:
                return "Generating interactive map..."
            else:
                return "Generating reports..."

        async def event_generator() -> AsyncGenerator[str, None]:
            """Generate SSE events for progress updates."""

            # Send initial event
            yield f"data: {json.dumps({'stage': 'upload', 'message': 'File received, starting processing...', 'progress': 5, 'job_id': job_id})}\n\n"

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

                # Poll for completion with realistic progress updates
                progress = 5
                poll_interval = 3  # seconds between updates
                max_progress = 95  # Don't exceed this until actually complete

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
                    except TimeoutError:
                        # Task still running - increment progress slowly
                        if progress < max_progress:
                            progress = min(progress + 5, max_progress)
                            message = get_progress_message(progress)
                            yield f"data: {json.dumps({'stage': 'processing', 'message': message, 'progress': progress})}\n\n"

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
