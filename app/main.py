"""
OMI Global Productions - FastAPI Application
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Load environment variables from .env.development file
env_file = Path(__file__).resolve().parent.parent / ".env.development"
if env_file.exists():
    load_dotenv(env_file)
    print(f"✓ Loaded environment from {env_file}")
else:
    # Fallback to .env if .env.development doesn't exist
    fallback_env = Path(__file__).resolve().parent.parent / ".env"
    if fallback_env.exists():
        load_dotenv(fallback_env)
        print(f"✓ Loaded environment from {fallback_env}")

from app.database import db


class ProjectSubmission(BaseModel):
    """Project submission form data."""
    # Contact Information (required)
    contact_name: str
    contact_email: str
    contact_phone: str
    # Project details (optional)
    title: Optional[str] = None
    logline: Optional[str] = None
    synopsis: Optional[str] = None
    treatment: Optional[str] = None
    moodboard: Optional[str] = None
    soundtracks: Optional[str] = None
    writer_bio: Optional[str] = None
    actor_1: Optional[str] = None
    actor_2: Optional[str] = None
    actor_3: Optional[str] = None
    actor_4: Optional[str] = None
    actor_5: Optional[str] = None
    actor_6: Optional[str] = None
    budget: Optional[float] = None
    languages: Optional[str] = None
    previous_works: Optional[str] = None
    terms: Optional[str] = None


# Application paths
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    print("🚀 Starting OMI Global Productions API...")
    try:
        db.initialize_pool()
    except Exception as e:
        print(f"⚠️  Database connection failed: {e}")
        print("   Application will run without database connectivity.")
    
    yield
    
    # Shutdown
    print("👋 Shutting down OMI Global Productions API...")
    db.close_pool()


# Create FastAPI application
app = FastAPI(
    title="OMI Global Productions",
    description="A creative hub dedicated to storytelling, wellness, and sustainability.",
    version="1.0.0",
    lifespan=lifespan,
)


# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# Setup Jinja2 templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main landing page."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    db_status = "connected"
    try:
        db.fetch_one("SELECT 1")
    except Exception:
        db_status = "disconnected"
    
    return {
        "status": "healthy",
        "database": db_status,
    }


@app.get("/api/v1/pillars")
async def get_pillars():
    """API endpoint returning the three pillars of OMI."""
    return {
        "pillars": [
            {
                "id": "storytelling",
                "title": "Storytelling",
                "icon": "movie",
                "description": "Narratives that move the soul and challenge the conventional boundaries of digital media.",
            },
            {
                "id": "wellness",
                "title": "Wellness",
                "icon": "spa",
                "description": "Holistic practices and environments designed to nourish the mind and restore inner balance.",
            },
            {
                "id": "sustainability",
                "title": "Sustainability",
                "icon": "eco",
                "description": "Building a greener future by integrating nature directly into our creative workflows.",
            },
        ]
    }


@app.post("/api/v1/contact")
async def submit_project(submission: ProjectSubmission):
    """Handle project submission from the contact form."""
    # Collect actor recommendations into a list for response
    actors = [
        submission.actor_1,
        submission.actor_2,
        submission.actor_3,
        submission.actor_4,
        submission.actor_5,
        submission.actor_6,
    ]
    actors = [a for a in actors if a]  # Filter out empty values
    
    # Try to save to database if connected
    submission_id = None
    db_saved = False
    
    try:
        # Insert into project_submissions table with all form fields
        result = db.fetch_one(
            """
            INSERT INTO project_submissions (
                contact_name,
                contact_email,
                contact_phone,
                title,
                logline,
                synopsis,
                treatment_url,
                moodboard_url,
                soundtracks,
                writer_bio,
                actor_1,
                actor_2,
                actor_3,
                actor_4,
                actor_5,
                actor_6,
                budget,
                languages,
                previous_works,
                terms_accepted,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id
            """,
            (
                submission.contact_name,
                submission.contact_email,
                submission.contact_phone,
                submission.title,
                submission.logline,
                submission.synopsis,
                submission.treatment,
                submission.moodboard,
                submission.soundtracks,
                submission.writer_bio,
                submission.actor_1,
                submission.actor_2,
                submission.actor_3,
                submission.actor_4,
                submission.actor_5,
                submission.actor_6,
                submission.budget,
                submission.languages,
                submission.previous_works,
                submission.terms == "on" or submission.terms == True,
                datetime.utcnow(),
            ),
        )
        if result:
            submission_id = str(result["id"])
            db_saved = True
    except Exception as e:
        # Log error but don't fail - database might not be connected
        print(f"Database save failed: {e}")
    
    return {
        "success": True,
        "message": "Project submitted successfully",
        "submission_id": submission_id,
        "db_saved": db_saved,
        "data": {
            "title": submission.title,
            "logline": submission.logline,
            "actors": actors,
            "budget": submission.budget,
        }
    }


@app.get("/api/v1/submissions")
async def get_submissions():
    """Get all project submissions (for admin purposes)."""
    try:
        submissions = db.fetch_all(
            """
            SELECT 
                id,
                contact_name,
                contact_email,
                contact_phone,
                title,
                logline,
                synopsis,
                treatment_url,
                moodboard_url,
                soundtracks,
                writer_bio,
                actor_1,
                actor_2,
                actor_3,
                actor_4,
                actor_5,
                actor_6,
                budget,
                languages,
                previous_works,
                terms_accepted,
                status,
                created_at,
                updated_at,
                reviewed_at,
                reviewed_by
            FROM project_submissions
            ORDER BY created_at DESC
            """
        )
        return {"success": True, "submissions": submissions}
    except Exception as e:
        print(f"Failed to fetch submissions: {e}")
        return {"success": False, "error": str(e), "submissions": []}


@app.get("/api/v1/submissions/{submission_id}")
async def get_submission(submission_id: str):
    """Get a specific project submission by ID."""
    try:
        submission = db.fetch_one(
            """
            SELECT 
                id,
                contact_name,
                contact_email,
                contact_phone,
                title,
                logline,
                synopsis,
                treatment_url,
                moodboard_url,
                soundtracks,
                writer_bio,
                actor_1,
                actor_2,
                actor_3,
                actor_4,
                actor_5,
                actor_6,
                budget,
                languages,
                previous_works,
                terms_accepted,
                status,
                created_at,
                updated_at,
                reviewed_at,
                reviewed_by
            FROM project_submissions
            WHERE id = %s
            """,
            (submission_id,)
        )
        if submission:
            return {"success": True, "submission": submission}
        return {"success": False, "error": "Submission not found"}
    except Exception as e:
        print(f"Failed to fetch submission: {e}")
        return {"success": False, "error": str(e)}


@app.patch("/api/v1/submissions/{submission_id}/status")
async def update_submission_status(submission_id: str, status: str, reviewed_by: Optional[str] = None):
    """Update the status of a project submission."""
    valid_statuses = ["pending", "reviewed", "approved", "rejected"]
    if status not in valid_statuses:
        return {"success": False, "error": f"Invalid status. Must be one of: {valid_statuses}"}
    
    try:
        result = db.fetch_one(
            """
            UPDATE project_submissions
            SET status = %s,
                updated_at = %s,
                reviewed_at = %s,
                reviewed_by = %s
            WHERE id = %s
            RETURNING id
            """,
            (status, datetime.utcnow(), datetime.utcnow(), reviewed_by, submission_id)
        )
        if result:
            return {"success": True, "message": f"Status updated to {status}"}
        return {"success": False, "error": "Submission not found"}
    except Exception as e:
        print(f"Failed to update submission status: {e}")
        return {"success": False, "error": str(e)}


@app.delete("/api/v1/submissions/{submission_id}")
async def delete_submission(submission_id: str):
    """Delete a project submission."""
    try:
        result = db.fetch_one(
            """
            DELETE FROM project_submissions
            WHERE id = %s
            RETURNING id
            """,
            (submission_id,)
        )
        if result:
            return {"success": True, "message": "Submission deleted"}
        return {"success": False, "error": "Submission not found"}
    except Exception as e:
        print(f"Failed to delete submission: {e}")
        return {"success": False, "error": str(e)}
