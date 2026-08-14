"""
Migration script for damage system redesign.

This script:
1. Adds damage_formula column to movesets table
2. Adds resistances/vulnerabilities columns to characters and forms tables
3. Migrates existing damage values to damage_formula format

Run this ONCE before deploying the new damage system.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))


def migrate_damage_system():
    """Run the complete damage system migration."""
    db_path = Path(__file__).parent / "ronan.db"

    if not db_path.exists():
        print(f"[ERROR] Database not found at {db_path}")
        return False

    print(f"[INFO] Starting damage system migration on {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # ===== STEP 1: Add new columns =====
        print("[INFO] Adding new columns...")

        # Add damage_formula to movesets
        try:
            cursor.execute("ALTER TABLE movesets ADD COLUMN damage_formula TEXT")
            print("[OK] Added damage_formula column to movesets")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("[SKIP] damage_formula column already exists in movesets")
            else:
                raise

        # Add resistances/vulnerabilities to characters
        try:
            cursor.execute("ALTER TABLE characters ADD COLUMN resistances TEXT DEFAULT '[]'")
            print("[OK] Added resistances column to characters")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("[SKIP] resistances column already exists in characters")
            else:
                raise

        try:
            cursor.execute("ALTER TABLE characters ADD COLUMN vulnerabilities TEXT DEFAULT '[]'")
            print("[OK] Added vulnerabilities column to characters")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("[SKIP] vulnerabilities column already exists in characters")
            else:
                raise

        # Add resistances/vulnerabilities to forms
        try:
            cursor.execute("ALTER TABLE forms ADD COLUMN resistances TEXT DEFAULT '[]'")
            print("[OK] Added resistances column to forms")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("[SKIP] resistances column already exists in forms")
            else:
                raise

        try:
            cursor.execute("ALTER TABLE forms ADD COLUMN vulnerabilities TEXT DEFAULT '[]'")
            print("[OK] Added vulnerabilities column to forms")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("[SKIP] vulnerabilities column already exists in forms")
            else:
                raise

        conn.commit()

        # ===== STEP 2: Migrate existing damage values =====
        print("\n[INFO] Migrating existing damage values...")

        # Get all moves with damage > 0 or damage IS NULL
        cursor.execute("""
            SELECT id, character_name, form_name, move_name, damage, damage_formula
            FROM movesets
        """)

        moves = cursor.fetchall()
        migrated_count = 0
        skipped_count = 0

        for move_id, char_name, form_name, move_name, damage, existing_formula in moves:
            # Skip if damage_formula already exists
            if existing_formula is not None and existing_formula.strip():
                skipped_count += 1
                continue

            # Migrate based on damage value
            new_formula = None
            if damage is not None and damage > 0:
                new_formula = str(damage)
            elif damage == 0 or damage is None:
                # Keep as NULL for moves with no damage (utility moves, etc.)
                new_formula = None

            if new_formula:
                cursor.execute("""
                    UPDATE movesets
                    SET damage_formula = ?
                    WHERE id = ?
                """, (new_formula, move_id))
                migrated_count += 1
                print(f"[MIGRATE] {char_name}/{form_name}/{move_name}: damage={damage} -> damage_formula='{new_formula}'")

        conn.commit()

        print(f"\n[OK] Migration complete!")
        print(f"  - Migrated: {migrated_count} moves")
        print(f"  - Skipped: {skipped_count} moves (already had damage_formula)")

        # ===== STEP 3: Verify migration =====
        print("\n[INFO] Verifying migration...")

        cursor.execute("""
            SELECT COUNT(*) FROM movesets
            WHERE damage > 0 AND (damage_formula IS NULL OR damage_formula = '')
        """)
        unmigrated = cursor.fetchone()[0]

        if unmigrated > 0:
            print(f"[WARNING] {unmigrated} moves still have damage but no damage_formula!")
            cursor.execute("""
                SELECT character_name, form_name, move_name, damage
                FROM movesets
                WHERE damage > 0 AND (damage_formula IS NULL OR damage_formula = '')
            """)
            for row in cursor.fetchall():
                print(f"  - {row[0]}/{row[1]}/{row[2]}: damage={row[3]}")
        else:
            print("[OK] All moves with damage have been migrated to damage_formula")

        # Show sample of migrated data
        print("\n[INFO] Sample of migrated moves:")
        cursor.execute("""
            SELECT character_name, form_name, move_name, damage, damage_formula
            FROM movesets
            WHERE damage_formula IS NOT NULL
            LIMIT 5
        """)
        for row in cursor.fetchall():
            print(f"  {row[0]}/{row[1]}/{row[2]}: damage={row[3]}, formula='{row[4]}'")

        return True

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Damage System Migration Script")
    print("=" * 60)
    print()

    success = migrate_damage_system()

    print()
    print("=" * 60)
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed. Please check errors above.")
    print("=" * 60)

    sys.exit(0 if success else 1)
