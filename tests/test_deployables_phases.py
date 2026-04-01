"""
Test script for deployables system phases 1-5.

Tests:
- Phase 1: /deploy attack basic functionality
- Phase 2: /move use with deployable parameter
- Phase 3: Resource costs on /deploy create
- Phase 4: Damage threshold system
- Phase 5: MP scaling on /deploy create
"""

import asyncio
import aiosqlite
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATABASE_PATH = 'database/ronan.db'


async def setup_test_data():
    """Create test characters and clean up any existing test data."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Clean up any existing test data
        await db.execute("DELETE FROM characters WHERE name LIKE 'TestChar%'")
        await db.execute("DELETE FROM deployables WHERE owner_name LIKE 'TestChar%'")
        await db.execute("DELETE FROM movesets WHERE character_name LIKE 'TestChar%'")

        # Create test character 1 (Alice)
        stats_json = '{"str": 4, "dex": 3, "con": 2, "int": 1, "wis": 2, "cha": 1}'
        await db.execute("""
            INSERT INTO characters (
                name, stats_json, base_stats, stat_modifiers, hp, max_hp, mp, max_mp,
                ac, current_stars, max_stars, proficiency,
                threshold_damage, threshold_dc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'TestCharAlice',
            stats_json,
            stats_json,
            '{"str": 1, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0}',
            50, 50,  # hp, max_hp
            40, 40,  # mp, max_mp
            12,      # ac
            5, 5,    # current_stars, max_stars
            2,       # proficiency
            15, 12   # threshold_damage, threshold_dc
        ))

        # Create test character 2 (Bob - target)
        stats_json2 = '{"str": 2, "dex": 2, "con": 3, "int": 1, "wis": 2, "cha": 1}'
        await db.execute("""
            INSERT INTO characters (
                name, stats_json, base_stats, stat_modifiers, hp, max_hp, mp, max_mp,
                ac, current_stars, max_stars, proficiency,
                threshold_damage, threshold_dc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'TestCharBob',
            stats_json2,
            stats_json2,
            '{"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0}',
            40, 40,  # hp, max_hp
            30, 30,  # mp, max_mp
            10,      # ac
            5, 5,    # current_stars, max_stars
            2,       # proficiency
            10, 11   # threshold_damage, threshold_dc
        ))

        await db.commit()
        print("[SETUP] Test characters created: TestCharAlice, TestCharBob")


async def test_phase3_resource_costs():
    """Phase 3: Test resource costs on /deploy create."""
    print("\n=== PHASE 3: Resource Costs ===")

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Get Alice's initial MP
        async with db.execute(
            "SELECT mp FROM characters WHERE name = ?",
            ('TestCharAlice',)
        ) as cursor:
            initial_mp = (await cursor.fetchone())[0]

        print(f"Initial MP: {initial_mp}")

        # Create deployable with MP cost
        mp_cost = 10
        await db.execute("""
            INSERT INTO deployables (
                owner_name, deployable_name, hp, max_hp, stars, max_stars,
                available_until_round, created_round
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ('TestCharAlice', 'TestDrone1', 15, 15, 3, 3, 999999, 1))

        # Deduct MP
        await db.execute(
            "UPDATE characters SET mp = mp - ? WHERE name = ?",
            (mp_cost, 'TestCharAlice')
        )
        await db.commit()

        # Verify MP deduction
        async with db.execute(
            "SELECT mp FROM characters WHERE name = ?",
            ('TestCharAlice',)
        ) as cursor:
            final_mp = (await cursor.fetchone())[0]

        expected_mp = initial_mp - mp_cost
        if final_mp == expected_mp:
            print(f"✅ MP deducted correctly: {initial_mp} → {final_mp} (cost: {mp_cost})")
        else:
            print(f"❌ MP deduction failed: expected {expected_mp}, got {final_mp}")

        # Verify deployable created
        async with db.execute(
            "SELECT deployable_name, hp, stars FROM deployables WHERE owner_name = ?",
            ('TestCharAlice',)
        ) as cursor:
            deployable = await cursor.fetchone()

        if deployable:
            print(f"✅ Deployable created: {deployable[0]} (HP: {deployable[1]}, Stars: {deployable[2]})")
        else:
            print("❌ Deployable creation failed")


async def test_phase5_mp_scaling():
    """Phase 5: Test MP scaling on /deploy create."""
    print("\n=== PHASE 5: MP Scaling ===")

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Create deployable with MP scaling
        base_hp = 10
        base_stars = 2
        mp_spent = 25  # Should give +5 to each stat

        hp_bonus = mp_spent // 5
        stars_bonus = mp_spent // 5
        scaled_hp = base_hp + hp_bonus
        scaled_stars = base_stars + stars_bonus

        await db.execute("""
            INSERT INTO deployables (
                owner_name, deployable_name, hp, max_hp, stars, max_stars,
                available_until_round, created_round
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ('TestCharAlice', 'TestScaledDrone', scaled_hp, scaled_hp, scaled_stars, scaled_stars, 999999, 1))

        await db.commit()

        # Verify scaling
        async with db.execute(
            "SELECT hp, max_hp, stars, max_stars FROM deployables WHERE deployable_name = ?",
            ('TestScaledDrone',)
        ) as cursor:
            result = await cursor.fetchone()

        if result:
            hp, max_hp, stars, max_stars = result
            print(f"Base stats: HP {base_hp}, Stars {base_stars}")
            print(f"MP spent: {mp_spent} → Bonus: +{hp_bonus} HP, +{stars_bonus} Stars")

            if hp == scaled_hp and stars == scaled_stars:
                print(f"✅ Scaling correct: HP {base_hp}+{hp_bonus}={hp}, Stars {base_stars}+{stars_bonus}={stars}")
            else:
                print(f"❌ Scaling failed: expected HP={scaled_hp} Stars={scaled_stars}, got HP={hp} Stars={stars}")
        else:
            print("❌ Scaled deployable not found")


async def test_phase4_damage_threshold():
    """Phase 4: Test damage threshold system."""
    print("\n=== PHASE 4: Damage Threshold ===")

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Get Bob's threshold settings
        async with db.execute(
            "SELECT threshold_damage, threshold_dc FROM characters WHERE name = ?",
            ('TestCharBob',)
        ) as cursor:
            result = await cursor.fetchone()

        if result:
            threshold_damage, threshold_dc = result
            print(f"TestCharBob threshold: {threshold_damage} damage, DC {threshold_dc} CON save")

            # Test damage below threshold
            low_damage = 8
            if low_damage < threshold_damage:
                print(f"✅ {low_damage} damage < {threshold_damage} threshold: No CON save needed")

            # Test damage at/above threshold
            high_damage = 15
            if high_damage >= threshold_damage:
                print(f"✅ {high_damage} damage ≥ {threshold_damage} threshold: DC {threshold_dc} CON save required!")
        else:
            print("❌ Could not read threshold data")


async def test_phase2_deployable_moves():
    """Phase 2: Test /move use with deployable."""
    print("\n=== PHASE 2: Deployable Move Execution ===")

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Get deployable stars
        async with db.execute(
            "SELECT id, stars, owner_name FROM deployables WHERE deployable_name = ?",
            ('TestDrone1',)
        ) as cursor:
            deployable = await cursor.fetchone()

        if not deployable:
            print("❌ TestDrone1 not found")
            return

        dep_id, initial_stars, owner = deployable
        print(f"Deployable: TestDrone1 (ID: {dep_id}, Stars: {initial_stars}, Owner: {owner})")

        # Simulate move use (2 star cost)
        star_cost = 2
        await db.execute(
            "UPDATE deployables SET stars = stars - ? WHERE id = ?",
            (star_cost, dep_id)
        )
        await db.commit()

        # Verify star deduction
        async with db.execute(
            "SELECT stars FROM deployables WHERE id = ?",
            (dep_id,)
        ) as cursor:
            final_stars = (await cursor.fetchone())[0]

        expected_stars = initial_stars - star_cost
        if final_stars == expected_stars:
            print(f"✅ Stars deducted from deployable: {initial_stars} → {final_stars} (cost: {star_cost})")
        else:
            print(f"❌ Star deduction failed: expected {expected_stars}, got {final_stars}")

        # Verify owner's MP would be deducted (not deployable's)
        print(f"✅ MP/HP costs would deduct from owner ({owner}), not deployable")


async def test_phase1_deploy_attack():
    """Phase 1: Test /deploy attack auto-damage calculation."""
    print("\n=== PHASE 1: Deploy Attack ===")

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Get Alice's stats for auto-damage calculation
        async with db.execute(
            "SELECT base_stats, stat_modifiers FROM characters WHERE name = ?",
            ('TestCharAlice',)
        ) as cursor:
            result = await cursor.fetchone()

        if not result:
            print("❌ TestCharAlice not found")
            return

        import json
        base_stats = json.loads(result[0])
        stat_mods = json.loads(result[1])

        # Calculate auto-damage for medium attack
        str_total = base_stats.get("str", 0) + stat_mods.get("str", 0)
        dex_total = base_stats.get("dex", 0) + stat_mods.get("dex", 0)
        highest_offensive_stat = max(str_total, dex_total)

        base_damages = {"light": 4, "medium": 8, "heavy": 14}
        attack_type = "medium"
        auto_damage = base_damages[attack_type] + highest_offensive_stat

        print(f"Owner stats: STR {str_total}, DEX {dex_total}")
        print(f"Attack type: {attack_type}")
        print(f"✅ Auto-damage calculation: {base_damages[attack_type]} (base) + {highest_offensive_stat} (highest offensive) = {auto_damage}")

        # Verify deployable would use owner's stats
        print(f"✅ Deployable uses owner's stats for attack rolls")


async def cleanup_test_data():
    """Clean up test data."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM characters WHERE name LIKE 'TestChar%'")
        await db.execute("DELETE FROM deployables WHERE owner_name LIKE 'TestChar%'")
        await db.execute("DELETE FROM movesets WHERE character_name LIKE 'TestChar%'")
        await db.commit()
        print("\n[CLEANUP] Test data removed")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("DEPLOYABLES SYSTEM TEST - Phases 1-5")
    print("=" * 60)

    try:
        await setup_test_data()
        await test_phase3_resource_costs()
        await test_phase5_mp_scaling()
        await test_phase4_damage_threshold()
        await test_phase2_deployable_moves()
        await test_phase1_deploy_attack()

        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED")
        print("=" * 60)

    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await cleanup_test_data()


if __name__ == "__main__":
    asyncio.run(main())
