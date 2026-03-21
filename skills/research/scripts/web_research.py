#!/usr/bin/env python3
"""
Web Research Skill - Search and extract content without API keys
Uses Playwright for headless browser automation
"""
import sys
import json
import asyncio
from typing import List, Dict, Optional
from urllib.parse import quote_plus

# Check if playwright is available
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

async def search_google(query: str, num_results: int = 5) -> List[Dict]:
    """Search Google and return results."""
    if not HAS_PLAYWRIGHT:
        return [{"error": "Playwright not installed. Run: pip install playwright && playwright install"}]
    
    results = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # Go to Google
            search_url = f"https://www.google.com/search?q={quote_plus(query)}"
            await page.goto(search_url, wait_until="networkidle")
            
            # Wait for results
            await page.wait_for_selector("div[data-result-index]", timeout=5000)
            
            # Extract search results
            search_results = await page.query_selector_all("div[data-result-index]")
            
            for i, result in enumerate(search_results[:num_results]):
                try:
                    # Try to get title
                    title_elem = await result.query_selector("h3")
                    title = await title_elem.inner_text() if title_elem else "No title"
                    
                    # Try to get link
                    link_elem = await result.query_selector("a[href]")
                    href = await link_elem.get_attribute("href") if link_elem else ""
                    
                    # Try to get snippet
                    snippet_elem = await result.query_selector("span, div[data-sokoban-container]")
                    snippet = await snippet_elem.inner_text() if snippet_elem else ""
                    
                    # Filter out non-HTTP links
                    if href and href.startswith("http"):
                        results.append({
                            "title": title[:200],
                            "url": href,
                            "snippet": snippet[:300],
                            "rank": i + 1
                        })
                except Exception:
                    continue
                    
        except Exception as e:
            results.append({"error": str(e)})
        finally:
            await browser.close()
    
    return results

async def search_duckduckgo(query: str, num_results: int = 5) -> List[Dict]:
    """Search DuckDuckGo (more scraping-friendly)."""
    if not HAS_PLAYWRIGHT:
        return [{"error": "Playwright not installed"}]
    
    results = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # DuckDuckGo HTML version (no JS required)
            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            await page.goto(search_url, wait_until="networkidle")
            
            # Extract results
            search_results = await page.query_selector_all(".result")
            
            for i, result in enumerate(search_results[:num_results]):
                try:
                    title_elem = await result.query_selector(".result__title")
                    title = await title_elem.inner_text() if title_elem else "No title"
                    
                    link_elem = await result.query_selector(".result__url")
                    url = await link_elem.inner_text() if link_elem else ""
                    
                    snippet_elem = await result.query_selector(".result__snippet")
                    snippet = await snippet_elem.inner_text() if snippet_elem else ""
                    
                    results.append({
                        "title": title[:200],
                        "url": url,
                        "snippet": snippet[:300],
                        "rank": i + 1
                    })
                except Exception:
                    continue
                    
        except Exception as e:
            results.append({"error": str(e)})
        finally:
            await browser.close()
    
    return results

async def fetch_page_content(url: str, max_chars: int = 3000) -> Dict:
    """Fetch and extract readable content from a webpage."""
    if not HAS_PLAYWRIGHT:
        return {"error": "Playwright not installed"}
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=15000)
            
            # Get title
            title = await page.title()
            
            # Try to get main content
            # Strategy 1: Look for article/main/content
            content = ""
            for selector in ["article", "main", "[role='main']", ".content", "#content"]:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        content = await elem.inner_text()
                        if len(content) > 200:
                            break
                except:
                    continue
            
            # Strategy 2: Get all paragraphs
            if len(content) < 200:
                paragraphs = await page.query_selector_all("p")
                content = "\n\n".join([await p.inner_text() for p in paragraphs[:20]])
            
            # Clean up content
            content = " ".join(content.split())  # Remove extra whitespace
            
            return {
                "url": url,
                "title": title[:200],
                "content": content[:max_chars],
                "content_length": len(content)
            }
            
        except Exception as e:
            return {"error": str(e), "url": url}
        finally:
            await browser.close()

def search_sync(query: str, engine: str = "duckduckgo", num_results: int = 5) -> List[Dict]:
    """Synchronous wrapper for search."""
    return asyncio.run(search_duckduckgo(query, num_results) if engine == "duckduckgo" else search_google(query, num_results))

def fetch_sync(url: str, max_chars: int = 3000) -> Dict:
    """Synchronous wrapper for fetch."""
    return asyncio.run(fetch_page_content(url, max_chars))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: web_research.py <command> [args]"}))
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else "OpenClaw documentation"
        engine = sys.argv[3] if len(sys.argv) > 3 else "duckduckgo"
        num = int(sys.argv[4]) if len(sys.argv) > 4 else 5
        print(json.dumps(search_sync(query, engine, num), indent=2))
    
    elif command == "fetch":
        url = sys.argv[2] if len(sys.argv) > 2 else "https://openclaw.ai"
        max_chars = int(sys.argv[3]) if len(sys.argv) > 3 else 3000
        print(json.dumps(fetch_sync(url, max_chars), indent=2))
    
    else:
        print(json.dumps({"error": f"Unknown command: {command}. Use 'search' or 'fetch'"}))
