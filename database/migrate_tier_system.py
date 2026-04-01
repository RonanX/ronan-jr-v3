import sqlite3

def migrate():
    conn = sqlite3.connect('database/ronan.db')
    cursor = conn.cursor()

    # Add tier column (default 'veteran' for existing characters)
    try:
        cursor.execute("ALTER TABLE characters ADD COLUMN tier TEXT DEFAULT 'veteran'")
        conn.commit()
        print("[OK] Added tier column to characters table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("[OK] tier column already exists")
        else:
            print(f"[ERROR] Failed to add tier column: {e}")

    # Add grunt column (default 0 = false for existing characters)
    try:
        cursor.execute("ALTER TABLE characters ADD COLUMN grunt INTEGER DEFAULT 0")
        conn.commit()
        print("[OK] Added grunt column to characters table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("[OK] grunt column already exists")
        else:
            print(f"[ERROR] Failed to add grunt column: {e}")

    # Add base_stats_json column (copy from stats_json for existing characters)
    try:
        cursor.execute("ALTER TABLE characters ADD COLUMN base_stats_json TEXT")
        # Copy current stats to base_stats for existing characters
        cursor.execute("UPDATE characters SET base_stats_json = stats_json WHERE base_stats_json IS NULL")
        conn.commit()
        print("[OK] Added base_stats_json column to characters table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("[OK] base_stats_json column already exists")
        else:
            print(f"[ERROR] Failed to add base_stats_json column: {e}")

    conn.close()

if __name__ == "__main__":
    migrate()
