"""
Effect contribution system for unified dice pool mechanics.
Effects track their contributions and cleanly apply/remove modifiers.
"""

import aiosqlite
import json
from typing import Dict, Any
from utils.value_parser import parse_value, validate_value_format

DATABASE_PATH = 'database/ronan.db'


async def apply_effect(character_name: str, effect_data: Dict[str, Any], db):
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
        db: Database connection (required)
    """

    stackable = effect_data.get('stackable', False)

    # For non-stackable effects, check if it already exists and refresh/update it
    if not stackable:
        async with db.execute("""
            SELECT id, contributions FROM effects WHERE character_name = ? AND effect_name = ?
        """, (character_name, effect_data['name'])) as cursor:
            existing = await cursor.fetchone()

        if existing:
            effect_id, old_contributions_json = existing
            old_contributions = json.loads(old_contributions_json) if old_contributions_json else {}
            new_contributions = effect_data.get('contributions', {}).copy()

            # Get current modifiers and base stats
            async with db.execute("""
                SELECT stat_modifiers, roll_modifiers, ac_modifier, base_stats
                FROM characters WHERE name = ?
            """, (character_name,)) as cursor:
                row = await cursor.fetchone()
                stat_mods = json.loads(row[0])
                roll_mods = json.loads(row[1])
                ac_mod = row[2]
                base_stats = json.loads(row[3]) if row[3] else {}

            # Remove old contributions
            for stat, value in old_contributions.get('stat_modifiers', {}).items():
                stat_mods[stat] -= value
            for roll_type, value in old_contributions.get('roll_modifiers', {}).items():
                roll_mods[roll_type] -= value
            ac_mod -= old_contributions.get('ac_modifier', 0)

            # Add new contributions (handle HALVE markers)
            for stat, value in new_contributions.get('stat_modifiers', {}).items():
                if value == "HALVE":
                    # Calculate halving modifier
                    base_value = base_stats.get(stat, 1)
                    halved_value = base_value // 2
                    halving_modifier = halved_value - base_value
                    # Replace HALVE marker with actual value for storage
                    new_contributions['stat_modifiers'][stat] = halving_modifier
                    stat_mods[stat] += halving_modifier
                else:
                    stat_mods[stat] += value
            for roll_type, value in new_contributions.get('roll_modifiers', {}).items():
                roll_mods[roll_type] += value
            ac_mod += new_contributions.get('ac_modifier', 0)

            # Update character modifiers
            await db.execute("""
                UPDATE characters
                SET stat_modifiers = ?, roll_modifiers = ?, ac_modifier = ?
                WHERE name = ?
            """, (json.dumps(stat_mods), json.dumps(roll_mods), ac_mod, character_name))

            # Update effect in database
            await db.execute("""
                UPDATE effects
                SET available_until_round = ?, contributions = ?, resource_value = ?, dot_value = ?, note = ?
                WHERE character_name = ? AND effect_name = ?
            """, (
                effect_data.get('available_until_round'),
                json.dumps(new_contributions),
                effect_data.get('resource_value', '0'),
                effect_data.get('dot_value', '0'),
                effect_data.get('note', ''),
                character_name,
                effect_data['name']
            ))
            await db.commit()
            print(f"[EFFECT] Refreshed '{effect_data['name']}' on {character_name} (updated modifiers)")
            return

    # Apply contributions using atomic JSON updates
    contributions = effect_data.get('contributions', {})

    # Handle stat modifiers (including HALVE logic)
    stat_mods = contributions.get('stat_modifiers', {})
    for stat, value in stat_mods.items():
        if value == "HALVE":
            # Special halving logic: read base stat, calculate halving modifier, store it
            async with db.execute(f"""
                SELECT base_stats, stat_modifiers FROM characters WHERE name = ?
            """, (character_name,)) as cursor:
                row = await cursor.fetchone()
                base_stats = json.loads(row[0]) if row[0] else {}
                current_mods = json.loads(row[1]) if row[1] else {}

                # Get base stat value (1-5 range)
                base_value = base_stats.get(stat, 1)
                # Calculate halved value (round down)
                halved_value = base_value // 2
                # Modifier is difference: halved - base (will be negative)
                halving_modifier = halved_value - base_value

                # Store actual modifier value in contributions for removal tracking
                if 'stat_modifiers' not in contributions:
                    contributions['stat_modifiers'] = {}
                contributions['stat_modifiers'][stat] = halving_modifier

                # Apply the modifier
                await db.execute(f"""
                    UPDATE characters
                    SET stat_modifiers = json_set(
                        stat_modifiers,
                        '$.{stat}',
                        COALESCE(json_extract(stat_modifiers, '$.{stat}'), 0) + ?
                    )
                    WHERE name = ?
                """, (halving_modifier, character_name))
        else:
            # Normal numeric modifier
            await db.execute(f"""
                UPDATE characters
                SET stat_modifiers = json_set(
                    stat_modifiers,
                    '$.{stat}',
                    COALESCE(json_extract(stat_modifiers, '$.{stat}'), 0) + ?
                )
                WHERE name = ?
            """, (value, character_name))

    roll_mods = contributions.get('roll_modifiers', {})
    for roll_type, value in roll_mods.items():
        await db.execute(f"""
            UPDATE characters
            SET roll_modifiers = json_set(
                roll_modifiers,
                '$.{roll_type}',
                COALESCE(json_extract(roll_modifiers, '$.{roll_type}'), 0) + ?
            )
            WHERE name = ?
        """, (value, character_name))

    ac_modifier_value = contributions.get('ac_modifier', 0)
    if ac_modifier_value != 0:
        await db.execute("""
            UPDATE characters
            SET ac_modifier = ac_modifier + ?
            WHERE name = ?
        """, (ac_modifier_value, character_name))

    # Insert effect
    await db.execute("""
        INSERT INTO effects (character_name, effect_name, emoji, available_until_round, contributions,
                            dot_damage, dot_type, dot_value, resource_type, resource_change, resource_value,
                            stackable, note, damage_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        effect_data.get('note', ''),
        effect_data.get('damage_type', 'physical')
    ))

    await db.commit()
    print(f"[EFFECT] Applied '{effect_data['name']}' to {character_name}")


async def remove_effect(character_name: str, effect_identifier, db):
    """
    Remove effect and subtract contributions from character modifiers.

    Args:
        character_name: Name of character
        effect_identifier: Effect ID (int) or effect name (str)
        db: Database connection (required)
    """

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

    # Remove contributions using atomic JSON updates
    stat_mods = contributions.get('stat_modifiers', {})
    for stat, value in stat_mods.items():
        await db.execute(f"""
            UPDATE characters
            SET stat_modifiers = json_set(
                stat_modifiers,
                '$.{stat}',
                COALESCE(json_extract(stat_modifiers, '$.{stat}'), 0) - ?
            )
            WHERE name = ?
        """, (value, character_name))

    roll_mods = contributions.get('roll_modifiers', {})
    for roll_type, value in roll_mods.items():
        await db.execute(f"""
            UPDATE characters
            SET roll_modifiers = json_set(
                roll_modifiers,
                '$.{roll_type}',
                COALESCE(json_extract(roll_modifiers, '$.{roll_type}'), 0) - ?
            )
            WHERE name = ?
        """, (value, character_name))

    ac_modifier_value = contributions.get('ac_modifier', 0)
    if ac_modifier_value != 0:
        await db.execute("""
            UPDATE characters
            SET ac_modifier = ac_modifier - ?
            WHERE name = ?
        """, (ac_modifier_value, character_name))

    # Delete effect
    if isinstance(effect_identifier, int):
        await db.execute(delete_query, (effect_identifier,))
    else:
        await db.execute(delete_query, (effect_identifier, character_name))

    await db.commit()
    print(f"[EFFECT] Removed effect {effect_identifier} from {character_name}")


async def get_active_effects(character_name: str, db) -> list:
    """Get all active effects for a character."""
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


async def expire_effects(character_name: str, current_round: int, db) -> list:
    """
    Remove expired effects and return list of expired effect names.

    Args:
        character_name: Name of character
        current_round: Current combat round
        db: Database connection (required)

    Returns:
        List of (effect_id, effect_name) tuples that expired
    """
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


def get_preset_effect(effect_name: str, duration: int, **kwargs) -> Dict[str, Any]:
    """
    Get a preset effect configuration.

    Args:
        effect_name: Name of preset effect (burning, stunned, advantage, disadvantage, poisoned)
        duration: Number of rounds until effect expires
        **kwargs: Optional overrides (dot_value, resource_value, note, etc.)

    Returns:
        Effect data dict ready for apply_effect()
    """
    presets = {
        "dot": {
            "name": "dot",
            "emoji": "🩸",
            "contributions": {},
            "dot_value": "0",  # Must be set by caller
            "damage_type": "physical",  # Can be overridden (fire, cold, poison, etc.)
            "stackable": True,
            "note": ""  # Optional note like "fire", "bleed", "venom"
        },
        "poisoned": {
            "name": "poisoned",
            "emoji": "🤢",
            "contributions": {},
            "dot_value": "3",
            "damage_type": "poison",
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
                "roll_modifiers": {"incoming_modifier": 2}  # Positive = attackers get MORE dice (advantage)
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
            "contributions": {
                "stat_modifiers": {"dex": "HALVE"}  # Special marker for halving logic
            },
            "stackable": False,
            "note": ""
        },
        "weakened": {
            "name": "weakened",
            "emoji": "💪🔽",
            "contributions": {
                "stat_modifiers": {"str": "HALVE"}  # Special marker for halving logic
            },
            "stackable": False,
            "note": ""
        },
        "exposed": {
            "name": "exposed",
            "emoji": "🛡️🔽",
            "contributions": {
                "roll_modifiers": {"incoming_modifier": 2}
            },
            "stackable": False,
            "note": ""
        },
        "grappled": {
            "name": "grappled",
            "emoji": "🤼",
            "contributions": {},  # Narrative only
            "stackable": False,
            "note": ""
        },
        "frightened": {
            "name": "frightened",
            "emoji": "😰",
            "contributions": {
                "roll_modifiers": {"attack_modifier": -2}
            },
            "stackable": False,
            "note": ""  # Should specify source via kwargs
        },
        "silenced": {
            "name": "silenced",
            "emoji": "🔇",
            "contributions": {},  # Narrative only - prevents verbal components
            "stackable": False,
            "note": ""
        },
        "charmed": {
            "name": "charmed",
            "emoji": "💖",
            "contributions": {},  # Narrative only - can't attack charmer
            "stackable": False,
            "note": ""  # Should specify charmer via kwargs
        },
        "vulnerable": {
            "name": "vulnerable",
            "emoji": "💥",
            "contributions": {},  # Damage multiplier handled in move_execution.py
            "stackable": False,
            "note": ""  # Must specify damage type via kwargs (e.g., "fire", "cold")
        },
        "resistant": {
            "name": "resistant",
            "emoji": "🛡️",
            "contributions": {},  # Damage multiplier handled in move_execution.py
            "stackable": False,
            "note": ""  # Must specify damage type via kwargs (e.g., "fire", "cold")
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
                "roll_modifiers": {"incoming_modifier": 1}  # Positive = attackers get MORE dice (easier to hit)
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
    # Merge in any kwargs to override defaults
    effect.update(kwargs)
    return effect
