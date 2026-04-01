"""
Re-import Alicia and Hin'obi with correct column order
First deletes existing moves, then imports with fixed data
"""

import asyncio
import aiosqlite

DATABASE_PATH = 'database/ronan.db'

async def main():
    db = await aiosqlite.connect(DATABASE_PATH)

    # Delete existing moves
    print("Deleting existing moves for Alicia and Hinobi...")
    await db.execute("DELETE FROM movesets WHERE character_name IN ('Alicia', 'Hinobi')")
    await db.commit()
    print("[OK] Deleted existing moves\n")

    # Re-import with correct column order
    print("Re-importing moves with correct column order...")

    # Import corrected data
    from import_lore_characters import import_alicia, import_hinobi

    await db.close()

    # Run imports (they open their own connections)
    print("\nImporting Alicia...")
    await import_alicia()
    print("\nImporting Hinobi...")
    await import_hinobi()

    print("\n[SUCCESS] Re-import complete!")
    print("\nTest with: /move info Hinobi Storm Drummer")

if __name__ == "__main__":
    asyncio.run(main())
