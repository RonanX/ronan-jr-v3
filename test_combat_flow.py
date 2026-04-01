"""
Test harness for combat flow and database operations
Run this to test /init next logic without Discord
"""

import asyncio
import aiosqlite
import json
from utils.effects import expire_effects, apply_effect, get_active_effects

DATABASE_PATH = 'database/ronan.db'


async def setup_test_combat():
    """Set up a test combat scenario"""
    print("Setting up test combat...")

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Clear existing combat
        await db.execute("UPDATE initiative SET combat_active = 0 WHERE id = 1")
        await db.execute("DELETE FROM combat_state")
        await db.execute("DELETE FROM effects")

        # Create test turn order
        turn_order = [
            {"name": "test", "initiative": 15, "roll": 10, "dexterity": 5},
            {"name": "test2", "initiative": 12, "roll": 8, "dexterity": 4}
        ]

        # Set up combat
        await db.execute("""
            UPDATE initiative
            SET combat_active = 1,
                round_number = 1,
                current_turn_index = 0,
                turn_order_json = ?
            WHERE id = 1
        """, (json.dumps(turn_order),))

        # Add characters to combat_state
        for char in turn_order:
            await db.execute("""
                INSERT INTO combat_state (character_name, stars, effects_json)
                VALUES (?, 5, '[]')
            """, (char["name"],))

        # Add a test effect that expires on round 2
        effect_data = {
            "name": "test_effect",
            "emoji": "🔥",
            "available_until_round": 2,
            "contributions": {"stat_modifiers": {"str": 2}},
            "dot_damage": 5,
            "dot_type": "fire"
        }
        await apply_effect("test", effect_data, db=db)

        await db.commit()
        print("[OK] Test combat set up")


async def test_advance_turn():
    """Test advancing a turn (simulates /init next)"""
    print("\n=== Testing Turn Advancement ===")

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Get current state
        async with db.execute("""
            SELECT combat_active, round_number, current_turn_index, turn_order_json
            FROM initiative WHERE id = 1
        """) as cursor:
            row = await cursor.fetchone()
            combat_active, round_num, current_idx, turn_order_json = row
            turn_order = json.loads(turn_order_json)

        print(f"Before: Round {round_num}, Turn index {current_idx}")

        # Advance turn
        current_idx += 1
        if current_idx >= len(turn_order):
            current_idx = 0
            round_num += 1

        current_char_name = turn_order[current_idx]["name"]
        print(f"After: Round {round_num}, Turn index {current_idx}, Character: {current_char_name}")

        # Update initiative
        await db.execute("""
            UPDATE initiative
            SET round_number = ?, current_turn_index = ?
            WHERE id = 1
        """, (round_num, current_idx))

        # Test effect expiration (this is where the bug was)
        print(f"\nExpiring effects for {current_char_name} at round {round_num}...")
        expired = await expire_effects(current_char_name, round_num, db=db)

        if expired:
            print(f"[OK] Expired effects: {[name for _, name in expired]}")
        else:
            print("[OK] No effects expired")

        # Get active effects
        active = await get_active_effects(current_char_name)
        print(f"Active effects: {[e['name'] for e in active]}")

        await db.commit()
        print("[OK] Turn advanced successfully")


async def test_multiple_turns():
    """Test multiple turn advancements"""
    print("\n=== Testing Multiple Turns ===")

    for i in range(5):
        print(f"\n--- Turn {i+1} ---")
        await test_advance_turn()
        await asyncio.sleep(0.2)  # Simulate delay between turns


async def cleanup():
    """Clean up test data"""
    print("\n=== Cleanup ===")
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE initiative SET combat_active = 0 WHERE id = 1")
        await db.execute("DELETE FROM combat_state")
        await db.execute("DELETE FROM effects")
        await db.commit()
    print("[OK] Cleaned up test data")


async def main():
    """Run all tests"""
    try:
        await setup_test_combat()
        await test_advance_turn()
        await test_multiple_turns()
        print("\n[OK] All tests passed!")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await cleanup()


if __name__ == "__main__":
    asyncio.run(main())
