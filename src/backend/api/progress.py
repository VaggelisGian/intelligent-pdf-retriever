from fastapi import APIRouter
from typing import Dict, Any
import time
import redis
import json
import os
import datetime
import asyncio  # Added import for async functionality
from src.backend.api.websocket import broadcast_progress

# Create router
router = APIRouter()

# Standardize Redis client initialization
redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
try:
    # Add timeouts to prevent hanging
    redis_client = redis.Redis.from_url(
        redis_url,
        socket_connect_timeout=5,
        socket_timeout=5,
        decode_responses=True  # Added decode_responses for proper string handling
    )
    redis_client.ping()
    print(f"Progress API connected to Redis at: {redis_url}")
except Exception as e:
    print(f"FATAL: Failed to connect to Redis at {redis_url}: {e}")
    redis_client = None

@router.get("/{job_id}")  # Remove the "progress" prefix
async def get_progress(job_id: str):
    """Non-blocking progress endpoint"""
    if not redis_client:
        print(f"ERROR: get_progress called but Redis client is not initialized.")
        return {"job_id": job_id, "status": "error", "message": "Backend Redis connection failed"}

    redis_key = f"job:{job_id}"
    current_dt = datetime.datetime.now().isoformat()
    print(f"[{current_dt}] GET /progress/{job_id} - Looking for Redis key: {redis_key}")

    try:
        # Check if job exists
        job_data = redis_client.get(redis_key)

        if not job_data:
            print(f"[{current_dt}] Progress request: Key '{redis_key}' not found in Redis.")
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        # Parse the JSON data from Redis
        try:
            job = json.loads(job_data)
            print(f"[{current_dt}] Progress request successful: {job_id} - Status: {job.get('status', 'N/A')}, Page: {job.get('current_page', 0)}/{job.get('total_pages', 0)}")
            return job
        except json.JSONDecodeError as json_err:
            print(f"[{current_dt}] ERROR decoding job data for {job_id}. Data: '{job_data}'. Error: {json_err}")
            return {"job_id": job_id, "status": "error", "message": "Invalid job data in Redis"}

    except redis.exceptions.ConnectionError as e:
        print(f"[{current_dt}] ERROR: Redis ConnectionError in get_progress for {job_id}: {e}")
        return {"job_id": job_id, "status": "error", "message": f"Redis connection error: {e}"}
    except Exception as e:
        print(f"[{current_dt}] ERROR: Unexpected error in get_progress for {job_id}: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {"job_id": job_id, "status": "error", "message": f"Internal server error: {type(e).__name__}"}

# --- Functions called by background task ---

def create_job(job_id: str, filename: str, total_pages: int) -> None:
    """Initialize a job in Redis"""
    if not redis_client:
        print(f"ERROR: create_job called but Redis client is not initialized.")
        return
    try:
        job = {
            "job_id": job_id,
            "filename": filename,
            "current_page": 0,
            "total_pages": total_pages,
            "percent_complete": 0,
            "status": "processing",
            "message": "Starting PDF extraction..."
        }
        # Store in Redis (expire after 24 hours for active jobs)
        redis_client.setex(f"job:{job_id}", 86400, json.dumps(job))
        print(f"Created job: {job_id} for file {filename} with {total_pages} pages")
    except Exception as e:
        print(f"ERROR in create_job: {type(e).__name__}: {e}")

async def update_job_progress(job_id: str, current_page: int) -> None:
    """Update progress for a job and broadcast via WebSocket"""
    if not redis_client:
        print(f"ERROR: update_job_progress called but Redis client is not initialized.")
        return
    try:
        redis_key = f"job:{job_id}"
        job_data = redis_client.get(redis_key)

        if job_data:
            try:
                job = json.loads(job_data)
                # Update progress only if still in the 'processing' phase
                if job.get("status") == "processing":
                    job["current_page"] = current_page
                    
                    # Calculate percentage (0-55% range for extraction phase)
                    if current_page > 0 and job["total_pages"] > 0:
                        raw_percent = (current_page / job["total_pages"]) * 55
                        job["percent_complete"] = max(1, int(raw_percent))
                    else:
                        job["percent_complete"] = 0
                        
                    job["message"] = f"Extracting page {current_page} of {job['total_pages']}"

                    # Update in Redis
                    redis_client.setex(redis_key, 86400, json.dumps(job))
                    
                    # Broadcast update via WebSocket
                    await broadcast_progress(job_id, job)

                    # Log less frequently
                    if current_page % max(1, job["total_pages"] // 20) == 0 or current_page == job["total_pages"]:
                        print(f"PDF Extract Progress: {job_id} - Page {current_page}/{job['total_pages']} (Overall: {job['percent_complete']}%)")
            except Exception as e:
                print(f"ERROR in update_job_progress logic: {type(e).__name__}: {e}")
    except Exception as e:
        print(f"ERROR in update_job_progress connection/retrieval: {type(e).__name__}: {e}")

def complete_job_sync(job_id: str, message: str = "Processing complete", final_status: str = "completed") -> None:
    """Non-async version of complete_job for use in non-async contexts"""
    if not redis_client:
        print(f"ERROR: complete_job_sync called but Redis client is not initialized.")
        return
    try:
        redis_key = f"job:{job_id}"
        job_data = redis_client.get(redis_key)
        job = {}

        if job_data:
            try:
                job = json.loads(job_data)
            except json.JSONDecodeError as e:
                print(f"ERROR: Could not parse existing job data: {e}")

        # Update job fields for final status
        job["job_id"] = job_id
        job["status"] = final_status
        job["message"] = message
        if final_status == "completed":
            job["percent_complete"] = 100
            if "total_pages" in job:
                job["current_page"] = job["total_pages"]
        else:
            job["percent_complete"] = job.get("percent_complete", 0)

        # Store in Redis
        redis_client.set(redis_key, json.dumps(job))
        
        # Note: We cannot broadcast WebSocket updates here since it's not async
        # Clients will pick up the status on their next poll
        
        completion_dt = datetime.datetime.now().isoformat()
        print(f"[{completion_dt}] Finalized job (sync): {job_id} with status '{final_status}' - {message}")

    except Exception as e:
        error_dt = datetime.datetime.now().isoformat()
        print(f"[{error_dt}] ERROR in complete_job_sync for {job_id}: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

async def complete_job(job_id: str, message: str = "Processing complete", final_status: str = "completed") -> None:
    """Mark a job as complete or failed and broadcast the final status"""
    if not redis_client:
        print(f"ERROR: complete_job called but Redis client is not initialized.")
        return
    try:
        redis_key = f"job:{job_id}"
        job_data = redis_client.get(redis_key)
        job = {}

        if job_data:
            try:
                job = json.loads(job_data)
            except json.JSONDecodeError as e:
                print(f"ERROR: Could not parse existing job data in complete_job: {e}. Data: {job_data}")

        # Update job fields for final status
        job["job_id"] = job_id
        job["status"] = final_status
        job["message"] = message
        if final_status == "completed":
            job["percent_complete"] = 100
            if "total_pages" in job:
                job["current_page"] = job["total_pages"]
        else:
            job["percent_complete"] = job.get("percent_complete", 0)

        # Store in Redis
        redis_client.set(redis_key, json.dumps(job))
        
        # Broadcast final status via WebSocket
        await broadcast_progress(job_id, job)
        
        completion_dt = datetime.datetime.now().isoformat()
        print(f"[{completion_dt}] Finalized job: {job_id} with status '{final_status}' - {message}")

        # Verification
        time.sleep(0.1)
        verification = redis_client.get(redis_key)
        verify_dt = datetime.datetime.now().isoformat()
        if verification:
            print(f"[{verify_dt}] ✓ Verified final job data stored in Redis for key: {redis_key}")
        else:
            print(f"[{verify_dt}] ❌ ERROR: Final job data NOT found in Redis after setting! Key: {redis_key}")

    except Exception as e:
        error_dt = datetime.datetime.now().isoformat()
        print(f"[{error_dt}] ERROR in complete_job for {job_id}: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()