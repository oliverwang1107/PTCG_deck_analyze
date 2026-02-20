import unittest
from unittest.mock import MagicMock, patch
import sys

# Mock modules to avoid importing real ones that might need config/DB
sys.modules['src.web.app'] = MagicMock()
# Wait, we need the real app file to verify the code... 
# But we can't easily import it if it connects to DB at top level 
# (it doesn't seem to connect at top level, only in functions).

# Let's just import the specific function if possible, or use string search.
# String search is sufficient for this trivial change.

def verify_code_change():
    with open('src/web/app.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'limit=50' in content and 'get_recent_decks(name, limit=50)' in content:
        print("SUCCESS: Code contains limit=50")
    else:
        print("FAILURE: Code does not contain limit=50")
        
    with open('src/web/templates/index.html', 'r', encoding='utf-8') as f:
        html = f.read()
        
    if 'Recent 50' in html and 'recent_decks' in html:
        print("SUCCESS: HTML contains pagination/limit text")
    else:
        print("FAILURE: HTML missing recent decks section")

if __name__ == "__main__":
    verify_code_change()
