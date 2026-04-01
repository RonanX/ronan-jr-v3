"""
Effect contribution system for unified dice pool mechanics.
Effects track their contributions and cleanly apply/remove modifiers.
"""

import aiosqlite
import json
from typing import Dict, Any
from utils.value_parser import parse_value, validate_value_format

DATABASE_PATH = 'database/ronan.db'


async def apply_effect(character_name: str, effect_data: Dict[str, Any], db=None):
    """
    Apply effect and add contributions to character modifiers.

    Args:
        character_name: Name of character to apply effect to
        effect_data: Dict with keys:
            - name: Effect name
            - emoji: Effect emoji (optional)
            - available_until_round: Round when effect expires
            - contributions: Dict with stat_modifiers, roll_modifiers, ac_modifier
            - dot_value: DoT value per turn (flat/dice/percentage) (optional)
            - resource_type: 'hp' or 'mp' (optional)
            - resource_value: Resource change value (flat/dice/percentage) (optional)
            - stackable: Whether multiple instances can exist (optional)
            - note: Optional note to append to display name (optional)
        db: Optional database connection (for testing)
    """
    close_db = db is None
    if db is None:
        db = await aiosqlite.connect(DATABASE_PATH)

    try:
        stackable = effect_data.get('stackable', False)

        # For non-stackable effects, check if it already exists and refresh/update it
        if not stackable:
            async with db.execute("""
                SELECT id FROM effects WHERE character_name = ? AND effect_name = ?
            """, (character_name, effect_data['name'])) as cursor:
                existing = await cursor.fetchone()

            if existing:
                # Update existing effect's duration and value
                await db.execute("""
                    UPDATE effects
                    SET available_until_round = ?, resource_value = ?, note = ?
                    WHERE character_name = ? AND effect_name = ?
                """, (
                    effect_data.get('available_until_round'),
                    effect_data.get('resource_value', '0'),
                    effect_data.get('note', ''),
                    character_name,
                    effect_data['name']
                ))
                await db.commit()
                print(f"[EFFECT] Refreshed '{effect_data['name']}' on {character_name}")
                return

        # Get current modifiers
        async with db.execute("""
            SELECT stat_modifiers, roll_modifiers, ac_modifier
            FROM characters WHERE name = ?
        """, (character_name,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise ValueError(f"Character '{character_name}' not found")

            stat_mods = json.loads(row[0])
            roll_mods = json.loads(row[1])
            ac_mod = row[2]

        # Apply contributions
        contributions = effect_data.get('contributions', {})

        for stat, value in contributions.get('stat_modifiers', {}).items():
            stat_mods[stat] += value

        for roll_type, value in contributions.get('roll_modifiers', {}).items():
            roll_mods[roll_type] += value

        ac_mod += contributions.get('ac_modifier', 0)

        # Update character
        await db.execute("""
            UPDATE characters
            SET stat_modifiers = ?, roll_modifiers = ?, ac_modifier = ?
            WHERE name = ?
        """, (json.dumps(stat_mods), json.dumps(roll_mods), ac_mod, character_name))

        # Insert effect
        await db.execute("""
            INSERT INTO effects (character_name, effect_name, emoji, available_until_round, contributions,
                                dot_damage, dot_type, dot_value, resource_type, resource_change, resource_value,
                                stackable, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            character_name,
            effect_data['name'],
            effect_data.get('emoji', '🔮'),
            effect_data.get('available_until_round'),
            json.dumps(contributions),
            effect_data.get('dot_damage', 0),  # Legacy field
            effect_data.get('dot_type', ''),    # Legacy field
            effect_data.get('dot_value', '0'),
            effect_data.get('resource_type', 'hp'),
            effect_data.get('resource_change', 0),  # Legacy field
            effect_data.get('resource_value', '0'),
            1 if stackable else 0,
            effect_data.get('note', '')
        ))

        await db.commit()
        print(f"[EFFECT] Applied '{effect_data['name']}' to {character_name}")
    finally:
        if close_db:
            await db.close()


async def remove_effect(character_name: str, effect_identifier, db=None):
    """
    Remove effect and subtract contributions from character modifiers.

    Args:
        character_name: Name of character
        effect_identifier: Effect ID (int) or effect name (str)
        db: Optional database connection (for testing)
    """
    close_db = db is None
    if db is None:
        db = await aiosqlite.connect(DATABASE_PATH)

    try:
        # Determine if identifier is ID or name
        if isinstance(effect_identifier, int):
            query = "SELECT contributions FROM effects WHERE id = ? AND character_name = ?"
            delete_query = "DELETE FROM effects WHERE id = ?"
        else:
            query = "SELECT contributions FROM effects WHERE effect_name = ? AND character_name = ?"
            delete_query = "DELETE FROM effects WHERE effect_name = ? AND character_name = ?"

        # Get effect contributions
        async with db.execute(query, (effect_identifier, character_name)) as cursor:
            row = await cursor.fetchone()
            if not row:
                print(f"[WARN] Effect {effect_identifier} not found for {character_name}")
                return
            contributions = json.loads(row[0])

        # Get current modifiers
        async with db.execute("""
            SELECT stat_modifiers, roll_modifiers, ac_modifier
            FROM characters WHERE name = ?
        """, (character_name,)) as cursor:
            row = await cursor.fetchone()
            stat_mods = json.loads(row[0])
            roll_mods = json.loads(row[1])
            ac_mod = row[2]

        # Remove contributions
        for stat, value in contributions.get('stat_modifiers', {}).items():
            stat_mods[stat] -= value

        for roll_type, value in contributions.get('roll_modifiers', {}).items():
            roll_mods[roll_type] -= value

        ac_mod -= contributions.get('ac_modifier', 0)

        # Update character
        await db.execute("""
            UPDATE characters
            SET stat_modifiers = ?, roll_modifiers = ?, ac_modifier = ?
            WHERE name = ?
        """, (json.dumps(stat_mods), json.dumps(roll_mods), ac_mod, character_name))

        # Delete effect
        if isinstance(effect_identifier, int):
            await db.execute(delete_query, (effect_identifier,))
        else:
            await db.execute(delete_query, (effect_identifier, character_name))

        await db.commit()
        print(f"[EFFECT] Removed effect {effect_identifier} from {character_name}")
    finally:
        if close_db:
            await db.close()


async def get_active_effects(character_name: str, db=None) -> list:
    """Get all active effects for a character."""
    close_db = db is None
    if db is None:
        db = await aiosqlite.connect(DATABASE_PATH)

    try:
        async with db.execute("""
            SELECT id, effect_name, emoji, available_until_round, dot_damage, dot_type, dot_value,
                   resource_type, resource_change, resource_value, stackable, note
            FROM effects
            WHERE character_name = ?
            ORDER BY available_until_round ASC
        """, (character_name,)) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    'id': row[0],
                    'name': row[1],
                    'emoji': row[2],
                    'available_until_round': row[3],
                    'dot_damage': row[4],  # Legacy
                    'dot_type': row[5],    # Legacy
                    'dot_value': row[6] if len(row) > 6 else '0',
                    'resource_type': row[7] if len(row) > 7 else 'hp',
                    'resource_change': row[8] if len(row) > 8 else 0,  # Legacy
                    'resource_value': row[9] if len(row) > 9 else '0',
                    'stackable': bool(row[10]) if len(row) > 10 else False,
                    'note': row[11] if len(row) > 11 else ''
                }
                for row in rows
            ]
    finally:
        if close_db:
            await db.close()


async def expire_effects(character_name: str, current_round: int, db=None) -> list:
    """
    Remove expired effects and return list of expired effect names.

    Args:
        character_name: Name of character
        current_round: Current combat round
        db: Optional database connection (for reusing existing connection)

    Returns:
        List of (effect_id, effect_name) tuples that expired
    """
    close_db = db is None
    if db is None:
        db = await aiosqlite.connect(DATABASE_PATH)

    try:
        # Get expired effects
        async with db.execute("""
            SELECT id, effect_name
            FROM effects
            WHERE character_name = ? AND available_until_round <= ?
        """, (character_name, current_round)) as cursor:
            expired = await cursor.fetchall()

        # Remove each expired effect (pass db connection to avoid nested connections)
        for effect_id, effect_name in expired:
            await remove_effect(character_name, effect_id, db=db)

        return expired
    finally:
        if close_db:
            await db.close()


def get_preset_effect(effect_name: str, duration: int) -> Dict[str, Any]:
    """
    Get a preset effect configuration.

    Args:
        effect_name: Name of preset effect (burning, stunned, advantage, disadvantage, poisoned)
        duration: Number of rounds until effect expires

    Returns:
        Effect data dict ready for apply_effect()
    """
    presets = {
        "dot": {
            "name": "dot",
            "emoji": "🩸",
            "contributions": {},
            "dot_value": "0",  # Must be set by caller
            "stackable": True,
            "note": ""  # Optional note like "fire", "bleed", "venom"
        },
        "poisoned": {
            "name": "poisoned",
            "emoji": "🤢",
            "contributions": {},
            "dot_value": "3",
            "stackable": False,
            "note": ""
        },
        "mana_drain": {
            "name": "mana_drain",
            "emoji": "💧",
            "contributions": {},
            "resource_type": "mp",
            "resource_value": "-3",
            "stackable": False,
            "note": ""
        },
        "mana_regen": {
            "name": "mana_regen",
            "emoji": "💙",
            "contributions": {},
            "resource_type": "mp",
            "resource_value": "3",
            "stackable": False,
            "note": ""
        },
        "health_regen": {
            "name": "health_regen",
            "emoji": "💚",
            "contributions": {},
            "resource_type": "hp",
            "resource_value": "3",
            "stackable": False,
            "note": ""
        },
        "mana_siphon": {
            "name": "mana_siphon",
            "emoji": "🌀",
            "contributions": {},
            "resource_type": "mp",
            "resource_value": "-5",
            "stackable": False,
            "note": ""
        },
        "stunned": {
            "name": "stunned",
            "emoji": "💫",
            "contributions": {
                "roll_modifiers": {"attack_modifier": -99}
            },
            "stackable": False,
            "note": ""
        },
        "prone": {
            "name": "prone",
            "emoji": "🔻",
            "contributions": {
                "roll_modifiers": {"incoming_modifier": -2}
            },
            "stackable": False,
            "note": ""
        },
        "blinded": {
            "name": "blinded",
            "emoji": "👁️‍🗨️",
            "contributions": {
                "roll_modifiers": {"attack_modifier": -2}
            },
            "stackable": False,
            "note": ""
        },
        "slowed": {
            "name": "slowed",
            "emoji": "🐌",
            "contributions": {},
            "stackable": False,
            "note": ""
        },
        "restrained": {
            "name": "restrained",
            "emoji": "⛓️",
            "contributions": {
                "roll_modifiers": {"attack_modifier": -2, "save_modifier": -2}
            },
            "stackable": False,
            "note": ""
        },
        "marked": {
            "name": "marked",
            "emoji": "🎯",
            "contributions": {
                "roll_modifiers": {"incoming_modifier": -1}
            },
            "stackable": False,
            "note": ""
        },
        "advantage": {
            "name": "advantage",
            "emoji": "⬆️",
            "contributions": {
                "roll_modifiers": {"attack_modifier": 1}
            },
            "stackable": True,  # Each instance is +1, stackable
            "note": ""
        },
        "disadvantage": {
            "name": "disadvantage",
            "emoji": "⬇️",
            "contributions": {
                "roll_modifiers": {"attack_modifier": -1}
            },
            "stackable": True,  # Each instance is -1, stackable
            "note": ""
        }
    }

    if effect_name not in presets:
        raise ValueError(f"Unknown preset effect: {effect_name}")

    effect = presets[effect_name].copy()
    effect["available_until_round"] = duration
    return effect
