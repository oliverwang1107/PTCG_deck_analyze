
import sqlite3

def check_db():
    db_path = "data/ptcg_hij.sqlite"
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cards'")
        if not cursor.fetchone():
            print("Table 'cards' does not exist!")
            return

        # Check for SV6 / 64
        print("Checking for SV6 / 64...")
        cursor.execute("SELECT * FROM cards WHERE expansion_code = 'SV6' AND collector_number LIKE '%64%'")
        rows = cursor.fetchall()
        if rows:
            print(f"Found {len(rows)} rows matching '%64%':")
            for row in rows:
                print(f"  Name: {row['name']}")
                print(f"  Set: {row['expansion_code']}")
                print(f"  Number: {row['collector_number']}")
                print(f"  Image: {row['image_url']}")
                print("-" * 20)
        else:
            print("No rows found for SV6 / 64")
            
        # Check for exact 064
        print("\nChecking for SV6 with number '064'...")
        cursor.execute("SELECT * FROM cards WHERE expansion_code = 'SV6' AND collector_number LIKE '064%'")
        rows = cursor.fetchall()
        if not rows:
             print("No rows found for exact 064 prefix")

        # List some SV6 cards to see format
        print("\nListing first 5 SV6 cards:")
        cursor.execute("SELECT expansion_code, collector_number, name FROM cards WHERE expansion_code = 'SV6' LIMIT 5")
        for row in rows:
            print(f"  {row['expansion_code']} - {row['collector_number']} : {row['name']}")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db()
