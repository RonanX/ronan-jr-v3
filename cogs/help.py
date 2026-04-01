"""
Help commands explaining the combat system
"""

import discord
from discord import app_commands
from discord.ext import commands
from utils.constants import EmbedColors, Emoji


class HelpCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show help for the combat system")
    @app_commands.describe(topic="Specific topic to get help on")
    @app_commands.choices(topic=[
        app_commands.Choice(name="Getting Started", value="start"),
        app_commands.Choice(name="Characters", value="characters"),
        app_commands.Choice(name="Combat & Initiative", value="combat"),
        app_commands.Choice(name="Dice System", value="dice"),
        app_commands.Choice(name="Attacks", value="attacks"),
        app_commands.Choice(name="Moves", value="moves"),
        app_commands.Choice(name="Deployables", value="deployables"),
        app_commands.Choice(name="Save/Load", value="saveload"),
        app_commands.Choice(name="All Commands", value="commands")
    ])
    async def help_command(self, interaction: discord.Interaction, topic: str = "start"):
        """Show help information"""

        if topic == "start":
            embed = discord.Embed(
                title=f"{Emoji.INFO} Getting Started",
                description="Welcome to Ronan Jr v3! Here's how to get started:",
                color=EmbedColors.INFO
            )
            embed.add_field(
                name="1️⃣ Create Characters",
                value="Use `/char create [name]` to create characters with stats, HP, MP, and AC.",
                inline=False
            )
            embed.add_field(
                name="2️⃣ Start Combat",
                value="Use `/init start` to begin combat, then `/init add [character]` to roll initiative.",
                inline=False
            )
            embed.add_field(
                name="3️⃣ Take Turns",
                value="Use `/init next` to advance turns. Use `/attack` or `/move use` to fight!",
                inline=False
            )
            embed.add_field(
                name="4️⃣ Manage Combat",
                value="Track effects with `/effect`, summon helpers with `/deploy`, and save progress with `/save`.",
                inline=False
            )
            embed.set_footer(text="Use /help [topic] for detailed information on specific topics")

        elif topic == "characters":
            embed = discord.Embed(
                title=f"{Emoji.INFO} Character Management",
                description="Create and manage your characters:",
                color=EmbedColors.CHARACTER
            )
            embed.add_field(
                name="/char create [name]",
                value="Interactive character creation. Sets HP, MP, AC, movement, proficiency, and 6 stats (strength, dexterity, constitution, intelligence, wisdom, charisma). Stats must total 12-16.",
                inline=False
            )
            embed.add_field(
                name="/char show [name]",
                value="Display character sheet with all stats and current form.",
                inline=False
            )
            embed.add_field(
                name="/char update [name]",
                value="Modify character stats interactively.",
                inline=False
            )
            embed.add_field(
                name="/char delete [name]",
                value="Permanently delete a character (requires confirmation).",
                inline=False
            )
            embed.add_field(
                name="/char form add/swap",
                value="Add transformation forms or swap between them (costs 10 MP).",
                inline=False
            )

        elif topic == "combat":
            embed = discord.Embed(
                title=f"{Emoji.COMBAT} Combat & Initiative",
                description="Manage turn-based combat:",
                color=EmbedColors.COMBAT
            )
            embed.add_field(
                name="/init start",
                value="Start a new combat encounter. Prompts for autosave preference.",
                inline=False
            )
            embed.add_field(
                name="/init add [character]",
                value="Add character to initiative (rolls 1d20 + mobility).",
                inline=False
            )
            embed.add_field(
                name="/init show",
                value="Display current initiative order and turn.",
                inline=False
            )
            embed.add_field(
                name="/init next",
                value="Advance to next turn. Refreshes stars to 5, decrements effect/deployable durations, triggers autosave if enabled.",
                inline=False
            )
            embed.add_field(
                name="/init end",
                value="End combat and clear all combat state (requires confirmation).",
                inline=False
            )
            embed.add_field(
                name="/stars spend/show",
                value="Manage star resources (5 per turn).",
                inline=False
            )
            embed.add_field(
                name="/effect add/remove/list",
                value="Manage status effects with durations.",
                inline=False
            )

        elif topic == "dice":
            embed = discord.Embed(
                title=f"{Emoji.DICE} Dice System",
                description="Understanding the custom dice mechanics:",
                color=EmbedColors.INFO
            )
            embed.add_field(
                name="📊 Dice Pool System",
                value="Roll [stat rating]d6 and use the **highest single die**.\nStat ratings range from 0-4.",
                inline=False
            )
            embed.add_field(
                name="🎯 Hit Results (AC 10-12)",
                value="• **6+**: Clean Hit\n• **4-5**: Hit with Cost\n• **1-3**: Miss",
                inline=True
            )
            embed.add_field(
                name="🎯 Hit Results (AC 13-15)",
                value="• **6+**: Clean Hit\n• **5**: Hit with Cost\n• **1-4**: Miss",
                inline=True
            )
            embed.add_field(
                name="🎯 Hit Results (AC 16-18)",
                value="• **6**: Clean Hit\n• **5**: Hit with Cost\n• **1-4**: Miss",
                inline=True
            )
            embed.add_field(
                name="💥 Critical Hits",
                value="Rolling 2+ sixes in your dice pool = critical hit (double damage).",
                inline=False
            )
            embed.add_field(
                name="🎲 Advantage/Disadvantage",
                value="Roll double dice, split into halves, keep better/worse half.",
                inline=False
            )
            embed.add_field(
                name="🛡️ Saving Throws",
                value="Roll 1d20 + stat rating vs DC.",
                inline=False
            )

        elif topic == "attacks":
            embed = discord.Embed(
                title=f"{Emoji.COMBAT} Attack System",
                description="How to attack in combat:",
                color=EmbedColors.COMBAT
            )
            embed.add_field(
                name="/attack light [stat] [target]",
                value="Light attack - costs 1 star. Roll dice pool using chosen stat.",
                inline=False
            )
            embed.add_field(
                name="/attack medium [stat] [target]",
                value="Medium attack - costs 2 stars.",
                inline=False
            )
            embed.add_field(
                name="/attack heavy [stat] [target]",
                value="Heavy attack - costs 4 stars.",
                inline=False
            )
            embed.add_field(
                name="💔 Damage",
                value="On hit, you'll be prompted to enter damage. Clean hits deal full damage, crits deal double.",
                inline=False
            )
            embed.add_field(
                name="❌ Misses",
                value="Missing an attack means your combo breaks - no damage dealt, but stars are still spent.",
                inline=False
            )
            embed.add_field(
                name="/save [character] [type] [dc]",
                value="Force a target to make a saving throw (1d20 + stat vs DC).",
                inline=False
            )

        elif topic == "moves":
            embed = discord.Embed(
                title=f"{Emoji.EFFECT} Move System",
                description="Create and use custom movesets:",
                color=EmbedColors.CHARACTER
            )
            embed.add_field(
                name="/move create",
                value="Interactive move creation. Set name, type (light/medium/heavy), MP cost, stat, base damage, effect description, multihit count, cooldown, and uses.",
                inline=False
            )
            embed.add_field(
                name="/move use [name] [target]",
                value="Execute a saved move. Automatically spends stars/MP and rolls dice.",
                inline=False
            )
            embed.add_field(
                name="/move list",
                value="Show all moves for current form.",
                inline=False
            )
            embed.add_field(
                name="/move delete [name]",
                value="Remove a move from current form.",
                inline=False
            )
            embed.add_field(
                name="🎯 Multihit Moves",
                value="• **Clean Hit**: All hits land\n• **Hit with Cost**: Half hits land (rounded up)\n• **Miss**: 1 hit lands, combo breaks\n\nDamage = (base + stat) × hits × (2 if crit)",
                inline=False
            )
            embed.add_field(
                name="📋 Form-Based Movesets",
                value="Moves are tied to forms. Swapping forms changes your available moves.",
                inline=False
            )

        elif topic == "deployables":
            embed = discord.Embed(
                title=f"{Emoji.DEPLOYABLE} Deployable System",
                description="Summon helpers in combat:",
                color=EmbedColors.COMBAT
            )
            embed.add_field(
                name="/deploy create [name] [hp] [stars] [duration]",
                value="Summon a deployable (turret, drone, etc). Acts on your turn with its own star pool.",
                inline=False
            )
            embed.add_field(
                name="/deploy attack [deployable] [stat] [target]",
                value="Deployable performs an attack using its stars. Stat is a direct 0-4 rating.",
                inline=False
            )
            embed.add_field(
                name="/deploy damage [deployable] [amount]",
                value="Apply damage to a deployable. Destroyed at 0 HP.",
                inline=False
            )
            embed.add_field(
                name="/deploy list",
                value="Show all active deployables.",
                inline=False
            )
            embed.add_field(
                name="⏱️ Duration & Stars",
                value="• Stars refresh when owner's turn starts\n• Duration decrements each owner's turn\n• Deployables expire at 0 duration or 0 HP",
                inline=False
            )

        elif topic == "saveload":
            embed = discord.Embed(
                title=f"{Emoji.SAVE} Save/Load System",
                description="Persist combat state:",
                color=EmbedColors.SAVE
            )
            embed.add_field(
                name="/save [filename]",
                value="Save current combat state to `data/saves/[filename].json`. Includes all HP/MP/stars, effects, deployables, turn order, and round number.",
                inline=False
            )
            embed.add_field(
                name="/load [filename]",
                value="Load combat state from file. Validates file exists and has correct structure.",
                inline=False
            )
            embed.add_field(
                name="💾 Autosave",
                value="When starting combat, you can enable autosave. Saves as `autosave.json` after each turn automatically.",
                inline=False
            )
            embed.add_field(
                name="⚠️ Error Handling",
                value="System handles corrupt files, missing files, and incomplete data gracefully.",
                inline=False
            )

        elif topic == "commands":
            embed = discord.Embed(
                title=f"{Emoji.INFO} All Commands",
                description="Complete command reference:",
                color=EmbedColors.INFO
            )
            embed.add_field(
                name="📝 Characters",
                value="`/char create/show/update/delete/form`",
                inline=True
            )
            embed.add_field(
                name="⚔️ Combat",
                value="`/init start/add/show/next/end`\n`/attack [type] [stat] [target]`\n`/save [character] [type] [dc]`",
                inline=True
            )
            embed.add_field(
                name="⭐ Resources",
                value="`/stars spend/show`\n`/effect add/remove/list`",
                inline=True
            )
            embed.add_field(
                name="🎮 Moves",
                value="`/move create/use/list/delete`",
                inline=True
            )
            embed.add_field(
                name="🔧 Deployables",
                value="`/deploy create/attack/damage/list`",
                inline=True
            )
            embed.add_field(
                name="💾 Save/Load",
                value="`/save [filename]`\n`/load [filename]`",
                inline=True
            )
            embed.set_footer(text="Use /help [topic] for detailed information")

        else:
            embed = create_error_embed("Unknown Topic", "Please select a valid help topic.")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(HelpCommands(bot))
