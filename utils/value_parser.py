"""
Value parser for effects system
Supports three formats:
- Flat number: "5" or 5
- Dice string: "1d4", "2d6+1"
- Percentage: "10%" (of max HP/MP)
"""

import re
import random


def parse_value(value_str: str, max_value: int = None) -> int:
    """
    Parse a value string and return the calculated integer result.

    Args:
        value_str: String in format "5", "1d4", or "10%"
        max_value: Maximum value for percentage calculations (e.g., max_hp)

    Returns:
        Calculated integer value (minimum 1 for percentage if max_value > 0)

    Raises:
        ValueError: If format is invalid
    """
    value_str = str(value_str).strip()

    # Percentage format: "10%"
    if value_str.endswith('%'):
        if max_value is None or max_value == 0:
            return 0

        try:
            percentage = float(value_str.rstrip('%'))
            result = int((percentage / 100) * max_value)
            # Minimum 1 damage if max_value > 0
            return max(1, result)
        except ValueError:
            raise ValueError(f"Invalid percentage format: '{value_str}'")

    # Dice format: "1d4", "2d6+1", "1d20-5"
    dice_pattern = r'^(\d+)d(\d+)([\+\-]\d+)?$'
    match = re.match(dice_pattern, value_str, re.IGNORECASE)
    if match:
        num_dice = int(match.group(1))
        die_size = int(match.group(2))
        modifier = int(match.group(3)) if match.group(3) else 0

        if num_dice < 1 or die_size < 1:
            raise ValueError(f"Invalid dice format: '{value_str}' (dice must be >= 1)")

        # Roll the dice
        total = sum(random.randint(1, die_size) for _ in range(num_dice))
        return max(0, total + modifier)

    # Flat number format: "5" or "-3"
    try:
        return int(value_str)
    except ValueError:
        raise ValueError(f"Invalid value format: '{value_str}'. Expected flat number, dice (1d4), or percentage (10%)")


def validate_value_format(value_str: str) -> bool:
    """
    Check if a value string is in a valid format without calculating it.

    Args:
        value_str: String to validate

    Returns:
        True if format is valid, False otherwise
    """
    try:
        # Try to parse with a dummy max_value
        parse_value(value_str, max_value=100)
        return True
    except (ValueError, TypeError):
        return False
