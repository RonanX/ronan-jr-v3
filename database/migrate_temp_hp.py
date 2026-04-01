import sqlite3

def migrate():
    conn = sqlite3.connect('database/ronan.db')
    cursor = conn.cursor()

    # add temp_hp column with default value 0
    try:
        cursor.execute("ALTER TABLE characters ADD COLUMN temp_hp INTEGER DEFAULT 0")
        conn.commit()
        print("[OK] Added temp_hp column to characters table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("[OK] temp_hp column already exists")
        else:
            print(f"[ERROR] Migration failed: {e}")

    conn.close()

if __name__ == "__main__":
    migrate()
