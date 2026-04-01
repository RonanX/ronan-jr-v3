import pytest
import json
import aiosqlite
from utils.effects import apply_effect, remove_effect, get_preset_effect


@pytest.fixture
async def test_db():
    """Create a test database with characters and effects tables."""
    db = await aiosqlite.connect(":memory:")

    # Create characters table
    await db.execute("""
        CREATE TABLE characters (
            name TEXT PRIMARY KEY,
            base_stats TEXT DEFAULT '{"str":0,"dex":0,"con":0,"int":0,"wis":0,"cha":0}',
            stat_modifiers TEXT DEFAULT '{"str":0,"dex":0,"con":0,"int":0,"wis":0,"cha":0}',
            roll_modifiers TEXT DEFAULT '{"attack_modifier":0,"incoming_modifier":0,"save_modifier":0}',
            hp INTEGER DEFAULT 20,
            max_hp INTEGER DEFAULT 20,
            mp INTEGER DEFAULT 10,
            max_mp INTEGER DEFAULT 10,
            ac INTEGER DEFAULT 10
        )
    """)

    # Create effects table
    await db.execute("""
        CREATE TABLE effects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_name TEXT NOT NULL,
            effect_name TEXT NOT NULL,
            emoji TEXT DEFAULT '⚡',
            available_until_round INTEGER,
            contributions TEXT DEFAULT '{}',
            dot_damage INTEGER DEFAULT 0,
            dot_type TEXT DEFAULT '',
            FOREIGN KEY (character_name) REFERENCES characters(name) ON DELETE CASCADE
        )
    """)

    # Create test character
    await db.execute(
        "INSERT INTO characters (name) VALUES (?)",
        ("TestChar",)
    )
    await db.commit()

    yield db
    await db.close()


class TestEffectApplication:
    """Test applying effects to characters."""

    @pytest.mark.asyncio
    async def test_apply_effect_adds_contributions(self, test_db):
        """Applying an effect should add its contributions to character."""
        effect_data = {
            "name": "strength_boost",
            "emoji": "💪",
            "available_until_round": 5,
            "contributions": {"stat_modifiers": {"str": 2}},
            "dot_damage": 0,
            "dot_type": ""
        }

        await apply_effect("TestChar", effect_data, test_db)

        # Check character stat_modifiers
        async with test_db.execute(
            "SELECT stat_modifiers FROM characters WHERE name = ?",
            ("TestChar",)
        ) as cursor:
            row = await cursor.fetchone()
            stat_mods = json.loads(row[0])
            assert stat_mods["str"] == 2

    @pytest.mark.asyncio
    async def test_apply_multiple_effects_stack(self, test_db):
        """Multiple effects should stack numerically."""
        effect1 = {
            "name": "strength_boost",
            "emoji": "💪",
            "available_until_round": 5,
            "contributions": {"stat_modifiers": {"str": 2}},
            "dot_damage": 0,
            "dot_type": ""
        }
        effect2 = {
            "name": "agility_boost",
            "emoji": "🏃",
            "available_until_round": 5,
            "contributions": {"stat_modifiers": {"dex": 1, "str": 1}},
            "dot_damage": 0,
            "dot_type": ""
        }

        await apply_effect("TestChar", effect1, test_db)
        await apply_effect("TestChar", effect2, test_db)

        async with test_db.execute(
            "SELECT stat_modifiers FROM characters WHERE name = ?",
            ("TestChar",)
        ) as cursor:
            row = await cursor.fetchone()
            stat_mods = json.loads(row[0])
            assert stat_mods["str"] == 3  # 2 + 1
            assert stat_mods["dex"] == 1

    @pytest.mark.asyncio
    async def test_apply_effect_stores_in_database(self, test_db):
        """Applied effect should be stored in effects table."""
        effect_data = {
            "name": "test_effect",
            "emoji": "⚡",
            "available_until_round": 5,
            "contributions": {},
            "dot_damage": 5,
            "dot_type": "fire"
        }

        await apply_effect("TestChar", effect_data, test_db)

        async with test_db.execute(
            "SELECT effect_name, emoji, available_until_round, dot_damage, dot_type FROM effects WHERE character_name = ?",
            ("TestChar",)
        ) as cursor:
            row = await cursor.fetchone()
            assert row[0] == "test_effect"
            assert row[1] == "⚡"
            assert row[2] == 5
            assert row[3] == 5
            assert row[4] == "fire"


class TestEffectRemoval:
    """Test removing effects from characters."""

    @pytest.mark.asyncio
    async def test_remove_effect_subtracts_contributions(self, test_db):
        """Removing an effect should subtract its contributions."""
        effect_data = {
            "name": "strength_boost",
            "emoji": "💪",
            "available_until_round": 5,
            "contributions": {"stat_modifiers": {"str": 2}},
            "dot_damage": 0,
            "dot_type": ""
        }

        await apply_effect("TestChar", effect_data, test_db)
        await remove_effect("TestChar", "strength_boost", test_db)

        async with test_db.execute(
            "SELECT stat_modifiers FROM characters WHERE name = ?",
            ("TestChar",)
        ) as cursor:
            row = await cursor.fetchone()
            stat_mods = json.loads(row[0])
            assert stat_mods["str"] == 0

    @pytest.mark.asyncio
    async def test_remove_middle_effect_preserves_others(self, test_db):
        """Removing middle effect should preserve others."""
        effect1 = {
            "name": "effect1",
            "emoji": "1️⃣",
            "available_until_round": 5,
            "contributions": {"stat_modifiers": {"str": 1}},
            "dot_damage": 0,
            "dot_type": ""
        }
        effect2 = {
            "name": "effect2",
            "emoji": "2️⃣",
            "available_until_round": 5,
            "contributions": {"stat_modifiers": {"str": 2}},
            "dot_damage": 0,
            "dot_type": ""
        }
        effect3 = {
            "name": "effect3",
            "emoji": "3️⃣",
            "available_until_round": 5,
            "contributions": {"stat_modifiers": {"str": 3}},
            "dot_damage": 0,
            "dot_type": ""
        }

        await apply_effect("TestChar", effect1, test_db)
        await apply_effect("TestChar", effect2, test_db)
        await apply_effect("TestChar", effect3, test_db)

        # Remove middle effect
        await remove_effect("TestChar", "effect2", test_db)

        async with test_db.execute(
            "SELECT stat_modifiers FROM characters WHERE name = ?",
            ("TestChar",)
        ) as cursor:
            row = await cursor.fetchone()
            stat_mods = json.loads(row[0])
            assert stat_mods["str"] == 4  # 1 + 3, effect2 removed

        # Verify effects 1 and 3 still exist
        async with test_db.execute(
            "SELECT effect_name FROM effects WHERE character_name = ? ORDER BY effect_name",
            ("TestChar",)
        ) as cursor:
            rows = await cursor.fetchall()
            effect_names = [row[0] for row in rows]
            assert "effect1" in effect_names
            assert "effect2" not in effect_names
            assert "effect3" in effect_names


class TestPresetEffects:
    """Test preset effect definitions."""

    @pytest.mark.parametrize("effect_name,expected_fields", [
        ("burning", {"emoji": "🔥", "contributions": {}, "dot_damage": 5, "dot_type": "fire"}),
        ("stunned", {"emoji": "💫", "contributions": {"roll_modifiers": {"attack_modifier": -999}}}),
        ("advantage", {"emoji": "⬆️", "contributions": {"roll_modifiers": {"attack_modifier": 999}}}),
        ("disadvantage", {"emoji": "⬇️", "contributions": {"roll_modifiers": {"attack_modifier": -999}}}),
        ("poisoned", {"emoji": "🤢", "contributions": {}, "dot_damage": 3, "dot_type": "poison"}),
    ])
    def test_preset_effects(self, effect_name, expected_fields):
        """Test preset effects have correct structure."""
        effect = get_preset_effect(effect_name, duration=3)

        assert effect["name"] == effect_name
        assert effect["emoji"] == expected_fields["emoji"]
        assert effect["available_until_round"] == 3

        if "contributions" in expected_fields:
            for key, value in expected_fields["contributions"].items():
                assert effect["contributions"][key] == value

        if "dot_damage" in expected_fields:
            assert effect["dot_damage"] == expected_fields["dot_damage"]

        if "dot_type" in expected_fields:
            assert effect["dot_type"] == expected_fields["dot_type"]

    def test_stunned_prevents_attacks(self):
        """Stunned should have attack_modifier of -999."""
        effect = get_preset_effect("stunned", duration=2)
        assert effect["contributions"]["roll_modifiers"]["attack_modifier"] == -999

    def test_advantage_has_high_modifier(self):
        """Advantage should have attack_modifier of 999."""
        effect = get_preset_effect("advantage", duration=1)
        assert effect["contributions"]["roll_modifiers"]["attack_modifier"] == 999

    def test_burning_has_dot(self):
        """Burning should have fire DoT."""
        effect = get_preset_effect("burning", duration=3)
        assert effect["dot_damage"] == 5
        assert effect["dot_type"] == "fire"


class TestEffectTiming:
    """Test effect duration and expiry timing."""

    @pytest.mark.asyncio
    async def test_effect_expires_at_start_of_round(self, test_db):
        """Effect with available_until_round=5 should expire at START of round 5."""
        effect_data = {
            "name": "temp_boost",
            "emoji": "⏰",
            "available_until_round": 5,
            "contributions": {"stat_modifiers": {"str": 2}},
            "dot_damage": 0,
            "dot_type": ""
        }

        await apply_effect("TestChar", effect_data, test_db)

        # Effect should exist before round 5
        async with test_db.execute(
            "SELECT effect_name FROM effects WHERE character_name = ? AND available_until_round > ?",
            ("TestChar", 4)
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None

        # Effect should be expirable at round 5
        async with test_db.execute(
            "SELECT effect_name FROM effects WHERE character_name = ? AND available_until_round <= ?",
            ("TestChar", 5)
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
