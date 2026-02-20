
import json
import os

def check_unmapped():
    data_path = "data/scraped_data.json"
    map_path = "data/limitless_jp_map.json"
    
    # Load map
    if os.path.exists(map_path):
        with open(map_path, "r", encoding="utf-8") as f:
            mapping = json.load(f)
    else:
        mapping = {}
        
    print(f"Loaded {len(mapping)} mapped entries.")

    # Load data
    if os.path.exists(data_path):
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        unmapped = {}
        total_cards = 0
        
        for tournament in data.get("tournaments", []):
            for deck in tournament.get("decks", []):
                for card in deck.get("cards", []):
                    if "set_code" in card and "card_id" in card:
                        # Construct ID
                        parts = card['card_id'].split('-')
                        number = parts[-1]
                        limitless_id = f"{card['set_code']}-{number}"
                        
                        if limitless_id not in mapping:
                            if limitless_id not in unmapped:
                                unmapped[limitless_id] = {
                                    "name": card.get("name"),
                                    "count": 0
                                }
                            unmapped[limitless_id]["count"] += 1
                        total_cards += 1
                        
        print(f"Total card instances processed: {total_cards}")
        print(f"Found {len(unmapped)} unmapped unique cards.")
        
        print("\nTop 20 Unmapped Cards:")
        sorted_unmapped = sorted(unmapped.items(), key=lambda x: x[1]['count'], reverse=True)
        for uid, info in sorted_unmapped[:20]:
            print(f"{uid}: {info['name']} (Count: {info['count']})")
            
    else:
        print("Data file not found.")

if __name__ == "__main__":
    check_unmapped()
