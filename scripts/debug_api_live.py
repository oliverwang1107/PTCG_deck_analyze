
import requests
import sys

BASE_URL = "http://127.0.0.1:5000"

def test_endpoint(endpoint):
    url = f"{BASE_URL}{endpoint}"
    print(f"Testing {url}...")
    try:
        resp = requests.get(url, timeout=5)
        print(f"Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Error: {resp.text[:500]}")
            return False
        
        try:
            data = resp.json()
            print("JSON Decoded successfully.")
            # print(str(data)[:200] + "...")
            return True
        except Exception as e:
            print(f"JSON Decode Error: {e}")
            return False
            
    except Exception as e:
        print(f"Connection Error: {e}")
        return False

if __name__ == "__main__":
    endpoints = [
        "/api/overview",
        "/api/archetypes", 
        "/api/tournaments/weekly",
        "/api/recent-decks" # Wait, did I add this one? I need to check app.py routes.
    ]
    
    success = True
    for ep in endpoints:
        if not test_endpoint(ep):
            success = False
            
    if not success:
        sys.exit(1)
