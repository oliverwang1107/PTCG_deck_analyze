
import requests
import json
import sys

BASE_URL = "http://127.0.0.1:5000"

endpoints = [
    "/api/overview",
    "/api/archetypes",
    "/api/winrates",
    "/api/matchups",
    "/api/trends"
]

def check_apis():
    for ep in endpoints:
        url = f"{BASE_URL}{ep}"
        print(f"--- Fetching {url} ---")
        try:
            r = requests.get(url)
            if r.status_code != 200:
                print(f"FAILED: {r.status_code}")
                # print(r.text)
            else:
                data = r.json()
                print("SUCCESS")
                # Print stats or keys to allow quick verification
                if isinstance(data, dict):
                    print("Keys:", list(data.keys()))
                    # specific checks
                    if "distribution" in data and data["distribution"] is None:
                        print("WARNING: distribution is None")
                    if "heatmap" in data and data["heatmap"] is None:
                        print("WARNING: heatmap is None")
                elif isinstance(data, list):
                    print(f"List length: {len(data)}")
                
                # Dump to file for manual inspection if needed
                fname = f"debug_api_{ep.replace('/', '_')}.json"
                with open(fname, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"Saved to {fname}")
                
        except Exception as e:
            print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    check_apis()
