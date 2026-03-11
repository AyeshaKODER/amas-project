import os
import httpx
from typing import List, Dict

SEARCH_PROVIDER = os.getenv('SEARCH_API_PROVIDER', 'serpapi')
SERPAPI_KEY = os.getenv('SERPAPI_API_KEY', '')

class SearchService:
    def __init__(self):
        pass
    def search(self, query: str, num: int=10) -> List[Dict]:
        if SEARCH_PROVIDER == 'serpapi':
            if not SERPAPI_KEY:
                raise RuntimeError('SERPAPI_KEY not configured')
            params = {'q': query, 'api_key': SERPAPI_KEY, 'num': num}
            with httpx.Client(timeout=15.0) as client:
                r = client.get('https://serpapi.com/search', params=params)
                r.raise_for_status()
                data = r.json()
                return data.get('organic_results', [])
        else:
            # Fallback: use DuckDuckGo unofficial JSON via httpx to scrape-lite endpoints (best-effort)
            with httpx.Client(timeout=15.0) as client:
                r = client.get('https://api.duckduckgo.com', params={'q':query, 'format':'json', 't':'amas'})
                r.raise_for_status()
                data = r.json()
                return data.get('RelatedTopics', [])


