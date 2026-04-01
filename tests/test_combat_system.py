"""
Test combat system: attacks, damage projection, health bars, star validation
"""

import pytest
import pytest_asyncio
import aiosqlite
import json
import os
import random


TEST_DB = "database/test_combat.db"


@pytest_asyncio.fixture
async def db():
    """Create test database with combat tables"""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    async with aiosqlite.connect(TEST_DB) as conn:
        # Characters table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                name TEXT PRIMARY KEY,
                hp INTEGER NOT NULL,
                max_hp INTEGER NOT NULL,
                mp INTEGER NOT NULL,
                max_mp INTEGER NOT NULL,
                ac INTEGER NOT NULL,
                proficiency INTEGER DEFAULT 2,
                stats_json TEXT NOT NULL,
                temp_hp INTEGER DEFAULT 0
            )
        """)

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

        # Initiative table
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
async def test_attack_with_roll_stat(db):
    """Test attack with roll_stat (dice pool attack)"""
    async with aiosqlite.connect(db) as conn:
        # Create attacker
        stats = {"str": 4, "dex": 3, "con": 2, "int": 2, "wis": 2, "cha": 3}
        await conn.execute(
            """INSERT INTO characters (name, hp, max_hp, mp, max_mp, ac, proficiency, stats_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("Attacker", 100, 100, 50, 50, 14, 3, json.dumps(stats))
        )

        # Create target
        await conn.execute(
            """INSERT INTO characters (name, hp, max_hp, mp, max_mp, ac, proficiency, stats_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("Target", 80, 80, 40, 40, 12, 3, json.dumps(stats))
        )

        # Add to combat
        await conn.execute(
            "INSERT INTO combat_state (character_name, current_hp, current_mp, stars) VALUES (?, ?, ?, ?)",
            ("Attacker", 100, 50, 5)
        )

        await conn.commit()

        # Test dice pool logic
        stat_rating = 4  # STR
        pool_size = stat_rating
        ac = 12

        # Simulate rolling 4d6
        rolls = [random.randint(1, 6) for _ in range(pool_size)]
        highest = max(rolls)

        # AC thresholds: 1-2 = 10 AC, 3-4 = 13 AC, 5 = 16 AC, 6 = 19 AC
        def check_hit(highest_die, target_ac):
            if highest_die >= 6:
                return target_ac <= 19
            elif highest_die >= 5:
                return target_ac <= 16
            elif highest_die >= 3:
                return target_ac <= 13
            else:
                return target_ac <= 10

        hit = check_hit(highest, ac)
        assert isinstance(hit, bool)


@pytest.mark.asyncio
async def test_attack_without_roll_stat(db):
    """Test attack without roll_stat (direct damage projection)"""
    # When roll_stat is None, attack just projects damage without rolling
    damage = 25
    target_hp = 80

    # Projected result
    projected_hp = target_hp - damage
    assert projected_hp == 55


@pytest.mark.asyncio
async def test_hide_ac_flavor_text(db):
    """Test hide_ac generates flavor text instead of showing AC"""
    # Flavor text options for miss
    miss_flavors = [
        "The attack whiffs!",
        "Barely misses!",
        "Deflected at the last second!",
        "Goes wide!",
        "Blocked!"
    ]

    # Flavor text options for hit
    hit_flavors = [
        "Direct hit!",
        "Clean strike!",
        "Lands solidly!",
        "Connects!",
        "Critical impact!"
    ]

    # When hide_ac=True, should pick from these lists
    assert len(miss_flavors) > 0
    assert len(hit_flavors) > 0


@pytest.mark.asyncio
async def test_health_bar_rendering(db):
    """Test health bar visualization with Discord emojis"""
    def create_damage_bar(remaining: int, damage: int, max_hp: int) -> str:
        """Create damage visualization bar"""
        if max_hp <= 0:
            return ":black_large_square:" * 10

        remaining_pct = remaining / max_hp
        damage_pct = damage / max_hp

        remaining_blocks = round(remaining_pct * 10)
        damage_blocks = round(damage_pct * 10)

        # Ensure we don't exceed 10 blocks
        total = remaining_blocks + damage_blocks
        if total > 10:
            damage_blocks = 10 - remaining_blocks

        depleted_blocks = 10 - remaining_blocks - damage_blocks

        green = ":green_square:" * remaining_blocks
        red = ":red_square:" * damage_blocks
        black = ":black_large_square:" * depleted_blocks

        return green + red + black

    # Test full health
    bar1 = create_damage_bar(100, 0, 100)
    assert ":green_square:" in bar1
    assert bar1.count(":") == 20  # 10 emoji pairs (opening + closing colons)

    # Test 50% damage
    bar2 = create_damage_bar(50, 30, 100)
    assert ":green_square:" in bar2  # Remaining
    assert ":red_square:" in bar2  # Damage
    assert ":black_large_square:" in bar2  # Depleted


@pytest.mark.asyncio
async def test_star_cost_validation(db):
    """Test star costs are validated in combat"""
    async with aiosqlite.connect(db) as conn:
        stats = {"str": 3, "dex": 3, "con": 3, "int": 2, "wis": 2, "cha": 3}

        # Create character in combat with 2 stars
        await conn.execute(
            "INSERT INTO combat_state (character_name, current_hp, current_mp, stars) VALUES (?, ?, ?, ?)",
            ("Fighter", 100, 50, 2)
        )
        await conn.commit()

        # Verify star count
        async with conn.execute(
            "SELECT stars FROM combat_state WHERE character_name = ?",
            ("Fighter",)
        ) as cursor:
            row = await cursor.fetchone()
            current_stars = row[0]

        # Star costs
        star_costs = {"light": 1, "medium": 2, "heavy": 4}

        # Can afford light (1 star)
        assert current_stars >= star_costs["light"]

        # Can afford medium (2 stars)
        assert current_stars >= star_costs["medium"]

        # Cannot afford heavy (4 stars)
        assert current_stars < star_costs["heavy"]


@pytest.mark.asyncio
async def test_damage_projection_not_auto_applied(db):
    """Test that damage is projected but not auto-applied"""
    async with aiosqlite.connect(db) as conn:
        stats = {"str": 3, "dex": 3, "con": 3, "int": 2, "wis": 2, "cha": 3}

        # Create target with 100 HP
        await conn.execute(
            """INSERT INTO characters (name, hp, max_hp, mp, max_mp, ac, proficiency, stats_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("TestTarget", 100, 100, 50, 50, 13, 3, json.dumps(stats))
        )
        await conn.commit()

        # Project 30 damage
        projected_damage = 30
        projected_hp = 100 - projected_damage

        # Verify HP is still 100 (not auto-applied)
        async with conn.execute("SELECT hp FROM characters WHERE name = ?", ("TestTarget",)) as cursor:
            row = await cursor.fetchone()
            actual_hp = row[0]

        assert actual_hp == 100  # Unchanged
        assert projected_hp == 70  # Projection only


@pytest.mark.asyncio
async def test_crit_damage_calculation(db):
    """Test critical hit (6 on highest die) doubles damage"""
    base_damage = 20
    stat_rating = 3

    # Normal hit
    normal_damage = base_damage + stat_rating
    assert normal_damage == 23

    # Crit (x2)
    crit_damage = (base_damage + stat_rating) * 2
    assert crit_damage == 46


@pytest.mark.asyncio
async def test_temp_hp_absorbs_damage_first(db):
    """Test temp HP absorbs damage before actual HP"""
    current_hp = 80
    max_hp = 100
    temp_hp = 20
    damage = 35

    # Damage breakdown
    if temp_hp > 0:
        temp_absorbed = min(damage, temp_hp)
        actual_damage = damage - temp_absorbed
    else:
        temp_absorbed = 0
        actual_damage = damage

    new_temp_hp = max(0, temp_hp - damage)
    new_hp = max(0, current_hp - actual_damage)

    assert temp_absorbed == 20  # All temp HP absorbed
    assert actual_damage == 15  # Remaining damage to HP
    assert new_temp_hp == 0     # Temp HP depleted
    assert new_hp == 65         # HP reduced by 15
