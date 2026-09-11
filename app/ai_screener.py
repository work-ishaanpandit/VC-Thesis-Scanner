import os
import json
import httpx
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

# Optional import for openai SDK if available
try:
    from openai import AsyncOpenAI
    HAS_OPENAI_SDK = True
except ImportError:
    HAS_OPENAI_SDK = False


# Pydantic Schema for Structured Output Validation
class ScoreItem(BaseModel):
    criterion: str
    score: int = Field(description="Score between 1 and 5")
    reason: str

class ScreeningResponse(BaseModel):
    executive_summary: str
    scorecard: list[ScoreItem]
    why_it_fits: str
    investment_positives: list[str]
    risks_red_flags: list[str]
    key_unknowns: list[str]
    founder_questions: list[str]
    recommendation: str = Field(description="Must be exactly one of: PASS, WATCH, INVESTIGATE, HIGH PRIORITY")
    recommendation_reason: str
    fact_breakdown: Dict[str, list[str]] = Field(
        default_factory=dict,
        description="Keys: verified_facts, company_claims, inferences, unknown_information"
    )

INVESTMENT_THESIS_PROMPT = """
You are a senior Venture Capital Investment Principal specializing in Industrial Robotics and Physical AI across Germany and Western Europe.

Your Investment Thesis:
"I am building my edge by becoming a specialist in industrial robotics and Physical AI across Germany and Western Europe, focusing on pre-seed and seed startups building the enabling technologies for industrial automation."

Core Focus Areas:
- Industrial robotics
- Physical AI
- Machine vision
- Robot perception
- Robot manipulation
- Simulation and sim-to-real
- Industrial automation
- Robotics software
- Autonomous systems
- Technologies enabling industrial automation
- Humanoid robotics where there is a credible industrial application

Target Geography:
- Germany
- Netherlands
- Broader Western Europe

Target Stage:
- Pre-seed
- Seed

Founder Preference:
- Technical founders with strong engineering capability
- High founder-market fit
- Ability to build difficult hardware/software systems
- Deep understanding of underlying industrial manufacturing/logistics problems

CRITICAL OPERATIONAL RULES:
1. BE SKEPTICAL: Do NOT give a positive score merely because a company buzzes about "AI" or "robotics".
2. NO INVENTION: Never invent funding rounds, revenue numbers, customer logos, team backgrounds, technical specs, or market sizing if not explicitly provided in the input or web research.
3. DISTINGUISH EVIDENCE:
   - Verified facts (supported by external/direct evidence)
   - Company claims (uncorroborated assertions by founders)
   - Inferences (logical deductions based on available data)
   - Unknown information (gaps where evidence is missing)
4. STRICT SCORING (1 to 5 scale):
   - Thesis Fit
   - Geography Fit
   - Stage Fit
   - Founder/Technical Fit
   - Market Attractiveness
   - Defensibility
   - Commercial Traction
   Score strictly! Unknowns or missing data should lower the score (e.g. 1 or 2 for Commercial Traction if unverified).
5. RECOMMENDATION: Must select EXACTLY ONE of: PASS, WATCH, INVESTIGATE, HIGH PRIORITY.
"""

async def run_investment_screen(
    startup_name: str,
    startup_website: str,
    additional_notes: str,
    web_research_data: Dict[str, Any],
    api_key_override: Optional[str] = None,
    provider_override: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes AI investment screening against the VC thesis.
    Defaults to Google Gemini (free tier gemini-3.6-flash via GEMINI_API_KEY).
    Falls back to OpenAI or Offline Demo Mode if no key is configured.
    """
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    api_key = api_key_override or gemini_key or openai_key

    provider = provider_override
    if not provider:
        if api_key_override:
            if api_key_override.startswith("AIza") or len(api_key_override) > 20 and not api_key_override.startswith("sk-"):
                provider = "gemini"
            elif api_key_override.startswith("sk-"):
                provider = "openai"
            else:
                provider = "gemini"
        elif gemini_key:
            provider = "gemini"
        elif openai_key:
            provider = "openai"
        else:
            provider = "offline"

    web_text = web_research_data.get("extracted_text", "")
    sources = []
    if startup_website:
        sources.append(web_research_data.get("url") or startup_website)
    if additional_notes:
        sources.append("User Provided Pitch Notes & Details")

    if not api_key or provider == "offline":
        return run_offline_mock_screen(
            startup_name=startup_name,
            startup_website=startup_website,
            additional_notes=additional_notes,
            web_research_data=web_research_data,
            sources=sources
        )

    user_content = f"""
STARTUP SCREENING REQUEST:
- Startup Name: {startup_name}
- Startup Website: {startup_website}

RESEARCH & WEBSITE EXTRACTED CONTENT:
{web_text if web_text else "No direct website content available."}

ADDITIONAL COMPANY NOTES & FOUNDER INFO:
{additional_notes if additional_notes else "No additional notes provided."}

Please conduct a structured first-pass investment screening adhering strictly to your VC thesis instructions.
Return the output formatted strictly according to the required JSON schema.
"""

    if provider == "gemini":
        try:
            res = await call_gemini_provider(api_key, user_content)
            res["sources"] = sources
            res["is_offline_fallback"] = False
            res["provider_used"] = f"Google Gemini ({os.getenv('GEMINI_MODEL', 'gemini-3.6-flash')})"
            return res
        except Exception as e:
            fallback = run_offline_mock_screen(startup_name, startup_website, additional_notes, web_research_data, sources)
            fallback["api_error_warning"] = f"Gemini API error: {str(e)}. Switched to offline backup screener."
            return fallback

    elif provider == "openai" and HAS_OPENAI_SDK:
        try:
            res = await call_openai_provider(api_key, user_content)
            res["sources"] = sources
            res["is_offline_fallback"] = False
            res["provider_used"] = f"OpenAI ({os.getenv('OPENAI_MODEL', 'gpt-4o-mini')})"
            return res
        except Exception as e:
            fallback = run_offline_mock_screen(startup_name, startup_website, additional_notes, web_research_data, sources)
            fallback["api_error_warning"] = f"OpenAI API error: {str(e)}. Switched to offline backup screener."
            return fallback

    else:
        return run_offline_mock_screen(startup_name, startup_website, additional_notes, web_research_data, sources)


async def call_gemini_provider(api_key: str, user_content: str) -> Dict[str, Any]:
    """
    Calls Google Gemini API using direct REST API endpoint for 100% clean JSON output.
    Uses free-tier model 'gemini-3.6-flash'.
    """
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    json_instruction = """
IMPORTANT: Output MUST be a single valid JSON object strictly matching this schema:
{
  "executive_summary": "Detailed summary of startup and investment case",
  "scorecard": [
    {"criterion": "Thesis Fit", "score": 4, "reason": "Explanation"},
    {"criterion": "Geography Fit", "score": 5, "reason": "Explanation"},
    {"criterion": "Stage Fit", "score": 4, "reason": "Explanation"},
    {"criterion": "Founder/Technical Fit", "score": 4, "reason": "Explanation"},
    {"criterion": "Market Attractiveness", "score": 4, "reason": "Explanation"},
    {"criterion": "Defensibility", "score": 4, "reason": "Explanation"},
    {"criterion": "Commercial Traction", "score": 2, "reason": "Explanation"}
  ],
  "why_it_fits": "Specific reasons this startup matches the thesis",
  "investment_positives": ["Positive 1", "Positive 2", "Positive 3"],
  "risks_red_flags": ["Risk 1", "Risk 2", "Risk 3"],
  "key_unknowns": ["Unknown 1", "Unknown 2", "Unknown 3"],
  "founder_questions": ["Question 1", "Question 2", "Question 3", "Question 4", "Question 5"],
  "recommendation": "HIGH PRIORITY",
  "recommendation_reason": "Brief explanation of recommendation",
  "fact_breakdown": {
    "verified_facts": ["Fact 1"],
    "company_claims": ["Claim 1"],
    "inferences": ["Inference 1"],
    "unknown_information": ["Unknown 1"]
  }
}
Recommendation MUST be exactly one of: PASS, WATCH, INVESTIGATE, HIGH PRIORITY.
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": INVESTMENT_THESIS_PROMPT + "\n" + json_instruction}]},
        "contents": [{"parts": [{"text": user_content}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code >= 400:
            raise Exception(f"Gemini API returned HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        text_out = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text_out)


async def call_openai_provider(api_key: str, user_content: str) -> Dict[str, Any]:
    """Calls OpenAI API using AsyncOpenAI structured outputs."""
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = AsyncOpenAI(api_key=api_key)
    completion = await client.beta.chat.completions.parse(
        model=model_name,
        messages=[
            {"role": "system", "content": INVESTMENT_THESIS_PROMPT},
            {"role": "user", "content": user_content}
        ],
        response_format=ScreeningResponse,
        temperature=0.2
    )
    parsed_data: ScreeningResponse = completion.choices[0].message.parsed
    return parsed_data.model_dump()


def run_offline_mock_screen(
    startup_name: str,
    startup_website: str,
    additional_notes: str,
    web_research_data: Dict[str, Any],
    sources: list[str]
) -> Dict[str, Any]:
    """
    Deterministic analytical fallback screener for offline evaluation & testing.
    Analyzes keywords in name, website text, and pitch notes against thesis rules.
    Requires ZERO API keys or credits.
    """
    combined_input = f"{startup_name} {startup_website} {additional_notes} {web_research_data.get('extracted_text', '')}".lower()

    robotics_keywords = ["robot", "robotics", "physical ai", "perception", "manipulation", "sim-to-real", "vision", "automation", "humanoid", "actuator", "ros", "gripper", "kinematics", "autonomous"]
    is_robotics = any(k in combined_input for k in robotics_keywords)

    geo_keywords = ["germany", "munich", "berlin", "stuttgart", "netherlands", "amsterdam", "delft", "eindhoven", "europe", "western europe", "de", "nl", "gmbh"]
    is_geo_fit = any(k in combined_input for k in geo_keywords)

    stage_keywords = ["pre-seed", "seed", "early stage", "stealth", "prototype"]
    is_stage_fit = any(k in combined_input for k in stage_keywords) or ("series a" not in combined_input and "series b" not in combined_input)

    tech_founder_keywords = ["phd", "engineer", "tum", "eth", "rwth", "cto", "robotics engineer", "mechanics", "software engineer", "technical founder"]
    has_tech_founder = any(k in combined_input for k in tech_founder_keywords)

    thesis_score = 4 if is_robotics else 2
    geo_score = 5 if is_geo_fit else 3
    stage_score = 4 if is_stage_fit else 2
    founder_score = 4 if has_tech_founder else 3
    market_score = 4 if is_robotics else 3
    defensibility_score = 4 if ("hardware" in combined_input or "patent" in combined_input or "sim-to-real" in combined_input or "perception" in combined_input) else 2
    traction_score = 2

    avg_score = (thesis_score + geo_score + stage_score + founder_score + market_score + defensibility_score + traction_score) / 7.0

    if avg_score >= 3.8 and thesis_score >= 4:
        recommendation = "HIGH PRIORITY"
        rec_reason = f"{startup_name} aligns strongly with the Industrial Robotics & Physical AI thesis with favorable geographic and technical alignment."
    elif avg_score >= 3.2:
        recommendation = "INVESTIGATE"
        rec_reason = f"{startup_name} shows promising thesis alignment; requires deeper technical audit of core claims and founder traction."
    elif is_robotics:
        recommendation = "WATCH"
        rec_reason = f"Relevant domain focus, but key information regarding stage, technical defensibility, or founder background remains unverified."
    else:
        recommendation = "PASS"
        rec_reason = f"Low thesis fit. The company does not demonstrate clear alignment with industrial automation or enabling Physical AI technologies."

    scorecard = [
        {"criterion": "Thesis Fit", "score": thesis_score, "reason": "High relevance to industrial automation/robotics focus" if is_robotics else "Limited alignment with core Physical AI & robotics thesis"},
        {"criterion": "Geography Fit", "score": geo_score, "reason": "Based in target Western European hub (Germany/NL)" if is_geo_fit else "Location unspecified or outside core DACH/Western Europe focus"},
        {"criterion": "Stage Fit", "score": stage_score, "reason": "Appears to be in target Pre-Seed/Seed investment stage" if is_stage_fit else "Stage unconfirmed or later stage"},
        {"criterion": "Founder/Technical Fit", "score": founder_score, "reason": "Evidence of technical engineering background" if has_tech_founder else "Founder technical depth and industrial problem fit need validation"},
        {"criterion": "Market Attractiveness", "score": market_score, "reason": "Industrial automation market exhibits high tailwinds for labor substitution" if is_robotics else "Market size & industrial urgency remain unvalidated"},
        {"criterion": "Defensibility", "score": defensibility_score, "reason": "Proprietary software/hardware coupling or sim-to-real pipeline" if defensibility_score >= 4 else "Risk of low defensibility or reliance on off-the-shelf software wrappers"},
        {"criterion": "Commercial Traction", "score": traction_score, "reason": "Early stage company; customer pilots and deployment proof points require verification"}
    ]

    return {
        "executive_summary": f"{startup_name} is being screened against the Industrial Robotics & Physical AI thesis. Initial data suggests a focus on {'industrial automation / robotics software' if is_robotics else 'general technology'}. {"A direct website fetch was completed." if web_research_data.get('success') else "Screening was performed using provided startup inputs."}",
        "scorecard": scorecard,
        "why_it_fits": f"{startup_name} addresses core industrial automation themes within Western Europe. Focus on physical systems and engineering solutions matches thesis priorities." if is_robotics else "Requires further verification to establish clear fit with physical AI enabling technologies.",
        "investment_positives": [
            f"Targets high-value industrial automation sector.",
            f"Geographic focus within Western European industrial ecosystem.",
            f"Potential leverage of software/hardware integration for factory/warehouse efficiency.",
            f"Pre-seed/seed timing allows entry at favorable valuation entry points."
        ],
        "risks_red_flags": [
            "Hardware deployment complexity and long enterprise sales cycles in industrial manufacturing.",
            "Technical risk in sim-to-real transfer and real-world edge condition reliability.",
            "Unverified customer traction or pilot commitments."
        ],
        "key_unknowns": [
            "Exact founding team engineering credentials and equity split.",
            "Current runway, previous funding status, and valuation expectation.",
            "Specific benchmark performance of the core perception/control stack."
        ],
        "founder_questions": [
            "What specific industrial environment or cell type is your system deployed in today?",
            "What is your proprietary IP or defensible technical advantage over existing ROS-based frameworks?",
            "How do you handle edge cases and sim-to-real gap during customer deployments?",
            "What ROI payback period do your initial industrial pilot partners experience?",
            "What is your target seed milestone over the next 12 to 18 months?"
        ],
        "recommendation": recommendation,
        "recommendation_reason": rec_reason,
        "fact_breakdown": {
            "verified_facts": [f"Company Name: {startup_name}", f"Website URL: {startup_website or 'Not provided'}"],
            "company_claims": [c.strip() for c in additional_notes.split('\n') if len(c.strip()) > 10][:3] or ["Claims provided in pitch notes."],
            "inferences": ["Positioned within industrial technology ecosystem based on terminology."],
            "unknown_information": ["Validated ARR / pilot revenues", "Verified customer contract details", "Detailed cap table structure"]
        },
        "sources": sources if sources else ["User Input Data"],
        "is_offline_fallback": True,
        "model_used": "Deterministic Rule Engine (Offline Demo Mode)"
    }
