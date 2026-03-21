#!/usr/bin/env python3
"""
Web Research Skill - Search without API keys
Uses requests + BeautifulSoup (lighter than Playwright)
"""
import sys
import json
import urllib.request
import urllib.parse
from html.parser import HTMLParser

class DDGHTMLParser(HTMLParser):
    """Simple parser for DuckDuckGo HTML results."""
    def __init__(self):
        super().__init__()
        self.results = []
        self.current = {}
        self.in_result = False
        self.in_title = False
        self.in_url = False
        self.in_snippet = False
        self.depth = 0
    
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        if tag == "div" and "result" in attrs_dict.get("class", ""):
            self.in_result = True
            self.current = {}
        
        elif self.in_result:
            if tag == "a" and "result__a" in attrs_dict.get("class", ""):
                self.in_title = True
                self.current["url"] = attrs_dict.get("href", "")
            elif tag == "a" and "result__url" in attrs_dict.get("class", ""):
                self.in_url = True
    
    def handle_data(self, data):
        if self.in_title:
            self.current["title"] = data.strip()
        elif self.in_url:
            self.current["url"] = data.strip()
        elif self.in_snippet:
            self.current["snippet"] = self.current.get("snippet", "") + data.strip()
    
    def handle_endtag(self, tag):
        if tag == "a" and self.in_title:
            self.in_title = False
        elif tag == "a" and self.in_url:
            self.in_url = False
        elif tag == "div" and self.in_result and tag == "div":
            if self.current.get("title") and self.current.get("url"):
                self.results.append(self.current)
            self.in_result = False
            self.current = {}

def search_duckduckgo_simple(query: str, num_results: int = 5):
    """Search using DuckDuckGo Lite (no JS, simple HTML)."""
    try:
        # Use DuckDuckGo Lite
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://lite.duckduckgo.com/lite/?q={encoded_query}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
        
        # Simple parsing
        results = []
        lines = html.split('\n')
        
        for i, line in enumerate(lines):
            # Look for result links
            if 'class="result-link"' in line or '<a rel="nofollow"' in line:
                # Extract title and URL
                if 'href="' in line:
                    start = line.find('href="') + 6
                    end = line.find('"', start)
                    href = line[start:end]
                    
                    # Extract title
                    title_start = line.find('>', line.find('<a')) + 1
                    title_end = line.find('</a>', title_start)
                    title = line[title_start:title_end] if title_end > title_start else "No title"
                    
                    # Clean up
                    title = title.replace('<', '').replace('>', '').strip()
                    
                    if href and not href.startswith('/') and 'duckduckgo' not in href:
                        results.append({
                            "title": title[:200],
                            "url": href,
                            "snippet": "",
                            "rank": len(results) + 1
                        })
                        
                        if len(results) >= num_results:
                            break
        
        return results[:num_results]
        
    except Exception as e:
        return [{"error": str(e)}]

def search_wikipedia(query: str):
    """Search Wikipedia API (free, no key)."""
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded}&format=json"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        results = []
        for item in data.get('query', {}).get('search', [])[:5]:
            results.append({
                "title": item['title'],
                "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(item['title'].replace(' ', '_'))}",
                "snippet": item.get('snippet', '').replace('<', '').replace('>', ''),
                "rank": len(results) + 1
            })
        
        return results
    except Exception as e:
        return [{"error": str(e)}]

def fetch_url_content(url: str, max_chars: int = 3000):
    """Fetch and extract text from URL."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8', errors='ignore')
        
        # Extract title
        title = "No title"
        if '<title>' in html.lower():
            start = html.lower().find('<title>') + 7
            end = html.lower().find('</title>', start)
            if end > start:
                title = html[start:end].strip()
        
        # Extract text content (simple approach)
        text = html
        
        # Remove script and style tags
        for tag in ['script', 'style', 'nav', 'footer', 'header']:
            while f'<{tag}' in text.lower():
                start = text.lower().find(f'<{tag}')
                end = text.lower().find(f'</{tag}>', start)
                if end > start:
                    text = text[:start] + text[end+len(f'</{tag}>'):]
                else:
                    break
        
        # Remove HTML tags
        import re
        text = re.sub('<[^<]+?>', ' ', text)
        
        # Clean up
        text = re.sub(r'\s+', ' ', text).strip()
        
        return {
            "url": url,
            "title": title[:200],
            "content": text[:max_chars],
            "content_length": len(text)
        }
        
    except Exception as e:
        return {"error": str(e), "url": url}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({
            "usage": "web_research_simple.py <command> [args]",
            "commands": {
                "search": "search <query> [num_results]",
                "wikipedia": "wikipedia <query>",
                "fetch": "fetch <url> [max_chars]"
            }
        }))
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else "OpenClaw"
        num = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        print(json.dumps(search_duckduckgo_simple(query, num), indent=2))
    
    elif command == "wikipedia":
        query = sys.argv[2] if len(sys.argv) > 2 else "OpenClaw"
        print(json.dumps(search_wikipedia(query), indent=2))
    
    elif command == "fetch":
        url = sys.argv[2] if len(sys.argv) > 2 else "https://openclaw.ai"
        max_chars = int(sys.argv[3]) if len(sys.argv) > 3 else 3000
        print(json.dumps(fetch_url_content(url, max_chars), indent=2))
    
    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))
