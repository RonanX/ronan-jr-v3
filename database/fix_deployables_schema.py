"""
Fix deployables table schema - add owner_name column if missing
"""

import aiosqlite
import asyncio

DATABASE_PATH = "database/ronan.db"

async def fix_schema():
    """Add owner_name column to deployables table if it doesn't exist."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Check if owner_name column exists
        async with db.execute("PRAGMA table_info(deployables)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

        if "owner_name" in column_names:
            print("[INFO] owner_name column already exists, no changes needed")
        else:
            print("[FIX] Adding owner_name column to deployables table...")
            try:
                # Add the missing column (will be NULL for existing rows)
                await db.execute("""
                    ALTER TABLE deployables ADD COLUMN owner_name TEXT
                """)
                print("[SUCCESS] Added owner_name column")

                # Note: Existing deployable rows will have NULL owner_name
                # They should be deleted or manually updated
                async with db.execute("SELECT COUNT(*) FROM deployables WHERE owner_name IS NULL") as cursor:
                    null_count = await cursor.fetchone()
                    if null_count[0] > 0:
                        print(f"[WARNING] {null_count[0]} existing deployables have NULL owner_name")
                        print("[WARNING] Consider deleting them: DELETE FROM deployables WHERE owner_name IS NULL")

            except Exception as e:
                print(f"[ERROR] Failed to add column: {e}")
                return

        await db.commit()
        print("[OK] Deployables schema is correct")

if __name__ == "__main__":
    asyncio.run(fix_schema())
