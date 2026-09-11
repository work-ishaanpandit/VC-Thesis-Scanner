import os
from fastapi import FastAPI, HTTPException, Request, Response
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

def get_static_dir() -> str:
    """Robustly locate static directory in local dev or Vercel serverless environment."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(base_dir, "static"),
        os.path.join(os.getcwd(), "static"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"),
    ]
    for c in candidates:
        if os.path.exists(c) and os.path.isdir(c):
            return c
    return candidates[0]

static_dir = get_static_dir()
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

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
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
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
    3. Executes AI investment screening against VC thesis.
    """
    startup_name = request.startup_name.strip()
    if not startup_name:
        raise HTTPException(status_code=400, detail="Startup name is required.")

    startup_website = (request.startup_website or "").strip()
    additional_notes = (request.additional_notes or "").strip()

    web_research_data = {"extracted_text": "", "success": False, "summary": "No URL provided."}
    if startup_website:
        web_research_data = await fetch_startup_website(startup_website)

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

@app.get("/static/styles.css")
async def get_styles_fallback():
    """Fallback handler to ensure CSS is always served on Vercel."""
    css_path = os.path.join(get_static_dir(), "styles.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="text/css")
    raise HTTPException(status_code=404, detail="styles.css not found")

@app.get("/static/app.js")
async def get_js_fallback():
    """Fallback handler to ensure JavaScript is always served on Vercel."""
    js_path = os.path.join(get_static_dir(), "app.js")
    if os.path.exists(js_path):
        with open(js_path, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="application/javascript")
    raise HTTPException(status_code=404, detail="app.js not found")

@app.get("/", response_class=HTMLResponse)
async def serve_homepage():
    """Serves the main application homepage."""
    index_path = os.path.join(get_static_dir(), "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>VC Thesis Screener API Server is running. UI not found.</h1>", status_code=404)
