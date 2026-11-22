"""Docker health check: exit 0 if GET /health answers 200, else 1 (Week 8)."""
import os
import sys
import urllib.request

try:
    url = f"http://localhost:{os.environ.get('PORT', 8000)}/health"
    sys.exit(0 if urllib.request.urlopen(url, timeout=3).status == 200 else 1)
except Exception:
    sys.exit(1)
