"""
OMI Global Productions - FastAPI Application
"""

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.database import db


class ProjectSubmission(BaseModel):
    """Project submission form data."""
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
    # Collect actor recommendations into a list
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
    try:
        result = db.fetch_one(
            """
            INSERT INTO contact_submissions (name, email, subject, message, created_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                submission.title or "Untitled Project",
                "",  # Email not collected in this form
                f"Project Submission: {submission.title or 'Untitled'}",
                f"""
                Logline: {submission.logline or 'N/A'}
                Synopsis: {submission.synopsis or 'N/A'}
                Treatment URL: {submission.treatment or 'N/A'}
                Moodboard URL: {submission.moodboard or 'N/A'}
                Soundtrack: {submission.soundtracks or 'N/A'}
                Writer Bio: {submission.writer_bio or 'N/A'}
                Actors: {', '.join(actors) if actors else 'N/A'}
                Budget: ${submission.budget or 0:,.2f}
                Languages: {submission.languages or 'N/A'}
                Previous Works: {submission.previous_works or 'N/A'}
                """,
                datetime.utcnow(),
            ),
        )
        if result:
            submission_id = str(result["id"])
    except Exception as e:
        # Log error but don't fail - database might not be connected
        print(f"Database save failed: {e}")
    
    return {
        "success": True,
        "message": "Project submitted successfully",
        "submission_id": submission_id,
        "data": {
            "title": submission.title,
            "logline": submission.logline,
            "actors": actors,
            "budget": submission.budget,
        }
    }
