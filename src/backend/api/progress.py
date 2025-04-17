from fastapi import APIRouter, HTTPException
import redis
import json
import os
import datetime
import traceback
import time
# REMOVE: from src.backend.api.websocket import broadcast_progress # Remove WebSocket import
from typing import Optional
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

# Define JobStatus model here if not imported from models.py
from pydantic import BaseModel
class JobStatus(BaseModel):
    job_id: str
    status: str
    message: str
    percent_complete: int = 0
    filename: Optional[str] = None
    current_page: Optional[int] = 0
    total_pages: Optional[int] = 0


@router.get("/{job_id}", response_model=JobStatus)
async def get_progress(job_id: str):
    """Non-blocking progress endpoint"""
    if not redis_client:
        print(f"ERROR: get_progress called but Redis client is not initialized.")
        # Return a valid JobStatus model for error
        raise HTTPException(status_code=503, detail="Backend Redis connection failed")

    redis_key = f"job:{job_id}"
    current_dt = datetime.datetime.now().isoformat()
    # print(f"[{current_dt}] GET /progress/{job_id} - Looking for Redis key: {redis_key}") # Reduce logging noise

    try:
        # Check if job exists
        job_data = redis_client.get(redis_key)

        if not job_data:
            print(f"[{current_dt}] Progress request: Key '{redis_key}' not found in Redis.")
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        # Parse the JSON data from Redis
        try:
            job = json.loads(job_data)
            # print(f"[{current_dt}] Progress request successful: {job_id} - Status: {job.get('status', 'N/A')}, Page: {job.get('current_page', 0)}/{job.get('total_pages', 0)}") # Reduce logging noise
            # Ensure the returned data matches the JobStatus model
            return JobStatus(**job)
        except json.JSONDecodeError as json_err:
            print(f"[{current_dt}] ERROR decoding job data for {job_id}. Data: '{job_data}'. Error: {json_err}")
            raise HTTPException(status_code=500, detail="Invalid job data in Redis")
        except Exception as pydantic_err: # Catch potential Pydantic validation errors
             print(f"[{current_dt}] ERROR validating job data for {job_id}. Data: '{job_data}'. Error: {pydantic_err}")
             raise HTTPException(status_code=500, detail="Job data validation error")


    except redis.exceptions.ConnectionError as e:
        print(f"[{current_dt}] ERROR: Redis ConnectionError in get_progress for {job_id}: {e}")
        raise HTTPException(status_code=503, detail=f"Redis connection error: {e}")
    except HTTPException:
         raise # Re-raise HTTP exceptions
    except Exception as e:
        print(f"[{current_dt}] ERROR: Unexpected error in get_progress for {job_id}: {type(e).__name__}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {type(e).__name__}")

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
            "status": "starting", # Change initial status
            "message": "Initializing..."
        }
        # Store in Redis (expire after 24 hours for active jobs)
        redis_client.setex(f"job:{job_id}", 86400, json.dumps(job))
        print(f"Created job: {job_id} for file {filename} with {total_pages} pages")
    except Exception as e:
        print(f"ERROR in create_job: {type(e).__name__}: {e}")

async def update_job_status(job_id: str, status: str, message: str, percent_complete: Optional[int] = None, current_page: Optional[int] = None) -> None:
    """Update the status, message, and optionally percentage/page of a job."""
    if not redis_client:
        print(f"ERROR: update_job_status called but Redis client is not initialized.")
        return
    try:
        redis_key = f"job:{job_id}"
        job_data = redis_client.get(redis_key)
        if job_data:
            try:
                job = json.loads(job_data)
                job["status"] = status
                job["message"] = message
                if percent_complete is not None:
                    job["percent_complete"] = max(0, min(100, percent_complete))
                if current_page is not None:
                     job["current_page"] = current_page

                # Update in Redis
                redis_client.setex(redis_key, 86400, json.dumps(job))
                # REMOVE: await broadcast_progress(job_id, job) # No longer broadcast
            except Exception as e:
                print(f"ERROR updating job status fields for {job_id}: {e}")
    except Exception as e:
        print(f"ERROR retrieving job for status update {job_id}: {e}")


async def update_job_progress(job_id: str, current_page: int) -> None:
    """Update progress (page count and percentage) for a job"""
    if not redis_client:
        print(f"ERROR: update_job_progress called but Redis client is not initialized.")
        return
    try:
        redis_key = f"job:{job_id}"
        job_data = redis_client.get(redis_key)

        if job_data:
            try:
                job = json.loads(job_data)
                # Update progress only if still in a processing phase
                if job.get("status") not in ["completed", "failed", "error"]:
                    job["current_page"] = current_page
                    percent = 0
                    if job.get("total_pages", 0) > 0:
                         percent = int((current_page / job["total_pages"]) * 100)
                    job["percent_complete"] = max(0, min(100, percent)) # Ensure bounds
                    job["message"] = f"Processing item {current_page} of {job.get('total_pages', '?')}"
                    job["status"] = "processing" # Ensure status reflects activity

                    # Update in Redis
                    redis_client.setex(redis_key, 86400, json.dumps(job))
                    # REMOVE: await broadcast_progress(job_id, job) # No longer broadcast
            except Exception as e:
                print(f"ERROR in update_job_progress logic for {job_id}: {type(e).__name__}: {e}")
    except Exception as e:
        print(f"ERROR in update_job_progress connection/retrieval for {job_id}: {type(e).__name__}: {e}")


async def progress_complete_job(job_id: str, message: str = "Processing complete", final_status: str = "completed") -> None:
    """Mark a job as complete or failed"""
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
        job["job_id"] = job_id # Ensure job_id is present
        job["status"] = final_status
        job["message"] = message
        if final_status == "completed":
            job["percent_complete"] = 100
            # Optionally set current_page to total_pages if meaningful
            if "total_pages" in job:
                 job["current_page"] = job.get("total_pages")
        else:
            # Keep existing percentage on failure, or set to 0 if undefined
            job["percent_complete"] = job.get("percent_complete", 0)

        # Store in Redis - use set instead of setex for final states? Or keep expiry? Keep expiry for now.
        redis_client.setex(redis_key, 86400, json.dumps(job))

        # REMOVE: await broadcast_progress(job_id, job) # No longer broadcast

        completion_dt = datetime.datetime.now().isoformat()
        print(f"[{completion_dt}] Finalized job: {job_id} with status '{final_status}' - {message}")

    except Exception as e:
        error_dt = datetime.datetime.now().isoformat()
        print(f"[{error_dt}] ERROR in complete_job for {job_id}: {type(e).__name__}: {e}")
        traceback.print_exc()

# Keep complete_job_sync if it's used elsewhere (e.g., synchronous parts of error handling)
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
        redis_client.setex(redis_key, 86400, json.dumps(job)) # Keep expiry consistent

        completion_dt = datetime.datetime.now().isoformat()
        print(f"[{completion_dt}] Finalized job (sync): {job_id} with status '{final_status}' - {message}")

    except Exception as e:
        error_dt = datetime.datetime.now().isoformat()
        print(f"[{error_dt}] ERROR in complete_job_sync for {job_id}: {type(e).__name__}: {e}")
        traceback.print_exc()
