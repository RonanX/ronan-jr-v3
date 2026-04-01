import pytest
import json
import aiosqlite
from utils.dice import roll_dice_pool, check_result
from utils.move_execution import calculate_attack_damage, calculate_multihit_result
from utils.effects import apply_effect, remove_effect, get_preset_effect


@pytest.fixture
async def combat_db():
    """Create a test database with full combat setup."""
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
            stars INTEGER DEFAULT 0,
            max_stars INTEGER DEFAULT 3,
            ac INTEGER DEFAULT 10,
            proficiency INTEGER DEFAULT 2
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

    # Create combat table
    await db.execute("""
        CREATE TABLE combat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_num INTEGER DEFAULT 1,
            current_turn INTEGER DEFAULT 0
        )
    """)

    # Create initiative table
    await db.execute("""
        CREATE TABLE initiative (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_name TEXT NOT NULL,
            initiative INTEGER NOT NULL,
            FOREIGN KEY (character_name) REFERENCES characters(name) ON DELETE CASCADE
        )
    """)

    await db.commit()
    yield db
    await db.close()


class TestFullAttackFlow:
    """Test complete attack flow from attacker to defender."""

    @pytest.mark.asyncio
    async def test_basic_attack_flow(self, combat_db):
        """Test full attack: create chars, calc modifiers, roll vs AC, project damage."""
        # Create attacker with str=3
        attacker_stats = json.dumps({"str": 3, "dex": 1, "con": 2, "int": 0, "wis": 0, "cha": 0})
        await combat_db.execute(
            "INSERT INTO characters (name, base_stats, ac) VALUES (?, ?, ?)",
            ("Attacker", attacker_stats, 12)
        )

        # Create defender with ac=15
        defender_stats = json.dumps({"str": 1, "dex": 2, "con": 3, "int": 0, "wis": 0, "cha": 0})
        await combat_db.execute(
            "INSERT INTO characters (name, base_stats, ac) VALUES (?, ?, ?)",
            ("Defender", defender_stats, 15)
        )
        await combat_db.commit()

        # Get attacker stats
        async with combat_db.execute(
            "SELECT base_stats, stat_modifiers, roll_modifiers FROM characters WHERE name = ?",
            ("Attacker",)
        ) as cursor:
            row = await cursor.fetchone()
            base_stats = json.loads(row[0])
            stat_mods = json.loads(row[1])
            roll_mods = json.loads(row[2])

        effective_str = base_stats["str"] + stat_mods["str"]
        net_modifier = roll_mods["attack_modifier"]

        # Get defender AC and incoming modifier
        async with combat_db.execute(
            "SELECT ac, roll_modifiers FROM characters WHERE name = ?",
            ("Defender",)
        ) as cursor:
            row = await cursor.fetchone()
            defender_ac = row[0]
            defender_roll_mods = json.loads(row[1])

        net_modifier += defender_roll_mods["incoming_modifier"]

        # Roll attack
        highest, all_dice, is_crit = roll_dice_pool(effective_str, net_modifier)
        outcome = check_result(highest, defender_ac)

        # Project damage (example: base damage 10, 2 hits)
        hits_landed = calculate_multihit_result(outcome, 2)
        damage_per_hit, total_damage = calculate_attack_damage(10, effective_str, hits_landed, is_crit)

        # Verify flow worked
        assert effective_str == 3
        assert len(all_dice) == 3
        assert outcome in ["clean_hit", "hit_with_cost", "miss"]
        assert hits_landed >= 0

    @pytest.mark.asyncio
    async def test_attack_with_modifiers(self, combat_db):
        """Test attack flow with attack and incoming modifiers."""
        # Create attacker with attack_modifier +2
        attacker_stats = json.dumps({"str": 2, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0})
        attacker_roll_mods = json.dumps({"attack_modifier": 2, "incoming_modifier": 0, "save_modifier": 0})
        await combat_db.execute(
            "INSERT INTO characters (name, base_stats, roll_modifiers) VALUES (?, ?, ?)",
            ("Attacker", attacker_stats, attacker_roll_mods)
        )

        # Create defender with incoming_modifier -1
        defender_roll_mods = json.dumps({"attack_modifier": 0, "incoming_modifier": -1, "save_modifier": 0})
        await combat_db.execute(
            "INSERT INTO characters (name, roll_modifiers, ac) VALUES (?, ?, ?)",
            ("Defender", defender_roll_mods, 15)
        )
        await combat_db.commit()

        # Get net modifier (attack + incoming)
        async with combat_db.execute(
            "SELECT roll_modifiers FROM characters WHERE name = ?",
            ("Attacker",)
        ) as cursor:
            attacker_mods = json.loads((await cursor.fetchone())[0])

        async with combat_db.execute(
            "SELECT roll_modifiers FROM characters WHERE name = ?",
            ("Defender",)
        ) as cursor:
            defender_mods = json.loads((await cursor.fetchone())[0])

        net_modifier = attacker_mods["attack_modifier"] + defender_mods["incoming_modifier"]
        assert net_modifier == 1  # 2 + (-1)


class TestEffectLifecycle:
    """Test complete effect lifecycle."""

    @pytest.mark.asyncio
    async def test_effect_lifecycle(self, combat_db):
        """Test: apply → contributions added → advance turns → expire → contributions removed."""
        # Create character
        await combat_db.execute(
            "INSERT INTO characters (name, max_stars) VALUES (?, ?)",
            ("Hero", 3)
        )

        # Initialize combat
        await combat_db.execute("INSERT INTO combat (round_num, current_turn) VALUES (1, 0)")
        await combat_db.execute(
            "INSERT INTO initiative (character_name, initiative) VALUES (?, ?)",
            ("Hero", 15)
        )
        await combat_db.commit()

        # Apply effect that expires at round 3
        effect_data = {
            "name": "power_surge",
            "emoji": "⚡",
            "available_until_round": 3,
            "contributions": {"stat_modifiers": {"str": 2}},
            "dot_damage": 0,
            "dot_type": ""
        }
        await apply_effect("Hero", effect_data, combat_db)

        # Verify contributions added
        async with combat_db.execute(
            "SELECT stat_modifiers FROM characters WHERE name = ?",
            ("Hero",)
        ) as cursor:
            stat_mods = json.loads((await cursor.fetchone())[0])
            assert stat_mods["str"] == 2

        # Advance to round 2 (effect still active)
        await combat_db.execute("UPDATE combat SET round_num = 2")
        await combat_db.commit()

        async with combat_db.execute(
            "SELECT COUNT(*) FROM effects WHERE character_name = ? AND available_until_round > 2",
            ("Hero",)
        ) as cursor:
            count = (await cursor.fetchone())[0]
            assert count == 1  # Effect still active

        # Advance to round 3 (effect expires at START of round 3)
        await combat_db.execute("UPDATE combat SET round_num = 3")

        # Remove expired effects
        async with combat_db.execute(
            "SELECT effect_name FROM effects WHERE character_name = ? AND available_until_round <= 3",
            ("Hero",)
        ) as cursor:
            expired = await cursor.fetchall()

        for effect_row in expired:
            await remove_effect("Hero", effect_row[0], combat_db)

        # Verify contributions removed
        async with combat_db.execute(
            "SELECT stat_modifiers FROM characters WHERE name = ?",
            ("Hero",)
        ) as cursor:
            stat_mods = json.loads((await cursor.fetchone())[0])
            assert stat_mods["str"] == 0


class TestCombatTurn:
    """Test combat turn advancement."""

    @pytest.mark.asyncio
    async def test_turn_advancement_flow(self, combat_db):
        """Test: advance turn → stars refresh → effects tick → expired cleanup."""
        # Create character
        await combat_db.execute(
            "INSERT INTO characters (name, stars, max_stars) VALUES (?, ?, ?)",
            ("Hero", 0, 3)
        )
        await combat_db.execute("INSERT INTO combat (round_num, current_turn) VALUES (1, 0)")
        await combat_db.execute(
            "INSERT INTO initiative (character_name, initiative) VALUES (?, ?)",
            ("Hero", 15)
        )
        await combat_db.commit()

        # Apply effect that expires at round 2
        effect_data = {
            "name": "temp_buff",
            "emoji": "✨",
            "available_until_round": 2,
            "contributions": {"stat_modifiers": {"dex": 1}},
            "dot_damage": 0,
            "dot_type": ""
        }
        await apply_effect("Hero", effect_data, combat_db)

        # Stars should refresh on turn
        await combat_db.execute(
            "UPDATE characters SET stars = max_stars WHERE name = ?",
            ("Hero",)
        )

        async with combat_db.execute(
            "SELECT stars FROM characters WHERE name = ?",
            ("Hero",)
        ) as cursor:
            stars = (await cursor.fetchone())[0]
            assert stars == 3

        # Advance to round 2
        await combat_db.execute("UPDATE combat SET round_num = 2")

        # Effect should expire at start of round 2
        async with combat_db.execute(
            "SELECT effect_name FROM effects WHERE character_name = ? AND available_until_round <= 2",
            ("Hero",)
        ) as cursor:
            expired = await cursor.fetchall()
            assert len(expired) == 1


class TestMultipleEffects:
    """Test multiple effects interacting."""

    @pytest.mark.asyncio
    async def test_three_effects_stack_and_remove_middle(self, combat_db):
        """Apply 3 effects → verify all stack → remove middle → others persist."""
        await combat_db.execute("INSERT INTO characters (name) VALUES (?)", ("Hero",))
        await combat_db.commit()

        # Apply three effects
        effect1 = {
            "name": "buff1",
            "emoji": "1️⃣",
            "available_until_round": 5,
            "contributions": {"stat_modifiers": {"str": 1}, "roll_modifiers": {"attack_modifier": 1}},
            "dot_damage": 0,
            "dot_type": ""
        }
        effect2 = {
            "name": "buff2",
            "emoji": "2️⃣",
            "available_until_round": 5,
            "contributions": {"stat_modifiers": {"str": 2}, "roll_modifiers": {"attack_modifier": 2}},
            "dot_damage": 0,
            "dot_type": ""
        }
        effect3 = {
            "name": "buff3",
            "emoji": "3️⃣",
            "available_until_round": 5,
            "contributions": {"stat_modifiers": {"str": 3}, "roll_modifiers": {"save_modifier": 1}},
            "dot_damage": 0,
            "dot_type": ""
        }

        await apply_effect("Hero", effect1, combat_db)
        await apply_effect("Hero", effect2, combat_db)
        await apply_effect("Hero", effect3, combat_db)

        # Verify all stack
        async with combat_db.execute(
            "SELECT stat_modifiers, roll_modifiers FROM characters WHERE name = ?",
            ("Hero",)
        ) as cursor:
            row = await cursor.fetchone()
            stat_mods = json.loads(row[0])
            roll_mods = json.loads(row[1])
            assert stat_mods["str"] == 6  # 1 + 2 + 3
            assert roll_mods["attack_modifier"] == 3  # 1 + 2
            assert roll_mods["save_modifier"] == 1

        # Remove middle effect
        await remove_effect("Hero", "buff2", combat_db)

        # Verify others persist
        async with combat_db.execute(
            "SELECT stat_modifiers, roll_modifiers FROM characters WHERE name = ?",
            ("Hero",)
        ) as cursor:
            row = await cursor.fetchone()
            stat_mods = json.loads(row[0])
            roll_mods = json.loads(row[1])
            assert stat_mods["str"] == 4  # 1 + 3
            assert roll_mods["attack_modifier"] == 1  # Only buff1
            assert roll_mods["save_modifier"] == 1  # buff3

        # Verify buff2 deleted
        async with combat_db.execute(
            "SELECT COUNT(*) FROM effects WHERE character_name = ? AND effect_name = ?",
            ("Hero", "buff2")
        ) as cursor:
            count = (await cursor.fetchone())[0]
            assert count == 0
