
import json
import os
import time
import random
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

class CardMapper:
    def __init__(self, data_path="data/scraped_data.json", output_path="data/limitless_jp_map.json"):
        self.data_path = data_path
        self.output_path = output_path
        self.mapping = {}
        self.cards_to_map = set()
        
    def load_data(self):
        if os.path.exists(self.output_path):
            with open(self.output_path, "r", encoding="utf-8") as f:
                self.mapping = json.load(f)
                print(f"Loaded existing mapping with {len(self.mapping)} entries.")
        
        if os.path.exists(self.data_path):
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            for tournament in data.get("tournaments", []):
                for deck in tournament.get("decks", []):
                    for card in deck.get("cards", []):
                        if "set_code" in card and "card_id" in card:
                            limitless_id = f"{card['set_code']}-{card['card_id'].split('-')[-1]}"
                            if limitless_id not in self.mapping:
                                self.cards_to_map.add((card['set_code'], card['card_id'].split('-')[-1]))
            
            print(f"Found {len(self.cards_to_map)} new cards to map.")
        else:
            print(f"Data file {self.data_path} not found.")

    def fetch_card_jp_info(self, set_code, number):
        url = f"https://limitlesstcg.com/cards/{set_code}/{number}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find JP Prints section
                # Look for row with "JP. Prints" header
                jp_header = soup.find('th', string=lambda t: t and "JP. Prints" in t)
                if jp_header:
                    # The next rows should contain JP prints
                    # But they might be in separate trs.
                    # Based on HTML structure seen in debug file:
                    # <tr><th colspan="3">JP. Prints</th></tr>
                    # <tr>...<a href="/cards/jp/SV6/79">...</a>...</tr>
                    
                    found_prints = []
                    current_row = jp_header.parent.find_next_sibling('tr')
                    while current_row:
                        link = current_row.find('a', href=True)
                        if link and '/cards/jp/' in link['href']:
                            parts = link['href'].split('/')
                            # Expected format: /cards/jp/{set}/{number}
                            if len(parts) >= 5:
                                jp_set = parts[3]
                                jp_number = parts[4].split('?')[0] # Remove query params if any
                                found_prints.append({'set': jp_set, 'number': jp_number})
                        
                        current_row = current_row.find_next_sibling('tr')
                        # Stop if we hit a new header or end of table (structure might vary)
                        # Actually, strictly following siblings is risky if structure changes.
                        # But looking at debug HTML, all rows after JP header seemed safely to be JP prints until table end?
                        # The debug HTML showed table closing after JP prints. So this should work.
                        
                    return found_prints
            else:
                print(f"Failed to fetch {url}: {response.status_code}")
        except Exception as e:
            print(f"Error fetching {url}: {e}")
        return None

    def process_card(self, card_tuple):
        set_code, number = card_tuple
        limitless_id = f"{set_code}-{number}"
        
        # Rate limiting
        time.sleep(random.uniform(0.5, 1.5))
        
        print(f"Mapping {limitless_id}...")
        jp_prints = self.fetch_card_jp_info(set_code, number)
        
        if jp_prints:
            print(f"  -> Found: {jp_prints[0]}")
            return limitless_id, jp_prints
        else:
            print(f"  -> No JP prints found for {limitless_id}")
            return limitless_id, None
            
    def run(self):
        # Load unique cards from scraped data
        if os.path.exists(self.data_path):
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            unique_cards = set()
            for tournament in data.get("tournaments", []):
                for deck in tournament.get("decks", []):
                    for card in deck.get("cards", []):
                        if "set_code" in card and "card_id" in card:
                            # Extract number from ID (e.g. TWM-111 -> 111)
                            # Some IDs might be like "SMP-SM226", so split carefully
                            parts = card['card_id'].split('-')
                            number = parts[-1] 
                            unique_cards.add((card['set_code'], number))
            
            # Filter out already mapped
            if os.path.exists(self.output_path):
                with open(self.output_path, "r", encoding="utf-8") as f:
                    self.mapping = json.load(f)
                    print(f"Loaded existing mapping: {len(self.mapping)} entries")
            
            self.cards_to_map = [c for c in unique_cards if f"{c[0]}-{c[1]}" not in self.mapping]
            print(f"Total unique cards: {len(unique_cards)}")
            print(f"Cards needed to map: {len(self.cards_to_map)}")
        else:
            print(f"Data file {self.data_path} not found.")
            return

        if not self.cards_to_map:
            print("No new cards to map.")
            return
            
        # Use ThreadPoolExecutor for concurrent fetching
        # Be nice to the server, limit workers
        print("Starting mapping process...")
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(self.process_card, self.cards_to_map))
            
        new_mappings = 0
        for limitless_id, jp_prints in results:
            if jp_prints:
                self.mapping[limitless_id] = jp_prints[0] # Take the first one as primary
                new_mappings += 1
                
        # Save mapping
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(self.mapping, f, indent=2, ensure_ascii=False)
        print(f"Saved mapping to {self.output_path} (Added {new_mappings} entries)")

if __name__ == "__main__":
    mapper = CardMapper()
    mapper.run()
