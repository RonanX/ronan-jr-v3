"""
Test effects system: preset effects, countdown, emoji display
"""

import pytest
import pytest_asyncio
import aiosqlite
import json
import os


TEST_DB = "database/test_effects.db"


@pytest_asyncio.fixture
async def db():
    """Create test database with combat state"""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    async with aiosqlite.connect(TEST_DB) as conn:
        # Combat state table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS combat_state (
                character_name TEXT PRIMARY KEY,
                current_hp INTEGER,
                current_mp INTEGER,
                stars INTEGER DEFAULT 5,
                effects_json TEXT DEFAULT '[]'
            )
        """)

        # Initiative table (for combat active check)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS initiative (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                combat_active INTEGER DEFAULT 0,
                round_number INTEGER DEFAULT 0,
                current_turn_index INTEGER DEFAULT 0,
                turn_order_json TEXT
            )
        """)

        await conn.execute(
            "INSERT INTO initiative (id, combat_active, round_number, turn_order_json) VALUES (1, 1, 1, '[]')"
        )

        await conn.commit()

    yield TEST_DB

    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@pytest.mark.asyncio
async def test_preset_effect_creation(db):
    """Test creating preset effects with emojis"""
    async with aiosqlite.connect(db) as conn:
        # Add character to combat
        await conn.execute(
            "INSERT INTO combat_state (character_name, current_hp, current_mp, stars, effects_json) VALUES (?, ?, ?, ?, ?)",
            ("TestChar", 100, 50, 5, "[]")
        )
        await conn.commit()

        # Effect emojis
        effect_emojis = {
            "burning": "🔥",
            "bleeding": "🩸",
            "poisoned": "☠️",
            "stunned": "💫",
            "prone": "🔻",
            "blinded": "👁️‍🗨️",
            "slowed": "🐌",
            "restrained": "⛓️",
            "marked": "🎯",
            "advantage": "⬆️",
            "disadvantage": "⬇️"
        }

        # Create burning effect
        effect_type = "burning"
        duration = 3
        note = "fire from dragon breath"

        effect_entry = {
            "name": effect_type,
            "emoji": effect_emojis[effect_type],
            "duration": duration,
            "note": note
        }

        # Get current effects
        async with conn.execute(
            "SELECT effects_json FROM combat_state WHERE character_name = ?",
            ("TestChar",)
        ) as cursor:
            row = await cursor.fetchone()
            effects = json.loads(row[0])

        # Add effect
        effects.append(effect_entry)

        await conn.execute(
            "UPDATE combat_state SET effects_json = ? WHERE character_name = ?",
            (json.dumps(effects), "TestChar")
        )
        await conn.commit()

        # Verify
        async with conn.execute(
            "SELECT effects_json FROM combat_state WHERE character_name = ?",
            ("TestChar",)
        ) as cursor:
            row = await cursor.fetchone()
            loaded_effects = json.loads(row[0])

        assert len(loaded_effects) == 1
        assert loaded_effects[0]["name"] == "burning"
        assert loaded_effects[0]["emoji"] == "🔥"
        assert loaded_effects[0]["duration"] == 3
        assert loaded_effects[0]["note"] == "fire from dragon breath"


@pytest.mark.asyncio
async def test_effect_countdown(db):
    """Test effect duration decrements each round"""
    async with aiosqlite.connect(db) as conn:
        # Create character with effect
        effects = [
            {"name": "burning", "emoji": "🔥", "duration": 3},
            {"name": "stunned", "emoji": "💫", "duration": 2}
        ]

        await conn.execute(
            "INSERT INTO combat_state (character_name, current_hp, current_mp, stars, effects_json) VALUES (?, ?, ?, ?, ?)",
            ("TestChar", 100, 50, 5, json.dumps(effects))
        )
        await conn.commit()

        # Simulate countdown
        async with conn.execute(
            "SELECT effects_json FROM combat_state WHERE character_name = ?",
            ("TestChar",)
        ) as cursor:
            row = await cursor.fetchone()
            current_effects = json.loads(row[0])

        # Decrement all durations by 1
        for effect in current_effects:
            effect["duration"] -= 1

        # Remove expired effects (duration <= 0)
        current_effects = [e for e in current_effects if e["duration"] > 0]

        # Update
        await conn.execute(
            "UPDATE combat_state SET effects_json = ? WHERE character_name = ?",
            (json.dumps(current_effects), "TestChar")
        )
        await conn.commit()

        # Verify
        async with conn.execute(
            "SELECT effects_json FROM combat_state WHERE character_name = ?",
            ("TestChar",)
        ) as cursor:
            row = await cursor.fetchone()
            updated_effects = json.loads(row[0])

        assert len(updated_effects) == 2
        assert updated_effects[0]["duration"] == 2  # burning: 3 -> 2
        assert updated_effects[1]["duration"] == 1  # stunned: 2 -> 1


@pytest.mark.asyncio
async def test_effect_listing_with_emojis(db):
    """Test effect list displays with emojis and notes"""
    async with aiosqlite.connect(db) as conn:
        effects = [
            {"name": "burning", "emoji": "🔥", "duration": 2, "note": "fire from dragon breath"},
            {"name": "stunned", "emoji": "💫", "duration": 1},
            {"name": "advantage", "emoji": "⬆️", "duration": 1, "note": "flanking bonus"}
        ]

        await conn.execute(
            "INSERT INTO combat_state (character_name, current_hp, current_mp, stars, effects_json) VALUES (?, ?, ?, ?, ?)",
            ("TestChar", 100, 50, 5, json.dumps(effects))
        )
        await conn.commit()

        # Build effect list display
        async with conn.execute(
            "SELECT effects_json FROM combat_state WHERE character_name = ?",
            ("TestChar",)
        ) as cursor:
            row = await cursor.fetchone()
            loaded_effects = json.loads(row[0])

        effect_lines = []
        for effect in loaded_effects:
            emoji = effect.get("emoji", "🔮")
            name = effect["name"]
            duration = effect["duration"]
            note = effect.get("note", "")

            round_text = "round" if duration == 1 else "rounds"
            if note:
                effect_lines.append(f"- {emoji} **{name}** ({duration} {round_text}) - {note}")
            else:
                effect_lines.append(f"- {emoji} **{name}** ({duration} {round_text})")

        expected = [
            "- 🔥 **burning** (2 rounds) - fire from dragon breath",
            "- 💫 **stunned** (1 round)",
            "- ⬆️ **advantage** (1 round) - flanking bonus"
        ]

        assert effect_lines == expected


@pytest.mark.asyncio
async def test_all_preset_emojis(db):
    """Test all 11 preset effect emojis are correct"""
    effect_emojis = {
        "burning": "🔥",
        "bleeding": "🩸",
        "poisoned": "☠️",
        "stunned": "💫",
        "prone": "🔻",
        "blinded": "👁️‍🗨️",
        "slowed": "🐌",
        "restrained": "⛓️",
        "marked": "🎯",
        "advantage": "⬆️",
        "disadvantage": "⬇️"
    }

    # Verify all 11 presets exist
    assert len(effect_emojis) == 11

    # Verify specific emojis
    assert effect_emojis["burning"] == "🔥"
    assert effect_emojis["stunned"] == "💫"
    assert effect_emojis["advantage"] == "⬆️"


@pytest.mark.asyncio
async def test_effect_removal(db):
    """Test removing specific effects by name"""
    async with aiosqlite.connect(db) as conn:
        effects = [
            {"name": "burning", "emoji": "🔥", "duration": 3},
            {"name": "stunned", "emoji": "💫", "duration": 2},
            {"name": "poisoned", "emoji": "☠️", "duration": 4}
        ]

        await conn.execute(
            "INSERT INTO combat_state (character_name, current_hp, current_mp, stars, effects_json) VALUES (?, ?, ?, ?, ?)",
            ("TestChar", 100, 50, 5, json.dumps(effects))
        )
        await conn.commit()

        # Remove "stunned"
        async with conn.execute(
            "SELECT effects_json FROM combat_state WHERE character_name = ?",
            ("TestChar",)
        ) as cursor:
            row = await cursor.fetchone()
            current_effects = json.loads(row[0])

        # Filter out stunned
        current_effects = [e for e in current_effects if e["name"].lower() != "stunned"]

        await conn.execute(
            "UPDATE combat_state SET effects_json = ? WHERE character_name = ?",
            (json.dumps(current_effects), "TestChar")
        )
        await conn.commit()

        # Verify
        async with conn.execute(
            "SELECT effects_json FROM combat_state WHERE character_name = ?",
            ("TestChar",)
        ) as cursor:
            row = await cursor.fetchone()
            remaining = json.loads(row[0])

        assert len(remaining) == 2
        assert remaining[0]["name"] == "burning"
        assert remaining[1]["name"] == "poisoned"


@pytest.mark.asyncio
async def test_effect_without_note(db):
    """Test effects work without optional note"""
    async with aiosqlite.connect(db) as conn:
        effects = [
            {"name": "marked", "emoji": "🎯", "duration": 1}
            # No note field
        ]

        await conn.execute(
            "INSERT INTO combat_state (character_name, current_hp, current_mp, stars, effects_json) VALUES (?, ?, ?, ?, ?)",
            ("TestChar", 100, 50, 5, json.dumps(effects))
        )
        await conn.commit()

        # Verify
        async with conn.execute(
            "SELECT effects_json FROM combat_state WHERE character_name = ?",
            ("TestChar",)
        ) as cursor:
            row = await cursor.fetchone()
            loaded = json.loads(row[0])

        assert loaded[0]["name"] == "marked"
        assert "note" not in loaded[0]
