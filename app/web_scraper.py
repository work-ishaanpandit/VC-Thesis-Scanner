import httpx
from bs4 import BeautifulSoup
import re
from typing import Dict, Any

def normalize_url(url: str) -> str:
    """Ensure URL has http/https prefix."""
    url = url.strip()
    if not url:
        return ""
    if not (url.startswith("http://") or url.startswith("https://")):
        return f"https://{url}"
    return url

async def fetch_startup_website(url: str) -> Dict[str, Any]:
    """
    Fetches startup website HTML and extracts structured readable text content.
    Returns dict with success status, extracted content, page title, meta tags, and raw text.
    """
    clean_url = normalize_url(url)
    if not clean_url:
        return {
            "success": False,
            "url": "",
            "error": "No URL provided",
            "title": "",
            "summary": "No website URL provided.",
            "extracted_text": ""
        }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, verify=False) as client:
            response = await client.get(clean_url, headers=headers)
            
            if response.status_code >= 400:
                return {
                    "success": False,
                    "url": clean_url,
                    "error": f"HTTP status {response.status_code}",
                    "title": "",
                    "summary": f"Could not retrieve webpage (HTTP {response.status_code}).",
                    "extracted_text": ""
                }

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove unwanted tags
            for tag in soup(["script", "style", "nav", "footer", "iframe", "svg", "noscript"]):
                tag.decompose()

            # Extract Title
            title = soup.title.string.strip() if soup.title and soup.title.string else ""

            # Extract Meta Description
            meta_desc = ""
            desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
            if desc_tag and desc_tag.get("content"):
                meta_desc = desc_tag.get("content").strip()

            # Extract Headings & Paragraphs
            headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3"]) if h.get_text(strip=True)]
            paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 20]

            # Combine key textual content
            combined_parts = []
            if title:
                combined_parts.append(f"Page Title: {title}")
            if meta_desc:
                combined_parts.append(f"Meta Description: {meta_desc}")
            if headings:
                combined_parts.append("Main Headings:\n" + "\n".join(f"- {h}" for h in headings[:15]))
            if paragraphs:
                combined_parts.append("Page Content:\n" + "\n".join(paragraphs[:20]))

            full_text = "\n\n".join(combined_parts)
            # Limit total characters to 4000
            if len(full_text) > 4000:
                full_text = full_text[:4000] + "\n...[Content truncated]"

            return {
                "success": True,
                "url": clean_url,
                "title": title,
                "meta_description": meta_desc,
                "summary": f"Successfully retrieved content from {clean_url}.",
                "extracted_text": full_text
            }

    except Exception as e:
        return {
            "success": False,
            "url": clean_url,
            "error": str(e),
            "title": "",
            "summary": f"Direct website fetch failed ({type(e).__name__}). Screening will rely on startup name & provided notes.",
            "extracted_text": ""
        }
