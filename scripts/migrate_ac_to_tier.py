"""
Migration script: Convert AC from number ranges to tier system (1/2/3)

AC tier mapping:
- Old AC 10-12 → Tier 1 (easy)
- Old AC 13-15 → Tier 2 (medium)
- Old AC 16-18 → Tier 3 (hard)
"""

import sqlite3
import sys

DATABASE_PATH = 'database/ronan.db'

def migrate_ac_to_tier():
    """Convert existing AC values to tier system."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # Get all characters with their current AC
        cursor.execute("SELECT name, ac FROM characters")
        characters = cursor.fetchall()

        if not characters:
            print("[INFO] No characters found in database")
            return

        print(f"[INFO] Found {len(characters)} characters to migrate")

        # Migrate each character
        migrated_count = 0
        for name, old_ac in characters:
            # Determine new tier based on old AC
            if old_ac <= 12:
                new_tier = 1
                tier_label = "Tier 1 (easy)"
            elif old_ac <= 15:
                new_tier = 2
                tier_label = "Tier 2 (medium)"
            else:  # 16+
                new_tier = 3
                tier_label = "Tier 3 (hard)"

            # Update character
            cursor.execute("UPDATE characters SET ac = ? WHERE name = ?", (new_tier, name))
            print(f"[MIGRATE] {name}: AC {old_ac} -> {new_tier} ({tier_label})")
            migrated_count += 1

        # Commit changes
        conn.commit()
        print(f"\n[OK] Successfully migrated {migrated_count} characters")

        # Verify migration
        print("\n[VERIFY] Current AC values:")
        cursor.execute("SELECT name, ac FROM characters ORDER BY ac, name")
        for name, ac in cursor.fetchall():
            print(f"  {name}: AC tier {ac}")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("AC TIER MIGRATION SCRIPT")
    print("=" * 60)
    print("\nConverting AC from number ranges to tier system (1/2/3)")
    print("Mapping:")
    print("  - AC 10-12 -> Tier 1 (easy)")
    print("  - AC 13-15 -> Tier 2 (medium)")
    print("  - AC 16-18 -> Tier 3 (hard)")
    print()

    migrate_ac_to_tier()

    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
