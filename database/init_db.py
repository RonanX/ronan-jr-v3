"""
Database initialization for Ronan Jr v3
Uses SQLite for local storage (no Firebase needed!)
"""

import aiosqlite
import logging

logger = logging.getLogger(__name__)

DATABASE_PATH = "database/ronan.db"

async def init_database():
    """Initialize database with required tables"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Characters table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                name TEXT PRIMARY KEY,
                hp INTEGER NOT NULL,
                max_hp INTEGER NOT NULL,
                mp INTEGER NOT NULL,
                max_mp INTEGER NOT NULL,
                ac INTEGER NOT NULL,
                movement INTEGER DEFAULT 30,
                proficiency INTEGER DEFAULT 2,
                stats_json TEXT NOT NULL,
                current_form TEXT DEFAULT 'base',
                base_stats_json TEXT,
                base_stats TEXT,
                stat_modifiers TEXT,
                roll_modifiers TEXT,
                max_stars INTEGER DEFAULT 3,
                current_stars INTEGER,
                temp_hp INTEGER DEFAULT 0,
                temp_mp INTEGER DEFAULT 0,
                temp_stars INTEGER DEFAULT 0,
                ac_modifier INTEGER DEFAULT 0,
                ac_modifier_source TEXT,
                threshold_damage INTEGER,
                threshold_dc INTEGER,
                hidden_resources INTEGER DEFAULT 0,
                squishy INTEGER DEFAULT 0,
                tier TEXT,
                grunt INTEGER DEFAULT 0
            )
        """)

        # Forms table (for transformations)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS forms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_name TEXT NOT NULL,
                form_name TEXT NOT NULL,
                stats_json TEXT NOT NULL,
                UNIQUE(character_name, form_name),
                FOREIGN KEY (character_name) REFERENCES characters(name) ON DELETE CASCADE
            )
        """)

        # Movesets table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS movesets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_name TEXT NOT NULL,
                form_name TEXT DEFAULT 'base',
                moves_json TEXT NOT NULL,
                UNIQUE(character_name, form_name),
                FOREIGN KEY (character_name) REFERENCES characters(name) ON DELETE CASCADE
            )
        """)

        # Initiative tracker table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS initiative (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                combat_active INTEGER DEFAULT 0,
                round_number INTEGER DEFAULT 0,
                current_turn_index INTEGER DEFAULT 0,
                turn_order_json TEXT
            )
        """)

        # Initialize initiative row if it doesn't exist
        await db.execute("""
            INSERT OR IGNORE INTO initiative (id, combat_active, round_number, current_turn_index, turn_order_json)
            VALUES (1, 0, 0, 0, '[]')
        """)

        # Combat state table (stars and effects per character in combat)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS combat_state (
                character_name TEXT PRIMARY KEY,
                current_hp INTEGER,
                current_mp INTEGER,
                stars INTEGER DEFAULT 5,
                effects_json TEXT DEFAULT '[]'
            )
        """)
        # Deployables table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS deployables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deployable_name TEXT NOT NULL,
                owner_name TEXT NOT NULL,
                hp INTEGER NOT NULL,
                max_hp INTEGER NOT NULL,
                stars INTEGER NOT NULL,
                max_stars INTEGER NOT NULL,
                available_until_round INTEGER NOT NULL,
                created_round INTEGER NOT NULL,
                ac INTEGER DEFAULT 10,
                archetype TEXT DEFAULT 'Balanced',
                mp INTEGER DEFAULT 0,
                max_mp INTEGER DEFAULT 0,
                hidden_resources INTEGER DEFAULT 0
            )
        """)

        await db.commit()
        logger.info("Database initialized successfully!")

async def get_db():
    """Get database connection"""
    return await aiosqlite.connect(DATABASE_PATH)

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_database())
    print("Database initialized!")
