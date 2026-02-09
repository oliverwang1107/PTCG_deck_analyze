
import sqlite3

db_path = 'c:/projects/PTCG_deck_analyze/ptcg_hij.sqlite'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("--- cards Table Columns ---")
    cursor.execute("PRAGMA table_info(cards)")
    columns = cursor.fetchall()
    for col in columns:
        print(col[1]) # col[1] is name
            
    print("\n--- meta Table Columns ---")
    cursor.execute("PRAGMA table_info(meta)")
    columns = cursor.fetchall()
    for col in columns:
        print(col[1])

    conn.close()

except Exception as e:
    print(f"Error: {e}")
