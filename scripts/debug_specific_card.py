
import json
import sqlite3

def debug_card(limitless_id):
    print(f"--- Debugging {limitless_id} ---")
    
    # 1. Check Map
    with open("data/limitless_jp_map.json", "r", encoding="utf-8") as f:
        mapping = json.load(f)
        
    if limitless_id in mapping:
        jp_info = mapping[limitless_id]
        print(f"Mapped to: {jp_info}")
        jp_set = jp_info['set']
        jp_num = jp_info['number']
        
        # 2. Check DB
        conn = sqlite3.connect("data/ptcg_hij.sqlite")
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT * FROM cards WHERE expansion_code = ? AND collector_number = ?", (jp_set, jp_num))
        row = c.fetchone()
        
        if row:
            print(f"Found in DB: {row['name']} ({row['expansion_code']}-{row['collector_number']})")
        else:
            print(f"NOT FOUND in DB: {jp_set}-{jp_num}")
            # Try searching loosely
            c.execute("SELECT * FROM cards WHERE expansion_code = ?", (jp_set,))
            rows = c.fetchall()
            print(f"Set {jp_set} has {len(rows)} cards.")
            
        conn.close()
    else:
        print("Not found in mapping file.")

if __name__ == "__main__":
    # Test Lillie's Determination (PAF-180) and typical Ultra Ball (PAF-091 or SVI-196)
    debug_card("PAF-180") 
    debug_card("PAF-091") 
    debug_card("SVI-196")
