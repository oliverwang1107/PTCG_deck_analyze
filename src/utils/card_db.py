
import sqlite3
import json
import os

class CardDB:
    def __init__(self, db_path="ptcg_hij.sqlite", map_path="data/limitless_jp_map.json"):
        self.db_path = db_path
        self.map_path = map_path
        self.mapping = {}
        self.conn = None
        self.cursor = None
        
        self.load_mapping()
        self.connect()

    def load_mapping(self):
        if os.path.exists(self.map_path):
            with open(self.map_path, "r", encoding="utf-8") as f:
                self.mapping = json.load(f)
        else:
            print(f"Warning: Mapping file {self.map_path} not found.")

    def connect(self):
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
        except Exception as e:
            print(f"Error connecting to DB {self.db_path}: {e}")

    def get_card_info(self, set_code, number, english_name=None):
        """
        Get Chinese card info based on Limitless set/number.
        Returns dict with name_zh, image_url, etc.
        """
        limitless_id = f"{set_code}-{number}"
        
        # 1. Try mapping
        if limitless_id in self.mapping:
            jp_info = self.mapping[limitless_id]
            jp_set = jp_info['set']
            jp_num = jp_info['number']
            
            # Query DB with JP set/num
            # DB collector_number format is often like "079/101" or just "079"
            # We should try exact match or match prefix
            
            # Try to query by expansion_code and simple number match first
            # We need to handle leading zeros in DB or from Mapper
            # Mapper '079', DB '079/101' -> match '079%'
            
            # DB format: 001/187, Limitless format: 1, 79, 118
            try:
                # Try padding to 3 digits (standard JP format in DB)
                num_int = int(jp_num)
                padded_num = f"{num_int:03d}"
                
                query = "SELECT name, image_url, expansion_code, collector_number FROM cards WHERE expansion_code = ? AND (collector_number LIKE ? OR collector_number LIKE ?)"
                # Try '001/%' and '001'
                self.cursor.execute(query, (jp_set, f"{padded_num}/%", padded_num))
                row = self.cursor.fetchone()
                
                if not row:
                     # Try without padding (e.g. if DB has 1/187)
                     self.cursor.execute(query, (jp_set, f"{jp_num}/%", jp_num))
                     row = self.cursor.fetchone()
                     
                if row:
                    return {
                        "name_zh": row['name'],
                        "image_url": row['image_url'],
                        "jp_set": row['expansion_code'],
                        "jp_num": row['collector_number']
                    }
                    
            except ValueError:
                # jp_num matches non-integer (e.g. 'TB'), try direct match
                query = "SELECT name, image_url, expansion_code, collector_number FROM cards WHERE expansion_code = ? AND collector_number LIKE ?"
                self.cursor.execute(query, (jp_set, f"{jp_num}%"))
                row = self.cursor.fetchone()
                
                if row:
                    return {
                        "name_zh": row['name'],
                        "image_url": row['image_url'],
                        "jp_set": row['expansion_code'],
                        "jp_num": row['collector_number']
                    }
                
        # 2. Fallback: Query by English name (Limitless name) if we had a name mapping
        # But we don't have English names in DB.
        # We could try to translate English name to Chinese (using my translation.py) and query by name.
        if english_name:
            from ..translation import translate_pokemon_name
            zh_name = translate_pokemon_name(english_name)
            if zh_name and zh_name != english_name:
                # Query by name
                query = "SELECT name, image_url FROM cards WHERE name = ? LIMIT 1"
                self.cursor.execute(query, (zh_name,))
                row = self.cursor.fetchone()
                if row:
                     return {
                        "name_zh": row['name'],
                        "image_url": row['image_url'],
                        "note": "Fuzzy match by name"
                    }

        return None

    def close(self):
        if self.conn:
            self.conn.close()
