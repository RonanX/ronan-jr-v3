"""
Moveset parser utilities - PROMPT 6
Parse text and JSON moveset formats
"""

import json
import re
from typing import List, Dict, Tuple, Any

STAT_NAMES = ["str", "dex", "con", "int", "wis", "cha"]
VALID_CATEGORIES = ["light", "medium", "heavy", "utility"]
STAR_COSTS = {"light": 1, "medium": 2, "heavy": 4, "utility": 2}


def parse_text_moveset(text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Parse text format moveset.

    Format: name - type, property1, property2, etc
    Example: tempest fang - light, 4 damage, 2 hits, disadvantage to attackers

    Returns: (successful_moves, warnings)
    """
    moves = []
    warnings = []

    lines = [line.strip() for line in text.split('\n') if line.strip()]

    for line_num, line in enumerate(lines, 1):
        try:
            # Split on first dash
            if ' - ' not in line:
                warnings.append(f"Line {line_num}: No dash separator found, skipping: {line[:50]}")
                continue

            name_part, properties_part = line.split(' - ', 1)
            move_name = name_part.strip()

            # Parse properties
            move = {
                "name": move_name,
                "category": "utility",  # Default
                "stat": "str",  # Default
                "damage": 0,
                "hits": 1,
                "mp_cost": 0,
                "hp_cost": 0,
                "targets": 1,
                "description": ""
            }

            properties = [p.strip() for p in properties_part.split(',')]

            # Track unrecognized properties for description
            unrecognized = []

            for prop in properties:
                prop_lower = prop.lower()

                # Category/type
                if any(cat in prop_lower for cat in VALID_CATEGORIES):
                    for cat in VALID_CATEGORIES:
                        if cat in prop_lower:
                            move["category"] = cat
                            break

                # Damage
                elif 'damage' in prop_lower or 'dmg' in prop_lower:
                    # Extract number
                    match = re.search(r'(\d+)', prop)
                    if match:
                        move["damage"] = int(match.group(1))

                # Hits (support both "2 hits" and "multihit" keyword)
                elif 'hit' in prop_lower or 'multihit' in prop_lower:
                    match = re.search(r'(\d+)', prop)
                    if match:
                        move["hits"] = int(match.group(1))
                    elif 'multihit' in prop_lower:
                        # Default multihit to 2 if no number specified
                        move["hits"] = 2

                # MP cost
                elif 'mp' in prop_lower:
                    match = re.search(r'(\d+)', prop)
                    if match:
                        move["mp_cost"] = int(match.group(1))

                # HP cost
                elif 'hp' in prop_lower and 'cost' in prop_lower:
                    match = re.search(r'(\d+)', prop)
                    if match:
                        move["hp_cost"] = int(match.group(1))

                # Targets
                elif 'target' in prop_lower or 'enemies' in prop_lower or 'allies' in prop_lower:
                    match = re.search(r'(\d+)', prop)
                    if match:
                        move["targets"] = int(match.group(1))
                    else:
                        # "all enemies", "all allies", etc
                        move["targets"] = prop

                # Stat
                elif any(stat in prop_lower for stat in STAT_NAMES):
                    for stat in STAT_NAMES:
                        if stat in prop_lower:
                            move["stat"] = stat
                            break

                # Save type
                elif 'save' in prop_lower:
                    for stat in STAT_NAMES:
                        if stat in prop_lower:
                            move["save_type"] = stat
                            break

                # Save DC
                elif 'dc' in prop_lower:
                    match = re.search(r'(\d+)', prop)
                    if match:
                        move["save_dc"] = int(match.group(1))

                # Everything else goes to description
                else:
                    unrecognized.append(prop)

            # Combine unrecognized parts into description
            if unrecognized:
                move["description"] = ", ".join(unrecognized)

            moves.append(move)

        except Exception as e:
            warnings.append(f"Line {line_num}: Error parsing '{line[:50]}': {str(e)}")

    return moves, warnings


def parse_json_moveset(json_text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Parse JSON format moveset.

    Returns: (successful_moves, warnings)
    """
    moves = []
    warnings = []

    try:
        data = json.loads(json_text)

        if not isinstance(data, list):
            warnings.append("JSON must be an array of move objects")
            return [], warnings

        for idx, move_data in enumerate(data, 1):
            if not isinstance(move_data, dict):
                warnings.append(f"Move {idx}: Must be an object, skipping")
                continue

            # Required fields
            if "name" not in move_data:
                warnings.append(f"Move {idx}: Missing 'name' field, skipping")
                continue

            # Build move with defaults
            move = {
                "name": move_data["name"],
                "category": move_data.get("category") or move_data.get("type", "utility"),
                "stat": move_data.get("stat", "str"),
                "damage": move_data.get("damage", 0),
                "hits": move_data.get("hits", 1),
                "mp_cost": move_data.get("mp_cost", 0),
                "hp_cost": move_data.get("hp_cost", 0),
                "targets": move_data.get("targets", 1),
                "save_type": move_data.get("save_type"),
                "save_dc": move_data.get("save_dc"),
                "save_effect": move_data.get("save_effect"),
                "half_on_save": move_data.get("half_on_save", 0),
                "bonus_on_hit": move_data.get("bonus_on_hit"),
                "description": move_data.get("description", "")
            }

            # Validate category
            if move["category"] not in VALID_CATEGORIES:
                warnings.append(f"Move {idx} ({move['name']}): Invalid category '{move['category']}', defaulting to utility")
                move["category"] = "utility"

            # Validate stat
            if move["stat"] not in STAT_NAMES:
                warnings.append(f"Move {idx} ({move['name']}): Invalid stat '{move['stat']}', defaulting to str")
                move["stat"] = "str"

            moves.append(move)

    except json.JSONDecodeError as e:
        warnings.append(f"Invalid JSON: {str(e)}")
        return [], warnings

    return moves, warnings


def validate_moveset(moves: List[Dict[str, Any]]) -> List[str]:
    """
    Validate parsed moveset and return warnings.
    """
    warnings = []

    # Check for duplicates
    names = [m["name"].lower() for m in moves]
    duplicates = [name for name in names if names.count(name) > 1]
    if duplicates:
        warnings.append(f"Duplicate move names found: {', '.join(set(duplicates))}")

    # Check for unreasonable values
    for move in moves:
        if move["damage"] > 100:
            warnings.append(f"{move['name']}: Unusually high damage ({move['damage']})")

        if move["hits"] > 10:
            warnings.append(f"{move['name']}: Unusually high hit count ({move['hits']})")

        if move["mp_cost"] > 100:
            warnings.append(f"{move['name']}: Unusually high MP cost ({move['mp_cost']})")

        # Warn if has both save_type and direct damage (might be intended, but worth checking)
        if move.get("save_type") and move["damage"] > 0 and "save" not in move.get("description", "").lower():
            warnings.append(f"{move['name']}: Has both save_type and damage (is this intentional?)")

    return warnings


def format_moveset_preview(moves: List[Dict[str, Any]], character: str, form: str) -> str:
    """
    Format moveset for preview display.

    Returns formatted string for embed.
    """
    if not moves:
        return "No moves parsed."

    # Group by category
    by_category = {}
    for move in moves:
        cat = move["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(move)

    category_emojis = {
        "light": "⚡",
        "medium": "⚔️",
        "heavy": "💥",
        "utility": "🛠️"
    }

    lines = [f"Found {len(moves)} moves for **{character}** ({form} form):\n"]

    for category in ["light", "medium", "heavy", "utility"]:
        if category not in by_category:
            continue

        emoji = category_emojis[category]
        cat_moves = by_category[category]

        lines.append(f"\n{emoji} **{category.upper()}** ({len(cat_moves)})")

        for move in cat_moves:
            # Build info string
            info_parts = []

            if move["damage"] > 0:
                dmg_str = f"{move['damage']} dmg"
                if move["hits"] > 1:
                    dmg_str += f" × {move['hits']}"
                info_parts.append(dmg_str)

            if move["mp_cost"] > 0:
                info_parts.append(f"{move['mp_cost']} mp")

            if move["hp_cost"] > 0:
                info_parts.append(f"{move['hp_cost']} hp")

            if move.get("save_type"):
                info_parts.append(f"{move['save_type'].upper()} save")

            if isinstance(move["targets"], int) and move["targets"] > 1:
                info_parts.append(f"{move['targets']} targets")
            elif isinstance(move["targets"], str):
                info_parts.append(move["targets"])

            if move.get("bonus_on_hit"):
                info_parts.append(move["bonus_on_hit"])

            if move.get("description"):
                info_parts.append(move["description"])

            info_str = ", ".join(info_parts) if info_parts else "no properties"

            lines.append(f"• **{move['name']}** ({info_str})")

    return "\n".join(lines)


def export_moveset_json(moves: List[Dict[str, Any]]) -> str:
    """
    Export moveset to formatted JSON string.
    """
    # Clean up moves for export (remove None values)
    export_moves = []
    for move in moves:
        clean_move = {k: v for k, v in move.items() if v is not None and v != 0 and v != ""}
        export_moves.append(clean_move)

    return json.dumps(export_moves, indent=2)
