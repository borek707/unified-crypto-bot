---
name: web-research
description: Web search and content extraction without API keys. Search Wikipedia, fetch webpage content, and extract text using simple HTTP requests. Use when you need to research topics without requiring Brave API key, Google API, or other paid search APIs. Falls back to multiple sources for reliability.
---

# Web Research Skill

Research the web without API keys using lightweight HTTP requests.

## Features

- ✅ **No API keys required**
- ✅ **Wikipedia search** (fast, reliable)
- ✅ **DuckDuckGo search** (when available)
- ✅ **Web page fetching** (extract content)
- ✅ **Lightweight** (no browser needed)
- ✅ **Fast** (1-2 seconds per query)

## Commands

### Wikipedia Search

```bash
python3 scripts/web_research_simple.py wikipedia "Gold trading"
python3 scripts/web_research_simple.py wikipedia "Python programming"
```

### Web Search (DuckDuckGo)

```bash
python3 scripts/web_research_simple.py search "OpenClaw documentation"
python3 scripts/web_research_simple.py search "bitcoin price" 10
```

### Fetch Page Content

```bash
python3 scripts/web_research_simple.py fetch https://en.wikipedia.org/wiki/Gold
python3 scripts/web_research_simple.py fetch https://example.com 5000
```

## Docker Setup

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
CMD ["python3", "scripts/web_research_simple.py"]
```

Build and run:
```bash
docker build -t web-research .
docker run web-research wikipedia "your query"
```

## Alternative: Playwright Version

For JavaScript-heavy sites, use the Playwright version:

```bash
# Install Playwright
pip install playwright
playwright install chromium

# Use advanced version
python3 scripts/web_research.py search "query"
```

## Output Format

### Search Results
```json
[
  {
    "title": "Page Title",
    "url": "https://example.com",
    "snippet": "Description...",
    "rank": 1
  }
]
```

### Page Content
```json
{
  "url": "https://example.com",
  "title": "Page Title",
  "content": "Extracted text...",
  "content_length": 1234
}
```

## When to Use

- Research without API keys
- Quick fact checking
- Fetch documentation
- Extract article content
- Backup when Brave API unavailable

## Limitations

- DuckDuckGo may rate-limit heavy usage
- Some sites block automated requests
- JavaScript-heavy sites need Playwright version