import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

from app.web_scraper import fetch_startup_website
from app.ai_screener import run_investment_screen
from app.presets import PRESET_STARTUPS

# Load environment variables
load_dotenv()

app = FastAPI(
    title="VC Thesis Screener",
    description="API server for screening startups against an Industrial Robotics & Physical AI investment thesis.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScreenRequest(BaseModel):
    startup_name: str
    startup_website: Optional[str] = ""
    additional_notes: Optional[str] = ""
    api_key_override: Optional[str] = None
    provider_override: Optional[str] = None

@app.get("/api/health")
async def health_check():
    """Returns status of AI providers and server readiness."""
    has_gemini = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    return {
        "status": "online",
        "gemini_key_configured": has_gemini,
        "openai_key_configured": has_openai,
        "active_provider": "Gemini" if has_gemini else ("OpenAI" if has_openai else "Offline Demo Mode"),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    }

@app.get("/api/presets")
async def get_presets():
    """Returns preset sample startups for quick testing."""
    return {"presets": PRESET_STARTUPS}

@app.post("/api/screen")
async def screen_startup(request: ScreenRequest):
    """
    Main API endpoint:
    1. Validates input.
    2. Scrapes website content if URL provided.
    3. Executes AI investment screening against VC thesis (Gemini, OpenAI, or Offline Fallback).
    """
    startup_name = request.startup_name.strip()
    if not startup_name:
        raise HTTPException(status_code=400, detail="Startup name is required.")

    startup_website = (request.startup_website or "").strip()
    additional_notes = (request.additional_notes or "").strip()

    # Step 1: Web Research / Website fetching
    web_research_data = {"extracted_text": "", "success": False, "summary": "No URL provided."}
    if startup_website:
        web_research_data = await fetch_startup_website(startup_website)

    # Step 2: AI Screening
    screening_result = await run_investment_screen(
        startup_name=startup_name,
        startup_website=startup_website,
        additional_notes=additional_notes,
        web_research_data=web_research_data,
        api_key_override=request.api_key_override,
        provider_override=request.provider_override
    )

    return {
        "success": True,
        "startup_name": startup_name,
        "startup_website": startup_website,
        "web_research": {
            "success": web_research_data.get("success", False),
            "summary": web_research_data.get("summary", ""),
            "title": web_research_data.get("title", "")
        },
        "report": screening_result
    }

# Mount static assets directory
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_homepage():
    """Serves the main application homepage."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>VC Thesis Screener API Server is running. UI not found.</h1>", status_code=404)
