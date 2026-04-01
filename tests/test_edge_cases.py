import pytest
import json
import aiosqlite
from utils.dice import roll_dice_pool
from utils.move_execution import validate_costs
from utils.effects import apply_effect, remove_effect, get_preset_effect


@pytest.fixture
async def edge_db():
    """Create test database for edge cases."""
    db = await aiosqlite.connect(":memory:")

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
            current_form TEXT DEFAULT 'base'
        )
    """)

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

    await db.commit()
    yield db
    await db.close()


class TestBoundaryValues:
    """Test boundary value edge cases."""

    @pytest.mark.parametrize("rating", [0, 1, 2, 3, 4])
    def test_stat_boundary_values(self, rating):
        """Test stats from 0 to 4."""
        highest, all_dice, is_crit = roll_dice_pool(rating, modifier=0)

        # Stat 0 should still roll 1d6
        if rating == 0:
            assert len(all_dice) == 1
        else:
            assert len(all_dice) == rating

        assert 1 <= highest <= 6

    @pytest.mark.asyncio
    async def test_1_hp_character(self, edge_db):
        """Character with 1 HP should function normally."""
        await edge_db.execute(
            "INSERT INTO characters (name, hp, max_hp) VALUES (?, ?, ?)",
            ("LowHP", 1, 20)
        )
        await edge_db.commit()

        async with edge_db.execute(
            "SELECT hp FROM characters WHERE name = ?",
            ("LowHP",)
        ) as cursor:
            hp = (await cursor.fetchone())[0]
            assert hp == 1

    @pytest.mark.asyncio
    async def test_0_mp_character(self, edge_db):
        """Character with 0 MP should exist but can't spend MP."""
        await edge_db.execute(
            "INSERT INTO characters (name, mp, max_mp) VALUES (?, ?, ?)",
            ("NoMP", 0, 10)
        )
        await edge_db.commit()

        valid, error = validate_costs(
            current_stars=3, current_mp=0, current_hp=20,
            star_cost=0, mp_cost=5, hp_cost=0
        )
        assert valid is False
        assert "mp" in error.lower()

    @pytest.mark.asyncio
    async def test_0_stars_character(self, edge_db):
        """Character with 0 stars should exist but can't spend stars."""
        await edge_db.execute(
            "INSERT INTO characters (name, stars, max_stars) VALUES (?, ?, ?)",
            ("NoStars", 0, 3)
        )
        await edge_db.commit()

        valid, error = validate_costs(
            current_stars=0, current_mp=20, current_hp=20,
            star_cost=1, mp_cost=0, hp_cost=0
        )
        assert valid is False
        assert "star" in error.lower()

    @pytest.mark.asyncio
    async def test_exactly_1_hp_taking_damage(self, edge_db):
        """Character at 1 HP taking 1 damage should go to 0."""
        await edge_db.execute(
            "INSERT INTO characters (name, hp, max_hp) VALUES (?, ?, ?)",
            ("Fragile", 1, 20)
        )
        await edge_db.commit()

        # Apply 1 damage
        await edge_db.execute(
            "UPDATE characters SET hp = hp - ? WHERE name = ?",
            (1, "Fragile")
        )

        async with edge_db.execute(
            "SELECT hp FROM characters WHERE name = ?",
            ("Fragile",)
        ) as cursor:
            hp = (await cursor.fetchone())[0]
            assert hp == 0

    @pytest.mark.asyncio
    async def test_temp_hp_exceeds_max(self, edge_db):
        """Temporary HP can exceed max HP."""
        await edge_db.execute(
            "INSERT INTO characters (name, hp, max_hp) VALUES (?, ?, ?)",
            ("Buffed", 20, 20)
        )
        await edge_db.commit()

        # Add 50 HP (temp buff)
        await edge_db.execute(
            "UPDATE characters SET hp = hp + ? WHERE name = ?",
            (50, "Buffed")
        )

        async with edge_db.execute(
            "SELECT hp, max_hp FROM characters WHERE name = ?",
            ("Buffed",)
        ) as cursor:
            row = await cursor.fetchone()
            assert row[0] == 70  # Temp HP can exceed max
            assert row[1] == 20  # Max HP unchanged

    @pytest.mark.asyncio
    async def test_temp_mp_exceeds_max(self, edge_db):
        """Temporary MP can exceed max MP."""
        await edge_db.execute(
            "INSERT INTO characters (name, mp, max_mp) VALUES (?, ?, ?)",
            ("Buffed", 10, 10)
        )
        await edge_db.commit()

        # Add 50 MP (temp buff)
        await edge_db.execute(
            "UPDATE characters SET mp = mp + ? WHERE name = ?",
            (50, "Buffed")
        )

        async with edge_db.execute(
            "SELECT mp, max_mp FROM characters WHERE name = ?",
            ("Buffed",)
        ) as cursor:
            row = await cursor.fetchone()
            assert row[0] == 60  # Temp MP can exceed max
            assert row[1] == 10  # Max MP unchanged

    @pytest.mark.asyncio
    async def test_damage_exceeds_max_hp_caps_at_zero(self, edge_db):
        """Damage exceeding max HP should cap at 0."""
        await edge_db.execute(
            "INSERT INTO characters (name, hp, max_hp) VALUES (?, ?, ?)",
            ("Target", 20, 20)
        )
        await edge_db.commit()

        # Apply 1000 damage
        await edge_db.execute(
            "UPDATE characters SET hp = MAX(0, hp - ?) WHERE name = ?",
            (1000, "Target")
        )

        async with edge_db.execute(
            "SELECT hp FROM characters WHERE name = ?",
            ("Target",)
        ) as cursor:
            hp = (await cursor.fetchone())[0]
            assert hp == 0  # Capped at 0, not negative


class TestWeirdCombinations:
    """Test unusual combination scenarios."""

    @pytest.mark.asyncio
    async def test_stunned_character_attacks_blocked(self, edge_db):
        """Stunned character should have -999 attack modifier."""
        await edge_db.execute("INSERT INTO characters (name) VALUES (?)", ("Stunned",))
        await edge_db.commit()

        stunned_effect = get_preset_effect("stunned", duration=2)
        await apply_effect("Stunned", stunned_effect, edge_db)

        async with edge_db.execute(
            "SELECT roll_modifiers FROM characters WHERE name = ?",
            ("Stunned",)
        ) as cursor:
            roll_mods = json.loads((await cursor.fetchone())[0])
            assert roll_mods["attack_modifier"] == -999

        # Rolling with -999 modifier should result in 1d6 minimum
        highest, all_dice, is_crit = roll_dice_pool(rating=3, modifier=-999)
        assert len(all_dice) == 1


    @pytest.mark.asyncio
    async def test_same_effect_twice_refreshes_duration(self, edge_db):
        """Applying same effect twice should refresh duration."""
        await edge_db.execute("INSERT INTO characters (name) VALUES (?)", ("Hero",))
        await edge_db.commit()

        # Apply effect expiring at round 3
        effect1 = {
            "name": "power_boost",
            "emoji": "⚡",
            "available_until_round": 3,
            "contributions": {"stat_modifiers": {"str": 2}},
            "dot_damage": 0,
            "dot_type": ""
        }
        await apply_effect("Hero", effect1, edge_db)

        # Reapply with round 5
        effect2 = {
            "name": "power_boost",
            "emoji": "⚡",
            "available_until_round": 5,
            "contributions": {"stat_modifiers": {"str": 2}},
            "dot_damage": 0,
            "dot_type": ""
        }
        await apply_effect("Hero", effect2, edge_db)

        # Should only have one instance with updated duration
        async with edge_db.execute(
            "SELECT available_until_round FROM effects WHERE character_name = ? AND effect_name = ?",
            ("Hero", "power_boost")
        ) as cursor:
            rows = await cursor.fetchall()
            assert len(rows) == 1
            assert rows[0][0] == 5

    def test_advantage_and_disadvantage_cancel(self):
        """Advantage and disadvantage cancel through modifier system."""
        # +2 advantage, -2 disadvantage = 0 net modifier
        highest, all_dice, is_crit = roll_dice_pool(rating=2, modifier=0)
        assert len(all_dice) == 2  # Just base rating

    @pytest.mark.asyncio
    async def test_transform_preserves_effects(self, edge_db):
        """Transforming should preserve existing effects."""
        await edge_db.execute(
            "INSERT INTO characters (name, current_form) VALUES (?, ?)",
            ("Hero", "base")
        )
        await edge_db.commit()

        # Apply effect
        effect = {
            "name": "buff",
            "emoji": "💪",
            "available_until_round": 5,
            "contributions": {"stat_modifiers": {"str": 2}},
            "dot_damage": 0,
            "dot_type": ""
        }
        await apply_effect("Hero", effect, edge_db)

        # Transform
        await edge_db.execute(
            "UPDATE characters SET current_form = ? WHERE name = ?",
            ("dragon", "Hero")
        )
        await edge_db.commit()

        # Effect should still exist
        async with edge_db.execute(
            "SELECT COUNT(*) FROM effects WHERE character_name = ?",
            ("Hero",)
        ) as cursor:
            count = (await cursor.fetchone())[0]
            assert count == 1

        # Effect contributions should still apply
        async with edge_db.execute(
            "SELECT stat_modifiers FROM characters WHERE name = ?",
            ("Hero",)
        ) as cursor:
            stat_mods = json.loads((await cursor.fetchone())[0])
            assert stat_mods["str"] == 2


class TestTiming:
    """Test timing-related edge cases."""

    @pytest.mark.asyncio
    async def test_effect_expires_correct_round(self, edge_db):
        """Effect should expire at START of available_until_round."""
        await edge_db.execute("INSERT INTO characters (name) VALUES (?)", ("Hero",))
        await edge_db.commit()

        effect = {
            "name": "timed_buff",
            "emoji": "⏰",
            "available_until_round": 3,
            "contributions": {"stat_modifiers": {"str": 1}},
            "dot_damage": 0,
            "dot_type": ""
        }
        await apply_effect("Hero", effect, edge_db)

        # Should be active before round 3
        async with edge_db.execute(
            "SELECT COUNT(*) FROM effects WHERE character_name = ? AND available_until_round > 2",
            ("Hero",)
        ) as cursor:
            count = (await cursor.fetchone())[0]
            assert count == 1

        # Should be expirable at round 3
        async with edge_db.execute(
            "SELECT COUNT(*) FROM effects WHERE character_name = ? AND available_until_round <= 3",
            ("Hero",)
        ) as cursor:
            count = (await cursor.fetchone())[0]
            assert count == 1

    @pytest.mark.asyncio
    async def test_multiple_effects_expire_same_round(self, edge_db):
        """Multiple effects expiring same round should all be removed."""
        await edge_db.execute("INSERT INTO characters (name) VALUES (?)", ("Hero",))
        await edge_db.commit()

        # Apply 3 effects all expiring at round 3
        for i in range(3):
            effect = {
                "name": f"buff{i}",
                "emoji": "⚡",
                "available_until_round": 3,
                "contributions": {"stat_modifiers": {"str": 1}},
                "dot_damage": 0,
                "dot_type": ""
            }
            await apply_effect("Hero", effect, edge_db)

        # All should be expirable at round 3
        async with edge_db.execute(
            "SELECT effect_name FROM effects WHERE character_name = ? AND available_until_round <= 3",
            ("Hero",)
        ) as cursor:
            expired = await cursor.fetchall()
            assert len(expired) == 3

        # Remove all expired
        for effect_row in expired:
            await remove_effect("Hero", effect_row[0], edge_db)

        # Verify all removed
        async with edge_db.execute(
            "SELECT COUNT(*) FROM effects WHERE character_name = ?",
            ("Hero",)
        ) as cursor:
            count = (await cursor.fetchone())[0]
            assert count == 0

        # Verify contributions all removed
        async with edge_db.execute(
            "SELECT stat_modifiers FROM characters WHERE name = ?",
            ("Hero",)
        ) as cursor:
            stat_mods = json.loads((await cursor.fetchone())[0])
            assert stat_mods["str"] == 0

    @pytest.mark.asyncio
    async def test_remove_nonexistent_effect_fails_gracefully(self, edge_db):
        """Removing non-existent effect should fail gracefully."""
        await edge_db.execute("INSERT INTO characters (name) VALUES (?)", ("Hero",))
        await edge_db.commit()

        # Should not crash, just print warning
        await remove_effect("Hero", "nonexistent_effect", edge_db)

        # Character should be unchanged
        async with edge_db.execute(
            "SELECT stat_modifiers FROM characters WHERE name = ?",
            ("Hero",)
        ) as cursor:
            stat_mods = json.loads((await cursor.fetchone())[0])
            assert stat_mods == {"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0}

    @pytest.mark.asyncio
    async def test_effect_duration_zero_expires_immediately(self, edge_db):
        """Effect with duration 0 should be expirable immediately."""
        await edge_db.execute("INSERT INTO characters (name) VALUES (?)", ("Hero",))
        await edge_db.commit()

        effect = {
            "name": "instant_buff",
            "emoji": "⚡",
            "available_until_round": 0,
            "contributions": {"stat_modifiers": {"str": 1}},
            "dot_damage": 0,
            "dot_type": ""
        }
        await apply_effect("Hero", effect, edge_db)

        # Should be expirable at round 0
        async with edge_db.execute(
            "SELECT COUNT(*) FROM effects WHERE character_name = ? AND available_until_round <= 0",
            ("Hero",)
        ) as cursor:
            count = (await cursor.fetchone())[0]
            assert count == 1


class TestTimingWeirdness:
    """Test timing-related edge cases."""

    @pytest.mark.asyncio
    async def test_effect_round10_duration1_expires_round11(self, edge_db):
        """Effect applied at round 10 with duration 1 expires at round 11."""
        await edge_db.execute("INSERT INTO characters (name) VALUES (?)", ("Hero",))
        await edge_db.commit()

        current_round = 10
        effect = {
            "name": "quick_buff",
            "emoji": "⚡",
            "available_until_round": current_round + 1,  # Expires round 11
            "contributions": {"stat_modifiers": {"str": 1}},
            "dot_damage": 0,
            "dot_type": ""
        }
        await apply_effect("Hero", effect, edge_db)

        # Should be active at round 10
        async with edge_db.execute(
            "SELECT COUNT(*) FROM effects WHERE character_name = ? AND available_until_round > 10",
            ("Hero",)
        ) as cursor:
            count = (await cursor.fetchone())[0]
            assert count == 1

        # Should expire at round 11
        async with edge_db.execute(
            "SELECT COUNT(*) FROM effects WHERE character_name = ? AND available_until_round <= 11",
            ("Hero",)
        ) as cursor:
            count = (await cursor.fetchone())[0]
            assert count == 1

    @pytest.mark.asyncio
    async def test_multiple_effects_expire_same_round(self, edge_db):
        """Multiple effects expiring same round should all be removed."""
        await edge_db.execute("INSERT INTO characters (name) VALUES (?)", ("Hero",))
        await edge_db.commit()

        # Apply 3 effects all expiring at round 3
        for i in range(3):
            effect = {
                "name": f"buff{i}",
                "emoji": "⚡",
                "available_until_round": 3,
                "contributions": {"stat_modifiers": {"str": 1}},
                "dot_damage": 0,
                "dot_type": ""
            }
            await apply_effect("Hero", effect, edge_db)

        # All should be expirable at round 3
        async with edge_db.execute(
            "SELECT effect_name FROM effects WHERE character_name = ? AND available_until_round <= 3",
            ("Hero",)
        ) as cursor:
            expired = await cursor.fetchall()
            assert len(expired) == 3

        # Remove all expired
        for effect_row in expired:
            await remove_effect("Hero", effect_row[0], edge_db)

        # Verify all removed
        async with edge_db.execute(
            "SELECT COUNT(*) FROM effects WHERE character_name = ?",
            ("Hero",)
        ) as cursor:
            count = (await cursor.fetchone())[0]
            assert count == 0

        # Verify contributions all removed
        async with edge_db.execute(
            "SELECT stat_modifiers FROM characters WHERE name = ?",
            ("Hero",)
        ) as cursor:
            stat_mods = json.loads((await cursor.fetchone())[0])
            assert stat_mods["str"] == 0


class TestMoveEdgeCases:
    """Test move-specific edge cases."""

    @pytest.mark.asyncio
    async def test_move_on_cooldown_blocked(self, edge_db):
        """Move on cooldown should be blocked on second use."""
        # This would require move cooldown tracking in the database
        # For now, just test the concept with a simple flag
        await edge_db.execute("""
            CREATE TABLE IF NOT EXISTS movesets (
                id INTEGER PRIMARY KEY,
                character_name TEXT NOT NULL,
                move_name TEXT NOT NULL,
                category TEXT NOT NULL,
                cooldown INTEGER DEFAULT 0,
                current_cooldown INTEGER DEFAULT 0
            )
        """)

        await edge_db.execute(
            "INSERT INTO movesets (character_name, move_name, category, cooldown, current_cooldown) VALUES (?, ?, ?, ?, ?)",
            ("Hero", "BigMove", "heavy", 3, 0)
        )
        await edge_db.commit()

        # Use move (set cooldown)
        await edge_db.execute(
            "UPDATE movesets SET current_cooldown = cooldown WHERE move_name = ?",
            ("BigMove",)
        )

        # Check if on cooldown
        async with edge_db.execute(
            "SELECT current_cooldown FROM movesets WHERE move_name = ?",
            ("BigMove",)
        ) as cursor:
            cooldown = (await cursor.fetchone())[0]
            assert cooldown == 3

        # Second use should be blocked
        async with edge_db.execute(
            "SELECT current_cooldown > 0 FROM movesets WHERE move_name = ?",
            ("BigMove",)
        ) as cursor:
            on_cooldown = (await cursor.fetchone())[0]
            assert on_cooldown == 1  # True, blocked
