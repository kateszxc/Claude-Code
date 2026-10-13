"""FastAPI server used by the Next.js interface."""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import llm
from .config import settings
from .models import NICHES, JobState, ScrapeRequest
from .pipeline import run_job, write_csv

app = FastAPI(title="E-com Brand Scraper", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

JOBS: dict[str, JobState] = {}
_TASKS: dict[str, asyncio.Task] = {}


@app.get("/api/health")
async def health():
    return {"ok": True}


@app.get("/api/options")
async def options():
    return {
        "niches": [{"id": k, "label": v["label"]} for k, v in NICHES.items()],
        "providers": {
            "search": settings.search_provider,
            "hunter": bool(settings.hunter_api_key),
            "ai": llm.enabled(),
        },
    }


@app.post("/api/jobs")
async def create_job(req: ScrapeRequest):
    if any(j.status == "running" for j in JOBS.values()):
        raise HTTPException(409, "A scrape is already running – wait for it or cancel it first.")
    job = JobState(id=uuid.uuid4().hex, request=req)
    JOBS[job.id] = job
    _TASKS[job.id] = asyncio.create_task(run_job(job))
    return {"id": job.id}


@app.get("/api/jobs")
async def list_jobs():
    return [
        {"id": j.id, "status": j.status, "niche": j.request.niche_label, "found": j.found,
         "count": j.request.count, "created_at": j.created_at}
        for j in sorted(JOBS.values(), key=lambda j: j.created_at, reverse=True)
    ]


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str, log_tail: int = 60):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    data = job.model_dump(exclude={"logs"})
    data["logs"] = job.logs[-log_tail:]
    return data


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status == "running":
        job.status = "cancelled"
    return {"status": job.status}


@app.get("/api/jobs/{job_id}/csv")
async def download_csv(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status == "running" or not job.csv_path:
        # Partial download while the scrape is still going
        path = write_csv(list(job.results), settings.output_dir / f"partial-{job.id[:6]}.csv")
    else:
        path = Path(job.csv_path)
    return FileResponse(path, media_type="text/csv", filename=path.name)
