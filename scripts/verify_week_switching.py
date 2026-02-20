import requests
import json
import sys

BASE_URL = "http://127.0.0.1:5000"

def test_week_switching():
    print(f"Testing API at {BASE_URL}...")
    
    # 1. Get available weeks
    try:
        resp = requests.get(f"{BASE_URL}/api/tournaments/weekly")
        if resp.status_code != 200:
            print(f"FAILED: /api/tournaments/weekly returned {resp.status_code}")
            return
        
        data = resp.json()
        weeks = data.get("weeks", [])
        if not weeks:
            print("WARNING: No weeks found in data.")
            return
            
        print(f"Found {len(weeks)} weeks: {[w['week'] for w in weeks]}")
        
        # Test Latest (no param)
        resp_latest = requests.get(f"{BASE_URL}/api/overview")
        latest_data = resp_latest.json()
        print(f"Latest Week Overview: Current={latest_data.get('current_week')}, Tournaments={latest_data.get('total_tournaments')}")
        
        # Test Each Week
        for w in weeks[:3]: # Test top 3 weeks
            week_key = w['week']
            resp_week = requests.get(f"{BASE_URL}/api/overview?week={week_key}")
            week_data = resp_week.json()
            
            print(f"Week {week_key} Overview: Current={week_data.get('current_week')}, Tournaments={week_data.get('total_tournaments')}")
            
            # Check if it matches expected
            if week_data.get('current_week') != week_key:
                print(f"ERROR: Requested week {week_key} but got {week_data.get('current_week')}")
            
            # Verify Trends also accept week
            resp_trends = requests.get(f"{BASE_URL}/api/trends?week={week_key}")
            if resp_trends.status_code != 200:
                print(f"ERROR: /api/trends?week={week_key} failed")
                
    except Exception as e:
        print(f"Exception during test: {e}")

if __name__ == "__main__":
    test_week_switching()
