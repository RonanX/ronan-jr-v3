"""
Damage calculation system for Starfall Lite.

Supports flexible damage formulas with dice, static values, stat modifiers, and damage types.

Formula syntax:
    "4 fire" → 4 fire damage
    "2d6 cold" → roll 2d6 cold damage
    "1d8+str slashing" → roll 1d8, add STR modifier, slashing damage
    "+cha" → CHA modifier (no type specified)
    "2+cha/hit fire" → (2 + CHA) per hit

Multiple components separated by commas:
    "4 bludgeoning, 2d6+cha fire, +str"
"""

import random
import re
from typing import Dict, List, Optional, Tuple


def roll_dice(dice_str: str) -> int:
    """
    Roll XdY dice and return total.

    Args:
        dice_str: Dice notation (e.g., "2d6", "1d8", "3d4")

    Returns:
        Total of all dice rolled

    Examples:
        >>> random.seed(42)
        >>> roll_dice("2d6")  # Example output, will vary
        7
    """
    match = re.match(r'(\d+)d(\d+)', dice_str.lower().strip())
    if not match:
        raise ValueError(f"Invalid dice notation: {dice_str}")

    num_dice = int(match.group(1))
    die_size = int(match.group(2))

    if num_dice < 1 or die_size < 1:
        raise ValueError(f"Invalid dice values: {num_dice}d{die_size}")

    return sum(random.randint(1, die_size) for _ in range(num_dice))


def parse_damage_component(component_str: str) -> Dict:
    """
    Parse a single damage component.

    Args:
        component_str: Component string (e.g., "4 fire", "2d6+cha/hit fire", "+str")

    Returns:
        Dict with keys: dice, static, stat, type, per_hit

    Examples:
        "4 fire" → {dice: None, static: 4, stat: None, type: "fire", per_hit: False}
        "2d6+cha fire" → {dice: "2d6", static: 0, stat: "cha", type: "fire", per_hit: False}
        "+str/hit" → {dice: None, static: 0, stat: "str", type: None, per_hit: True}
        "1d8+str slashing" → {dice: "1d8", static: 0, stat: "str", type: "slashing", per_hit: False}
    """
    component_str = component_str.strip()

    # Check for /hit modifier
    per_hit = False
    if "/hit" in component_str.lower():
        per_hit = True
        component_str = component_str.lower().replace("/hit", "").strip()

    # Pattern: [dice][+/-static][+stat] [type]
    # Examples: "2d6+4+cha fire", "1d8+str slashing", "4 bludgeoning", "+cha"

    result = {
        "dice": None,
        "static": 0,
        "stat": None,
        "type": None,
        "per_hit": per_hit
    }

    # Split damage value from type
    parts = component_str.split()
    damage_part = parts[0] if parts else ""
    type_part = " ".join(parts[1:]) if len(parts) > 1 else None

    if type_part:
        result["type"] = type_part.lower()

    # Parse damage_part for dice, static, and stat
    # Valid stats: str, dex, con, int, wis, cha
    valid_stats = ['str', 'dex', 'con', 'int', 'wis', 'cha']

    # Extract stat modifier (e.g., "+cha", "-str")
    stat_pattern = r'([+-]?)(' + '|'.join(valid_stats) + r')'
    stat_match = re.search(stat_pattern, damage_part.lower())
    if stat_match:
        result["stat"] = stat_match.group(2)
        # Remove stat from damage_part for further parsing
        damage_part = damage_part[:stat_match.start()] + damage_part[stat_match.end():]

    # Extract dice notation (e.g., "2d6", "1d8")
    dice_match = re.search(r'\d+d\d+', damage_part.lower())
    if dice_match:
        result["dice"] = dice_match.group(0)
        # Remove dice from damage_part
        damage_part = damage_part[:dice_match.start()] + damage_part[dice_match.end():]

    # Parse remaining static value (e.g., "4", "+2", "-3")
    damage_part = damage_part.strip()
    if damage_part and damage_part not in ['+', '-']:
        try:
            result["static"] = int(damage_part)
        except ValueError:
            # If it's just "+" or invalid, static remains 0
            pass

    return result


def parse_damage_formula(formula_str: str) -> List[Dict]:
    """
    Parse complete damage formula into components.

    Args:
        formula_str: Full damage formula (e.g., "4 bludgeoning, 2d6+cha fire, +str")

    Returns:
        List of component dicts

    Examples:
        "4 fire, +cha" → [
            {dice: None, static: 4, stat: None, type: "fire", per_hit: False},
            {dice: None, static: 0, stat: "cha", type: None, per_hit: False}
        ]
    """
    if not formula_str or not formula_str.strip():
        return []

    components = []
    parts = formula_str.split(',')

    for part in parts:
        part = part.strip()
        if part:
            try:
                component = parse_damage_component(part)
                components.append(component)
            except Exception as e:
                # If parsing fails, skip this component
                print(f"[WARNING] Failed to parse damage component '{part}': {e}")
                continue

    return components


def calculate_damage(formula_str: str, stats_dict: Dict[str, int], hits: int = 1) -> Dict:
    """
    Calculate total damage from formula.

    Args:
        formula_str: Damage formula (e.g., "4 bludgeoning, 2d6+cha fire, +str")
        stats_dict: Character stats (e.g., {"str": 3, "cha": 4, ...})
        hits: Number of hits that landed (default 1)

    Returns:
        Dict with:
            - total: Total damage amount
            - breakdown: List of {type: str, amount: int} for display
            - success: Whether parsing succeeded

    Examples:
        calculate_damage("4 fire, +cha", {"cha": 3}, hits=2)
        → {
            "total": 11,
            "breakdown": [
                {"type": "fire", "amount": 8},
                {"type": "CHA", "amount": 3}
            ],
            "success": True
        }
    """
    result = {
        "total": 0,
        "breakdown": [],
        "success": True
    }

    try:
        components = parse_damage_formula(formula_str)

        if not components:
            result["success"] = False
            return result

        for comp in components:
            component_damage = 0

            # Roll dice if present
            if comp["dice"]:
                dice_total = sum(roll_dice(comp["dice"]) for _ in range(hits))
                component_damage += dice_total

            # Add static value (multiplied by hits if per_hit is True, or if there's no stat modifier)
            if comp["static"] != 0:
                if comp["per_hit"] or comp["stat"] is None:
                    component_damage += comp["static"] * hits
                else:
                    component_damage += comp["static"]

            # Add stat modifier
            if comp["stat"]:
                stat_value = stats_dict.get(comp["stat"], 0)
                if comp["per_hit"]:
                    component_damage += stat_value * hits
                else:
                    component_damage += stat_value

            # Determine display type
            if comp["stat"] and comp["type"] is None:
                # Pure stat modifier, show as "STR", "CHA", etc.
                display_type = comp["stat"].upper()
            elif comp["type"]:
                display_type = comp["type"]
            else:
                # No type specified, show as "damage"
                display_type = "damage"

            result["total"] += component_damage
            result["breakdown"].append({
                "type": display_type,
                "amount": component_damage
            })

    except Exception as e:
        print(f"[ERROR] Failed to calculate damage from formula '{formula_str}': {e}")
        result["success"] = False
        return result

    return result


def format_damage_breakdown(breakdown: List[Dict]) -> str:
    """
    Format damage breakdown for Discord display.

    Args:
        breakdown: List of {type: str, amount: int}

    Returns:
        Formatted string (e.g., "4 bludgeoning, 18 fire, 3 CHA")
    """
    if not breakdown:
        return ""

    parts = []
    for comp in breakdown:
        type_str = comp["type"] if comp["type"] else "damage"
        parts.append(f"{comp['amount']} {type_str}")

    return ", ".join(parts)
