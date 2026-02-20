
import json
import os

def check_mapper_logic():
    data_path = "data/scraped_data.json"
    output_path = "data/limitless_jp_map.json"
    
    # 1. Check if TWM-111 is in scraped_data
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    found_in_data = False
    for t in data.get("tournaments", []):
        for d in t.get("decks", []):
            for c in d.get("cards", []):
                if c.get("card_id") == "TWM-111":
                    found_in_data = True
                    print(f"Found TWM-111 in deck {d.get('deck_url')}")
                    break
            if found_in_data: break
        if found_in_data: break
        
    if not found_in_data:
        print("TWM-111 NOT found in scraped_data.json")
        return

    # 2. Check if TWM-111 is in existing map
    with open(output_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)
        
    if "TWM-111" in mapping:
        print("TWM-111 IS in mapping:")
        print(mapping["TWM-111"])
    else:
        print("TWM-111 is NOT in mapping.")
        
    # 3. Simulate cards_to_map logic
    unique_cards = set()
    for tournament in data.get("tournaments", []):
        for deck in tournament.get("decks", []):
            for card in deck.get("cards", []):
                if "set_code" in card and "card_id" in card:
                    parts = card['card_id'].split('-')
                    number = parts[-1] 
                    unique_cards.add((card['set_code'], number))
                    
    twm_111_tuple = ("TWM", "111")
    if twm_111_tuple in unique_cards:
        print("Tuple ('TWM', '111') is in unique_cards.")
    else:
        print("Tuple ('TWM', '111') is NOT in unique_cards.")
        
    to_map = [c for c in unique_cards if f"{c[0]}-{c[1]}" not in mapping]
    if twm_111_tuple in to_map:
        print("Tuple ('TWM', '111') IS in to_map list.")
    else:
        print("Tuple ('TWM', '111') is NOT in to_map list.")

if __name__ == "__main__":
    check_mapper_logic()
