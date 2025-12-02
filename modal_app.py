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

# Create Modal app
app = modal.App("peit-processor")

# Modal Dict for rate limiting
rate_limit_dict = modal.Dict.from_name("peit-rate-limits", create_if_missing=True)
MAX_RUNS_PER_DAY = 20

# Modal Volume for storing results temporarily
results_volume = modal.Volume.from_name("peit-results", create_if_missing=True)

# Define the container image with geospatial dependencies
peit_image = (
    modal.Image.micromamba()
    .micromamba_install(
        "gdal>=3.8",
        "geos>=3.12",
        "proj>=9.3",
        "fiona>=1.9",
        "pyproj>=3.6",
        "shapely>=2.0",
        "geopandas>=0.14",
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
    )
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


@app.function(image=peit_image, timeout=600, volumes={"/results": results_volume})
def process_file_task(
    file_content: bytes,
    filename: str,
    job_id: str,
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

        input_filename = Path(filename).stem

        # Process all layers
        layer_results, metadata, clip_summary = process_all_layers(polygon_gdf, config)

        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        xlsx_filename = f"PEIT_Report_{timestamp}.xlsx"
        pdf_filename = f"PEIT_Report_{timestamp}.pdf"

        # Create web map
        map_obj = create_web_map(
            polygon_gdf, layer_results, metadata, config, input_filename,
            xlsx_relative_path=xlsx_filename,
            pdf_relative_path=pdf_filename
        )

        # Generate output (temporarily to local temp)
        output_name = f"peit_map_{timestamp}"
        temp_output = temp_dir / output_name
        temp_output.mkdir(parents=True, exist_ok=True)

        # Manually save outputs to temp location
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

        # Generate reports
        from utils.xlsx_generator import generate_xlsx_report
        from utils.pdf_generator import generate_pdf_report

        generate_xlsx_report(layer_results, config, temp_output, timestamp, project_name, project_id)
        generate_pdf_report(layer_results, config, temp_output, timestamp, project_name, project_id)

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

        logger.info(f"Job {job_id} completed successfully")

        return {
            "success": True,
            "job_id": job_id,
            "zip_filename": zip_filename,
            "total_features": summary["total_features"],
            "layers_with_data": summary["layers_with_data"],
        }

    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
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
    volumes={"/results": results_volume},
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

    web_app = FastAPI(title="PEIT Processor API")

    # Add CORS middleware for frontend access
    web_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, restrict to your domain
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

    @web_app.get("/api/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": "peit-processor"}

    @web_app.get("/api/rate-limit")
    async def get_rate_limit_endpoint(request: Request):
        """Get rate limit status for the requesting IP."""
        client_ip = request.client.host if request.client else "unknown"
        remaining = get_remaining_runs(client_ip)
        return {
            "remaining_runs": remaining,
            "max_runs_per_day": MAX_RUNS_PER_DAY,
            "resets_at": "midnight UTC",
        }

    @web_app.post("/api/process")
    async def process_endpoint(
        request: Request,
        file: UploadFile = File(...),
        project_name: str = Form(""),
        project_id: str = Form(""),
        buffer_distance_feet: int = Form(500),
        clip_buffer_miles: float = Form(1.0),
    ):
        """
        Process a geospatial file and stream progress via SSE.

        Returns Server-Sent Events with progress updates, then final result.
        """
        # Rate limit check
        client_ip = request.client.host if request.client else "unknown"
        if not check_rate_limit(client_ip):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {MAX_RUNS_PER_DAY} runs per day. Please try again tomorrow.",
                    "remaining_runs": 0,
                }
            )

        # Validate file
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

        # Generate job ID
        job_id = str(uuid.uuid4())[:8]

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
                        # Task completed!
                        if result["success"]:
                            yield f"data: {json.dumps({'stage': 'complete', 'message': 'Processing complete!', 'progress': 100, 'job_id': job_id, 'download_url': f'/api/download/{job_id}'})}\n\n"
                        else:
                            yield f"data: {json.dumps({'stage': 'error', 'message': result.get('error', 'Unknown error'), 'progress': 0, 'error': result.get('error')})}\n\n"
                        break
                    except TimeoutError:
                        # Task still running - increment progress slowly
                        if progress < max_progress:
                            progress = min(progress + 5, max_progress)
                            message = get_progress_message(progress)
                            yield f"data: {json.dumps({'stage': 'processing', 'message': message, 'progress': progress})}\n\n"

            except Exception as e:
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

    return web_app


# Entry point for modal serve/deploy
if __name__ == "__main__":
    print("Use 'modal serve modal_app.py' for development")
    print("Use 'modal deploy modal_app.py' for production")
