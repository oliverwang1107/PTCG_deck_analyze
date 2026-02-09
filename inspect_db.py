
import sqlite3

db_path = 'c:/projects/PTCG_deck_analyze/ptcg_hij.sqlite'

try:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Access columns by name
    cursor = conn.cursor()
    
    # Get columns for 'cards' table
    print("--- 'cards' Table Schema ---")
    cursor.execute("PRAGMA table_info(cards)")
    columns = cursor.fetchall()
    col_names = []
    for col in columns:
        print(f"{col['cid']}: {col['name']} ({col['type']})")
        col_names.append(col['name'])
            
    # Preview data
    print("\n--- First 3 rows from 'cards' ---")
    cursor.execute(f"SELECT * FROM cards LIMIT 3")
    rows = cursor.fetchall()
    for row in rows:
        print(dict(row))

    conn.close()

except Exception as e:
    print(f"Error: {e}")
