
import json

def extract():
    try:
        with open("data/scraped_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            
        archetypes = set()
        for t in data.get("tournaments", []):
            for d in t.get("decks", []):
                arch = d.get("archetype", "Unknown")
                if arch != "Unknown":
                    # Split mainly for "dragonite / pidgeot" style
                    parts = arch.split(" / ")
                    for p in parts:
                        archetypes.add(p.strip())
                        
        print("Unique Archetype Parts:")
        for a in sorted(archetypes):
            print(a)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    extract()
