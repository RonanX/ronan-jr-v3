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


def roll_dice(notation: str) -> tuple:
    """
    Roll dice from standard notation (e.g., 2d6, 1d20+3).
    Returns: (rolls_list, notation_for_display)
    """
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

    @app_commands.command(name="roll", description="Roll dice with standard notation (e.g., 2d6+4, 1d20*1.5)")
    @app_commands.describe(
        query="Dice notation and arithmetic (e.g., 2d6+4, (1d8+2)*1.5)",
        note="Optional note/label for the roll"
    )
    async def roll_dice_command(
        self,
        interaction: discord.Interaction,
        query: str,
        note: str = None
    ):
        """Generic dice rolling command"""
        try:
            # Roll dice and get expression
            dice_rolls, expression = roll_dice(query)

            if not dice_rolls:
                await interaction.response.send_message(
                    "❌ No valid dice notation found (e.g., 1d20, 2d6)",
                    ephemeral=True
                )
                return

            # Evaluate the expression safely
            result = safe_eval(expression)
            final_result = round(result)

            # Build display string
            # Format: 🎲 **[note]** | query ➔ (rolls) = **result**

            # Build rolls display
            rolls_display_parts = []
            for dice_notation, rolls in dice_rolls:
                if len(rolls) == 1:
                    rolls_display_parts.append(f"({rolls[0]})")
                else:
                    rolls_str = ", ".join(map(str, rolls))
                    rolls_display_parts.append(f"({rolls_str})")

            rolls_display = "+".join(rolls_display_parts) if len(dice_rolls) > 1 else rolls_display_parts[0]

            # Check if there's additional arithmetic beyond the dice rolls
            # If expression is different from just the sum, show the calculation
            query_simplified = query.strip()

            if note:
                output = f"🎲 **[{note}]** | {query_simplified} ➔ {rolls_display}"
            else:
                output = f"🎲 {query_simplified} ➔ {rolls_display}"

            # Add arithmetic if expression was more than just dice
            if expression != str(sum(sum(r) for _, r in dice_rolls)):
                # Show the arithmetic
                output += f" = **{final_result}**"
            else:
                # Just the dice result
                output += f" = **{final_result}**"

            await interaction.response.send_message(output)
            print(f"[ROLL] {interaction.user.name} rolled {query} = {final_result}")

        except ValueError as e:
            await interaction.response.send_message(
                f"❌ Invalid dice notation or expression: {str(e)}",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(MiscCommands(bot))
