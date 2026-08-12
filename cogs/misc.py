"""
Miscellaneous commands - /roll and other utility commands
"""

import discord
from discord import app_commands
from discord.ext import commands
import re
import random
import ast
import operator
import aiosqlite
import json
import logging

logger = logging.getLogger(__name__)
DATABASE_PATH = "database/ronan.db"


def safe_eval(expression: str) -> float:
    """
    Safely evaluate a mathematical expression using AST.
    Supports: +, -, *, /, //, %, **, parentheses
    """
    # Define allowed operations
    allowed_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    def eval_node(node):
        if isinstance(node, ast.Constant):  # Python 3.8+
            return node.value
        elif isinstance(node, ast.Num):  # Python 3.7 compat
            return node.n
        elif isinstance(node, ast.BinOp):
            left = eval_node(node.left)
            right = eval_node(node.right)
            op = allowed_ops.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operation: {type(node.op).__name__}")
            return op(left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = eval_node(node.operand)
            op = allowed_ops.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported unary operation: {type(node.op).__name__}")
            return op(operand)
        else:
            raise ValueError(f"Unsupported expression: {type(node).__name__}")

    try:
        tree = ast.parse(expression, mode='eval')
        result = eval_node(tree.body)
        return result
    except Exception as e:
        raise ValueError(f"Invalid expression: {e}")


async def get_character_stats(character_name: str) -> dict:
    """
    Fetch character stats from the database.
    Returns a dict with stat names (lowercase) mapped to their modifier values.
    Returns None if character not found.
    """
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT stats_json, stat_modifiers FROM characters WHERE name = ?",
                (character_name,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None

                # Parse base stats
                stats_json = json.loads(row[0]) if row[0] else {}
                stat_modifiers = json.loads(row[1]) if row[1] else {}

                # Combine base stats with modifiers to get final stat values
                final_stats = {}
                for stat, value in stats_json.items():
                    modifier = stat_modifiers.get(stat, 0)
                    final_value = value + modifier
                    # Calculate D&D-style modifier: (stat - 10) // 2
                    final_stats[stat.lower()] = (final_value - 10) // 2

                return final_stats
    except Exception as e:
        logger.error(f"Error fetching stats for {character_name}: {e}")
        return None


def parse_stat_references(expression: str, character_stats: dict) -> tuple:
    """
    Parse stat references like +str, -dex, (str), etc. and replace with actual values.
    Returns: (modified_expression, list of substitutions made)
    Example: "2d20+str-dex" with str=3, dex=2 -> "2d20+3-2", [("str", 3), ("dex", -2)]
    Example: "(str)d6" with str=3 -> "3d6", [("str", 3)]
    """
    if not character_stats:
        return expression, []

    substitutions = []

    # Pattern 1: Parenthesized stats like (str), (dex)
    paren_pattern = r'\((str|dex|con|int|wis|cha)\)'

    def replace_paren_stat(match):
        stat_name = match.group(1).lower()
        stat_value = character_stats.get(stat_name, 0)
        substitutions.append((stat_name.upper(), stat_value))
        return str(stat_value)

    # Pattern 2: +/- stats like +str, -dex
    sign_pattern = r'([+\-])(str|dex|con|int|wis|cha)'

    def replace_sign_stat(match):
        sign = match.group(1)
        stat_name = match.group(2).lower()
        stat_value = character_stats.get(stat_name, 0)

        # Track what we substituted
        actual_value = stat_value if sign == '+' else -stat_value
        substitutions.append((stat_name.upper(), actual_value))

        # Return the numeric value with proper sign
        if sign == '+':
            return f"+{stat_value}"
        else:
            return f"-{stat_value}"

    # Apply both patterns
    modified = re.sub(paren_pattern, replace_paren_stat, expression, flags=re.IGNORECASE)
    modified = re.sub(sign_pattern, replace_sign_stat, modified, flags=re.IGNORECASE)

    return modified, substitutions


def roll_dice(notation: str) -> tuple:
    """
    Roll dice from standard notation (e.g., 2d6, 1d20+3, d20).
    Supports shorthand: "d20" becomes "1d20"
    Returns: (rolls_list, notation_for_display)
    """
    # First, handle shorthand notation: d20 -> 1d20
    notation = re.sub(r'\bd(\d+)', r'1d\1', notation)

    # Match patterns like 2d6, 1d20, 3d8
    dice_pattern = r'(\d+)d(\d+)'

    def roll_replace(match):
        count = int(match.group(1))
        sides = int(match.group(2))

        if count > 100 or sides > 10000:
            raise ValueError("Dice count or sides too large")

        rolls = [random.randint(1, sides) for _ in range(count)]

        # Store rolls for display
        if not hasattr(roll_replace, 'all_rolls'):
            roll_replace.all_rolls = []
        roll_replace.all_rolls.append((f"{count}d{sides}", rolls))

        # Replace with sum for calculation
        return str(sum(rolls))

    # Reset rolls storage
    roll_replace.all_rolls = []

    # Replace all dice notation with their sums
    expression = re.sub(dice_pattern, roll_replace, notation)

    return roll_replace.all_rolls, expression


class MiscCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="roll", description="Roll dice (d20+str, 2d6+4, etc.)")
    @app_commands.describe(
        query="Dice notation with optional stats (d20+str, 2d6-dex, 4d6+3)",
        character="Character name for stat lookups",
        note="Optional label for the roll"
    )
    async def roll_dice_command(
        self,
        interaction: discord.Interaction,
        query: str,
        character: str = None,
        note: str = None
    ):
        """Generic dice rolling command with stat support"""
        try:
            original_query = query.strip()
            character_stats = None
            substitutions = []

            # Fetch character stats if provided
            if character:
                character_stats = await get_character_stats(character)
                if character_stats is None:
                    logger.warning(f"Character '{character}' not found for roll, using 0 for stats")
                    # Use empty dict so stat references default to 0
                    character_stats = {}

            # Parse stat references if we have a character
            if character:
                query, substitutions = parse_stat_references(query, character_stats)

            # Roll dice and get expression
            dice_rolls, expression = roll_dice(query)

            if not dice_rolls:
                await interaction.response.send_message(
                    "❌ No valid dice notation found (e.g., d20, 2d6, 1d8+3)",
                    ephemeral=True
                )
                return

            # Evaluate the expression safely
            result = safe_eval(expression)
            final_result = round(result)

            # Build compact embed
            embed = discord.Embed(color=0x5865F2)  # Blurple color

            # Build the main roll display line
            rolls_display_parts = []
            for dice_notation, rolls in dice_rolls:
                if len(rolls) == 1:
                    rolls_display_parts.append(f"`{rolls[0]}`")
                else:
                    rolls_str = ", ".join(map(str, rolls))
                    rolls_display_parts.append(f"`({rolls_str})`")

            rolls_display = " + ".join(rolls_display_parts)

            # Build description with note if present
            desc_parts = []

            # Note with colon
            if note:
                note_part = f"**{note}:**"
            else:
                note_part = None

            # Show original query with stat substitutions if any
            if substitutions:
                stat_info = " ".join([f"{name}={val:+d}" for name, val in substitutions])
                query_part = f"`{original_query}` ({stat_info})"
            else:
                query_part = f"`{original_query}`"

            # Result with arrow
            result_part = f"{rolls_display} → **{final_result}**"

            # Combine parts
            if note_part:
                embed.description = f"{note_part} {query_part} → {result_part}"
            else:
                embed.description = f"{query_part} → {result_part}"

            # Send ephemeral confirmation, then post to channel
            await interaction.response.send_message("✓ Rolled", ephemeral=True, delete_after=2)
            await interaction.channel.send(embed=embed)

            logger.info(f"[ROLL] {interaction.user.name} rolled {original_query} = {final_result}")

        except ValueError as e:
            await interaction.response.send_message(
                f"❌ Invalid dice notation: {str(e)}",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in roll command: {e}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="contest", description="Head-to-head roll contest between two participants")
    @app_commands.describe(
        roll1="First roll (d20+str, 2d6, etc.)",
        roll2="Second roll (d20+dex, 2d6, etc.)",
        note1="Label for first roll",
        note2="Label for second roll",
        character1="Character name for first roll's stat lookups",
        character2="Character name for second roll's stat lookups"
    )
    async def contest_command(
        self,
        interaction: discord.Interaction,
        roll1: str,
        roll2: str,
        note1: str = None,
        note2: str = None,
        character1: str = None,
        character2: str = None
    ):
        """Contest command for head-to-head rolls"""
        try:
            # Process Roll 1
            original_query1 = roll1.strip()
            stats1 = None
            subs1 = []

            if character1:
                stats1 = await get_character_stats(character1)
                if stats1 is None:
                    logger.warning(f"Character '{character1}' not found, using 0 for stats")
                    stats1 = {}

            if character1:
                roll1, subs1 = parse_stat_references(roll1, stats1)

            dice_rolls1, expression1 = roll_dice(roll1)
            if not dice_rolls1:
                await interaction.response.send_message(
                    f"❌ Invalid dice notation in roll1: {original_query1}",
                    ephemeral=True
                )
                return

            result1 = round(safe_eval(expression1))

            # Process Roll 2
            original_query2 = roll2.strip()
            stats2 = None
            subs2 = []

            if character2:
                stats2 = await get_character_stats(character2)
                if stats2 is None:
                    logger.warning(f"Character '{character2}' not found, using 0 for stats")
                    stats2 = {}

            if character2:
                roll2, subs2 = parse_stat_references(roll2, stats2)

            dice_rolls2, expression2 = roll_dice(roll2)
            if not dice_rolls2:
                await interaction.response.send_message(
                    f"❌ Invalid dice notation in roll2: {original_query2}",
                    ephemeral=True
                )
                return

            result2 = round(safe_eval(expression2))

            # Determine winner
            if result1 > result2:
                winner_indicator = "🏆"
                loser_indicator = ""
                color = 0x57F287  # Green
            elif result2 > result1:
                winner_indicator = ""
                loser_indicator = "🏆"
                color = 0xED4245  # Red
            else:
                winner_indicator = "🤝"
                loser_indicator = "🤝"
                color = 0xFEE75C  # Yellow

            # Build rolls display
            def format_rolls(dice_rolls):
                parts = []
                for _, rolls in dice_rolls:
                    if len(rolls) == 1:
                        parts.append(f"`{rolls[0]}`")
                    else:
                        rolls_str = ", ".join(map(str, rolls))
                        parts.append(f"`({rolls_str})`")
                return " + ".join(parts)

            rolls_display1 = format_rolls(dice_rolls1)
            rolls_display2 = format_rolls(dice_rolls2)

            # Build embed
            embed = discord.Embed(color=color)

            # Build left side (Roll 1)
            if note1:
                left_note = f"**{note1}:**"
            else:
                left_note = None

            if subs1:
                stat_info = " ".join([f"{n}={v:+d}" for n, v in subs1])
                left_query = f"`{original_query1}` ({stat_info})"
            else:
                left_query = f"`{original_query1}`"

            left_result = f"{rolls_display1} → **{result1}** {winner_indicator}"

            # Build right side (Roll 2)
            if note2:
                right_note = f"**{note2}:**"
            else:
                right_note = None

            if subs2:
                stat_info = " ".join([f"{n}={v:+d}" for n, v in subs2])
                right_query = f"`{original_query2}` ({stat_info})"
            else:
                right_query = f"`{original_query2}`"

            right_result = f"{rolls_display2} → **{result2}** {loser_indicator}"

            # Combine with VS divider
            if left_note:
                left_text = f"{left_note} {left_query} → {left_result}"
            else:
                left_text = f"{left_query} → {left_result}"

            if right_note:
                right_text = f"{right_note} {right_query} → {right_result}"
            else:
                right_text = f"{right_query} → {right_result}"

            embed.description = f"{left_text}\n**vs**\n{right_text}"

            # Send ephemeral confirmation, then post to channel
            await interaction.response.send_message("✓ Contest rolled", ephemeral=True, delete_after=2)
            await interaction.channel.send(embed=embed)

            logger.info(f"[CONTEST] {interaction.user.name}: {result1} vs {result2}")

        except ValueError as e:
            await interaction.response.send_message(
                f"❌ Invalid dice notation: {str(e)}",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in contest command: {e}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(MiscCommands(bot))
