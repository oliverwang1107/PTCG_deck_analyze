
import sqlite3
import json
import os

class CardDB:
    def __init__(self, db_path="data/ptcg_hij.sqlite", jp_db_path="data/ptcg_jp.sqlite", map_path="data/limitless_jp_map.json"):
        self.db_path = db_path
        self.jp_db_path = jp_db_path
        self.map_path = map_path
        self.mapping = {}
        self.conn = None
        self.cursor = None
        self.jp_conn = None
        self.jp_cursor = None
        
        self.load_mapping()
        self.connect()

    def load_mapping(self):
        if os.path.exists(self.map_path):
            with open(self.map_path, "r", encoding="utf-8") as f:
                self.mapping = json.load(f)
        else:
            print(f"Warning: Mapping file {self.map_path} not found.")

    def connect(self):
        # Connect to TW database
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
        except Exception as e:
            print(f"Error connecting to TW DB {self.db_path}: {e}")
        
        # Connect to JP database if it exists
        if os.path.exists(self.jp_db_path):
            try:
                self.jp_conn = sqlite3.connect(self.jp_db_path, check_same_thread=False)
                self.jp_conn.row_factory = sqlite3.Row
                self.jp_cursor = self.jp_conn.cursor()
            except Exception as e:
                print(f"Error connecting to JP DB {self.jp_db_path}: {e}")

    def get_card_info(self, set_code, number, english_name=None):
        """
        Get card info based on Limitless set/number.
        Returns dict with name_zh (or name_jp), image_url, etc.
        """
        limitless_id = f"{set_code}-{number}"
        
        # 1. Try mapping
        if limitless_id in self.mapping:
            jp_info = self.mapping[limitless_id]
            jp_set = jp_info['set']
            jp_num = jp_info['number']
            
            # Query TW DB first with JP set/num
            result = self._query_db_by_expansion(self.cursor, jp_set, jp_num)
            if result:
                return result
            
            # Fallback to JP DB if TW DB failed
            if self.jp_cursor:
                result = self._query_db_by_expansion(self.jp_cursor, jp_set, jp_num, use_jp_name=True)
                if result:
                    return result
                
        # 2. Fallback: Query by English name (using translation)
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
    
    def _query_db_by_expansion(self, cursor, jp_set, jp_num, use_jp_name=False):
        """Helper to query a database by expansion_code and collector_number."""
        try:
            # Try padding to 3 digits (standard JP format in DB)
            num_int = int(jp_num)
            padded_num = f"{num_int:03d}"
            
            query = "SELECT name, image_url, expansion_code, collector_number FROM cards WHERE expansion_code = ? AND (collector_number LIKE ? OR collector_number LIKE ?)"
            # Try '001/%' and '001'
            cursor.execute(query, (jp_set, f"{padded_num}/%", padded_num))
            row = cursor.fetchone()
            
            if not row:
                 # Try without padding (e.g. if DB has 1/187)
                 cursor.execute(query, (jp_set, f"{jp_num}/%", jp_num))
                 row = cursor.fetchone()
                 
            if row:
                name_key = "name_jp" if use_jp_name else "name_zh"
                return {
                    name_key: row['name'],
                    "image_url": row['image_url'],
                    "jp_set": row['expansion_code'],
                    "jp_num": row['collector_number']
                }
                
        except ValueError:
            # jp_num matches non-integer (e.g. 'TB'), try direct match
            query = "SELECT name, image_url, expansion_code, collector_number FROM cards WHERE expansion_code = ? AND collector_number LIKE ?"
            cursor.execute(query, (jp_set, f"{jp_num}%"))
            row = cursor.fetchone()
            
            if row:
                name_key = "name_jp" if use_jp_name else "name_zh"
                return {
                    name_key: row['name'],
                    "image_url": row['image_url'],
                    "jp_set": row['expansion_code'],
                    "jp_num": row['collector_number']
                }
        
        return None

    def close(self):
        if self.conn:
            self.conn.close()
        if self.jp_conn:
            self.jp_conn.close()
