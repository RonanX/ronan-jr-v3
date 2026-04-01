"""
Character management commands
"""

import discord
from discord import app_commands
from discord.ext import commands
import json
import logging
from typing import Optional
import aiosqlite
from utils.autocomplete import character_autocomplete, character_and_deployable_autocomplete

logger = logging.getLogger(__name__)

# Valid stat names (D&D stats)
STAT_NAMES = ["str", "dex", "con", "int", "wis", "cha"]


def create_health_bar(current_hp: int, max_hp: int, temp_hp: int) -> str:
    """
    Create visual health bar with temp HP using Discord emojis (5 blocks)
    Returns: formatted string with bar and text
    """
    if max_hp <= 0:
        return ":black_large_square:" * 5 + " (0%)"

    # Calculate percentages (5 blocks max)
    hp_percentage = (current_hp / max_hp)
    temp_percentage = (temp_hp / max_hp)

    # Calculate blocks
    hp_blocks = round(hp_percentage * 5)
    temp_blocks = round(temp_percentage * 5)

    # Build the bar with Discord emojis
    filled = ":green_square:" * hp_blocks  # Actual HP
    temp = ":white_large_square:" * temp_blocks  # Temp HP

    # Calculate empty blocks (only if no overflow)
    total_blocks = hp_blocks + temp_blocks
    if total_blocks <= 5:
        empty_blocks = 5 - total_blocks
        empty = ":black_large_square:" * empty_blocks
    else:
        empty = ""  # Overflow, no empty blocks

    bar = filled + temp + empty

    # Calculate percentages for display
    hp_percent = int(hp_percentage * 100)
    temp_percent = int(temp_percentage * 100)

    if temp_hp > 0:
        return f"{bar} ({hp_percent}% + {temp_percent}% temp)"
    else:
        return f"{bar} ({hp_percent}%)"


# Autocomplete functions now imported from utils.autocomplete


class CharacterCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    char_group = app_commands.Group(name="char", description="Character management commands")

    @char_group.command(name="create", description="Create a new character")
    @app_commands.describe(
        name="Character name",
        hp="Max HP",
        mp="Max MP",
        ac="AC Tier: 1 (easy/4-6 to hit), 2 (medium/5-6 to hit), 3 (hard/6 to hit)",
        stats="Stats as comma-separated values (str,dex,con,int,wis,cha)",
        tier="Power tier (rookie/veteran/elite) - determines proficiency and stat ranges",
        grunt="If true, HP/damage reduced to 50% (for disposable enemies)",
        max_stars="Maximum stars for this character (3-6, default 5)",
        threshold_damage="Damage threshold - CON save required if single hit exceeds this",
        threshold_dc="DC for threshold CON save",
        hidden_resources="If true, HP/MP/Stars/AC display as ??? in embeds",
        squishy="If true, character is squishy (takes extra damage)"
    )
    @app_commands.choices(
        tier=[
            app_commands.Choice(name="Rookie (Prof +2, 10-14 pts)", value="rookie"),
            app_commands.Choice(name="Veteran (Prof +3, 12-16 pts)", value="veteran"),
            app_commands.Choice(name="Elite (Prof +4, 16-20 pts)", value="elite")
        ],
        ac=[
            app_commands.Choice(name="Tier 1 (Easy - 4-6 to hit clean)", value=1),
            app_commands.Choice(name="Tier 2 (Medium - 5-6 to hit clean)", value=2),
            app_commands.Choice(name="Tier 3 (Hard - 6 to hit clean)", value=3)
        ]
    )
    async def create_character(
        self,
        interaction: discord.Interaction,
        name: str,
        hp: int,
        mp: int,
        ac: int,
        stats: str,
        tier: str = "veteran",
        grunt: bool = False,
        max_stars: int = 5,
        threshold_damage: Optional[int] = None,
        threshold_dc: Optional[int] = None,
        hidden_resources: bool = False,
        squishy: bool = False
    ):
        """Create a new character with inline parameters"""
        print(f"[CMD] {interaction.user.name} used /char create with params: name={name}, hp={hp}, mp={mp}, ac={ac}, stats={stats}, tier={tier}, grunt={grunt}, max_stars={max_stars}")
        try:
            # Set proficiency based on tier
            tier_config = {
                "rookie": {"prof": 2, "stat_min": 10, "stat_max": 14, "stat_cap": 4},
                "veteran": {"prof": 3, "stat_min": 12, "stat_max": 16, "stat_cap": 4},
                "elite": {"prof": 4, "stat_min": 16, "stat_max": 20, "stat_cap": 5}
            }

            config = tier_config[tier]
            prof = config["prof"]
            stat_min = config["stat_min"]
            stat_max = config["stat_max"]
            stat_cap = config["stat_cap"]

            # Check if character exists
            async with aiosqlite.connect('database/ronan.db') as db:
                async with db.execute(
                    "SELECT name FROM characters WHERE name = ?",
                    (name,)
                ) as cursor:
                    if await cursor.fetchone():
                        print(f"[ERROR] Character '{name}' already exists")
                        await interaction.response.send_message(
                            f"❌ Character '{name}' already exists!",
                            ephemeral=True
                        )
                        return

            # Validate HP and MP
            if hp <= 0:
                raise ValueError("HP must be positive")
            if mp <= 0:
                raise ValueError("MP must be positive")

            # Validate AC tier
            if ac not in [1, 2, 3]:
                raise ValueError("AC tier must be 1, 2, or 3")

            # Validate max_stars
            if max_stars < 3 or max_stars > 6:
                raise ValueError("max_stars must be between 3 and 6")

            # Parse and validate stats
            stat_values = [int(s.strip()) for s in stats.split(',')]

            if len(stat_values) != 6:
                raise ValueError("Must provide exactly 6 stats (str,dex,con,int,wis,cha)")

            for val in stat_values:
                if val < 1:
                    raise ValueError(f"Each stat must be at least 1 (minimum changed from 0 to 1)")
                if val > stat_cap:
                    raise ValueError(f"Each stat must be at most {stat_cap} for {tier} tier")

            total = sum(stat_values)
            # Soft warning if outside expected range, but allow creation
            if total < stat_min or total > stat_max:
                print(f"[WARN] Stats total {total} is outside expected range {stat_min}-{stat_max} for {tier} tier")
                # Send warning but don't block creation
                await interaction.response.send_message(
                    f"⚠️ **Warning:** Stats total {total} is outside the expected range {stat_min}-{stat_max} for {tier} tier.\n"
                    f"Expected ranges per tier:\n"
                    f"• Rookie: 10-14\n"
                    f"• Veteran: 12-16\n"
                    f"• Elite: 16-20\n"
                    f"Proceeding with character creation anyway...",
                    ephemeral=True
                )
                # Need to defer since we just sent a response
                already_responded = True
            else:
                already_responded = False

            stat_dict = {
                "str": stat_values[0],
                "dex": stat_values[1],
                "con": stat_values[2],
                "int": stat_values[3],
                "wis": stat_values[4],
                "cha": stat_values[5]
            }

            # Store base_stats for transformation comparison (initially same as stats)
            base_stats_json = json.dumps(stat_dict)

            # Initialize modifiers
            stat_modifiers_json = json.dumps({
                "str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0
            })

            roll_modifiers_json = json.dumps({
                "attack_modifier": 0,
                "save_modifier": 0,
                "incoming_modifier": 0
            })

            # Save to database
            async with aiosqlite.connect('database/ronan.db') as db:
                await db.execute(
                    """
                    INSERT INTO characters (
                        name, hp, max_hp, mp, max_mp, ac, proficiency,
                        stats_json, base_stats, stat_modifiers, roll_modifiers,
                        current_form, tier, grunt, max_stars, current_stars, temp_hp, temp_mp, ac_modifier, ac_modifier_source,
                        threshold_damage, threshold_dc, hidden_resources, squishy
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name, hp, hp, mp, mp, ac, prof,
                        json.dumps(stat_dict), base_stats_json, stat_modifiers_json, roll_modifiers_json,
                        "base", tier, 1 if grunt else 0, max_stars, max_stars, 0, 0, 0, "",
                        threshold_damage, threshold_dc, 1 if hidden_resources else 0, 1 if squishy else 0
                    )
                )
                await db.commit()

            tier_label = tier.capitalize()
            grunt_label = " [GRUNT]" if grunt else ""
            print(f"[OK] Character created: {name} ({tier_label}{grunt_label})")

            # Create success embed
            embed = discord.Embed(
                title="✅ Character Created!",
                description=f"**{name}** ({tier_label}{grunt_label})",
                color=discord.Color.green()
            )
            # AC tier label
            ac_labels = {1: "Tier 1 (Easy)", 2: "Tier 2 (Medium)", 3: "Tier 3 (Hard)"}
            ac_label = ac_labels.get(ac, f"Tier {ac}")

            embed.add_field(name="❤️ HP", value=f"{hp}/{hp}", inline=True)
            embed.add_field(name="💙 MP", value=f"{mp}/{mp}", inline=True)
            embed.add_field(name="🛡️ AC", value=ac_label, inline=True)
            embed.add_field(name="⭐ Proficiency", value=f"+{prof}", inline=True)

            stat_text = "\n".join([f"**{k.upper()}**: {v}" for k, v in stat_dict.items()])
            stat_total = sum(stat_dict.values())
            embed.add_field(name="📊 Stats", value=f"{stat_text}\n**Total**: {stat_total}", inline=False)

            # Send response (or followup if we already sent warning)
            if already_responded:
                await interaction.followup.send(embed=embed)
            else:
                await interaction.response.send_message(embed=embed)

        except ValueError as e:
            print(f"[ERROR] /char create validation failed: {str(e)}")
            await interaction.response.send_message(f"❌ Invalid input: {str(e)}", ephemeral=True)
        except Exception as e:
            logger.error(f"Error creating character: {e}", exc_info=True)
            print(f"[ERROR] /char create failed: {str(e)}")
            await interaction.response.send_message(
                f"❌ Error creating character: {str(e)}",
                ephemeral=True
            )

    @char_group.command(name="random", description="Generate a random character based on archetype")
    @app_commands.describe(
        name="Character name",
        archetype="Character archetype (determines HP/MP/AC ranges)",
        tier="Power tier (rookie/veteran/elite)",
        grunt="If true, HP/damage reduced to 50% (for disposable enemies)"
    )
    @app_commands.choices(archetype=[
        app_commands.Choice(name="Rushdown (HP 45-55, MP 70-90, AC 14-16)", value="rushdown"),
        app_commands.Choice(name="Swarm (HP 40-50, MP 80-100, AC 12-14)", value="swarm"),
        app_commands.Choice(name="Bruiser (HP 65-75, MP 60-80, AC 11-13)", value="bruiser"),
        app_commands.Choice(name="Duelist (HP 50-60, MP 90-110, AC 12-14)", value="duelist"),
        app_commands.Choice(name="Mage Fighter (HP 50-60, MP 140-160, AC 12-14)", value="mage_fighter"),
        app_commands.Choice(name="Zoner (HP 45-55, MP 110-130, AC 12-14)", value="zoner"),
        app_commands.Choice(name="Tactician (HP 50-60, MP 110-130, AC 12-14)", value="tactician"),
        app_commands.Choice(name="Controller (HP 45-55, MP 130-150, AC 12-14)", value="controller"),
        app_commands.Choice(name="Striker (HP 45-55, MP 90-110, AC 13-15)", value="striker"),
        app_commands.Choice(name="Assassin (HP 40-50, MP 80-100, AC 14-16)", value="assassin"),
        app_commands.Choice(name="Berserker (HP 70-80, MP 60-80, AC 11-13)", value="berserker"),
        app_commands.Choice(name="Tank (HP 75-85, MP 50-70, AC 10-12)", value="tank"),
        app_commands.Choice(name="Counter (HP 55-65, MP 80-100, AC 12-14)", value="counter_fighter"),
        app_commands.Choice(name="Grappler (HP 60-70, MP 50-70, AC 11-13)", value="grappler"),
        app_commands.Choice(name="Momentum (HP 50-60, MP 90-110, AC 13-15)", value="momentum"),
        app_commands.Choice(name="Punisher (HP 55-65, MP 100-120, AC 11-13)", value="punisher"),
        app_commands.Choice(name="Support (HP 45-55, MP 130-150, AC 12-14)", value="support"),
        app_commands.Choice(name="Phantom (HP 40-50, MP 90-110, AC 14-16)", value="phantom")
    ])
    @app_commands.choices(tier=[
        app_commands.Choice(name="Rookie (Prof +2, 10-14 pts)", value="rookie"),
        app_commands.Choice(name="Veteran (Prof +3, 12-16 pts)", value="veteran"),
        app_commands.Choice(name="Elite (Prof +4, 16-20 pts)", value="elite")
    ])
    async def random_character(
        self,
        interaction: discord.Interaction,
        name: str,
        archetype: str,
        tier: str = "veteran",
        grunt: bool = False
    ):
        """Generate a random character"""
        print(f"[CMD] {interaction.user.name} used /char random with params: name={name}, archetype={archetype}, tier={tier}, grunt={grunt}")
        try:
            import random

            # Archetype definitions (from STARFALL_LITE.md v3.0 - updated MP/AC for combo economy)
            archetypes = {
                "rushdown": {  # sustained pressure, star efficient combos
                    "hp_range": (45, 55), "mp_range": (70, 90), "ac_range": (14, 16),
                    "primary_stats": ["str", "dex"], "secondary_stats": ["con", "wis"]
                },
                "swarm": {  # excels vs groups, divides attention
                    "hp_range": (40, 50), "mp_range": (80, 100), "ac_range": (12, 14),
                    "primary_stats": ["dex"], "secondary_stats": ["str", "con"]
                },
                "bruiser": {  # durable, consistent all-rounder
                    "hp_range": (65, 75), "mp_range": (60, 80), "ac_range": (11, 13),
                    "primary_stats": ["str", "con"], "secondary_stats": ["dex"]
                },
                "duelist": {  # adaptable, balanced stats
                    "hp_range": (50, 60), "mp_range": (90, 110), "ac_range": (12, 14),
                    "primary_stats": ["dex"], "secondary_stats": ["str", "wis"]
                },
                "mage_fighter": {  # versatile toolkit, blend melee and magic
                    "hp_range": (50, 60), "mp_range": (140, 160), "ac_range": (12, 14),
                    "primary_stats": ["str", "int"], "secondary_stats": ["dex", "wis"]
                },
                "zoner": {  # controls engagement range, safe poke
                    "hp_range": (45, 55), "mp_range": (110, 130), "ac_range": (12, 14),
                    "primary_stats": ["dex", "int"], "secondary_stats": ["wis"]
                },
                "tactician": {  # battlefield control, enables setups
                    "hp_range": (50, 60), "mp_range": (110, 130), "ac_range": (12, 14),
                    "primary_stats": ["int", "wis"], "secondary_stats": ["cha"]
                },
                "controller": {  # shuts down threats, denies actions
                    "hp_range": (45, 55), "mp_range": (130, 150), "ac_range": (12, 14),
                    "primary_stats": ["int", "wis"], "secondary_stats": ["cha"]
                },
                "striker": {  # massive burst windows, high ceiling
                    "hp_range": (45, 55), "mp_range": (90, 110), "ac_range": (13, 15),
                    "primary_stats": ["str", "dex"], "secondary_stats": ["con"]
                },
                "assassin": {  # punishes mistakes, excels vs squishies
                    "hp_range": (40, 50), "mp_range": (80, 100), "ac_range": (14, 16),
                    "primary_stats": ["dex"], "secondary_stats": ["str", "int"]
                },
                "berserker": {  # threatens when wounded, trades favorably
                    "hp_range": (70, 80), "mp_range": (60, 80), "ac_range": (11, 13),
                    "primary_stats": ["str", "con"], "secondary_stats": ["dex"]
                },
                "tank": {  # survives focus fire, protects allies
                    "hp_range": (75, 85), "mp_range": (50, 70), "ac_range": (10, 12),
                    "primary_stats": ["con"], "secondary_stats": ["str", "wis"]
                },
                "counter_fighter": {  # punishes aggression, hard to pressure
                    "hp_range": (55, 65), "mp_range": (80, 100), "ac_range": (12, 14),
                    "primary_stats": ["dex", "wis"], "secondary_stats": ["str"]
                },
                "grappler": {  # locks down single target completely
                    "hp_range": (60, 70), "mp_range": (50, 70), "ac_range": (11, 13),
                    "primary_stats": ["str", "con"], "secondary_stats": ["dex"]
                },
                "momentum": {  # unstoppable late fight, scales hard
                    "hp_range": (50, 60), "mp_range": (90, 110), "ac_range": (13, 15),
                    "primary_stats": ["str", "dex"], "secondary_stats": ["con", "wis"]
                },
                "punisher": {  # exploits patterns, counters specific tactics
                    "hp_range": (55, 65), "mp_range": (100, 120), "ac_range": (11, 13),
                    "primary_stats": ["str", "dex"], "secondary_stats": ["wis"]
                },
                "support": {  # force multiplier, sustains team
                    "hp_range": (45, 55), "mp_range": (130, 150), "ac_range": (12, 14),
                    "primary_stats": ["wis", "cha"], "secondary_stats": ["int"]
                },
                "phantom": {  # hard to pin down, controls information
                    "hp_range": (40, 50), "mp_range": (90, 110), "ac_range": (14, 16),
                    "primary_stats": ["dex"], "secondary_stats": ["int", "cha"]
                }
            }

            arch = archetypes[archetype]

            # Tier configuration
            tier_config = {
                "rookie": {"prof": 2, "stat_min": 10, "stat_max": 14, "stat_cap": 4, "hp_mult": 0.7},
                "veteran": {"prof": 3, "stat_min": 12, "stat_max": 16, "stat_cap": 4, "hp_mult": 1.0},
                "elite": {"prof": 4, "stat_min": 16, "stat_max": 20, "stat_cap": 5, "hp_mult": 1.3}
            }

            config = tier_config[tier]

            # Generate HP/MP with tier/grunt modifiers
            base_hp = random.randint(*arch["hp_range"])
            base_mp = random.randint(*arch["mp_range"])

            hp = int(base_hp * config["hp_mult"])
            mp = int(base_mp * config["hp_mult"])  # Scale MP with tier too

            if grunt:
                hp = int(hp * 0.5)
                mp = int(mp * 0.5)

            # Generate AC tier - convert old range to tier choice
            # Old AC 10-12 -> Tier 1, 13-15 -> Tier 2, 16-18 -> Tier 3
            old_ac_min, old_ac_max = arch["ac_range"]
            tier_options = []
            if old_ac_min <= 12:
                tier_options.append(1)
            if old_ac_min <= 15 and old_ac_max >= 13:
                tier_options.append(2)
            if old_ac_max >= 16:
                tier_options.append(3)
            ac = random.choice(tier_options) if tier_options else 2  # Default to tier 2

            # Generate stats
            stat_min = config["stat_min"]
            stat_max = config["stat_max"]
            stat_cap = config["stat_cap"]

            # Start with all zeros
            stats = {"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0}

            # Determine point budget
            points_to_spend = random.randint(stat_min, stat_max)

            # Allocate to primary stats first (60-70% of points)
            primary_points = int(points_to_spend * random.uniform(0.6, 0.7))
            remaining_points = points_to_spend - primary_points

            # Distribute primary points
            for stat in arch["primary_stats"]:
                if len(arch["primary_stats"]) > 1:
                    allocation = random.randint(primary_points // len(arch["primary_stats"]) - 1,
                                               min(stat_cap, primary_points // len(arch["primary_stats"]) + 2))
                else:
                    allocation = min(stat_cap, primary_points)
                stats[stat] = min(stat_cap, allocation)

            # Distribute remaining points to secondary stats
            secondary_stats = arch["secondary_stats"]
            for stat in secondary_stats:
                if remaining_points > 0:
                    allocation = random.randint(0, min(stat_cap, remaining_points))
                    stats[stat] = min(stat_cap, allocation)
                    remaining_points -= allocation

            # Adjust to hit exact total (redistribute any leftover)
            current_total = sum(stats.values())
            while current_total < points_to_spend:
                # Add to a random stat that isn't capped
                eligible = [s for s in STAT_NAMES if stats[s] < stat_cap]
                if not eligible:
                    break
                stat_to_boost = random.choice(eligible)
                stats[stat_to_boost] += 1
                current_total += 1

            while current_total > points_to_spend:
                # Remove from a random stat that isn't 0
                eligible = [s for s in STAT_NAMES if stats[s] > 0]
                if not eligible:
                    break
                stat_to_reduce = random.choice(eligible)
                stats[stat_to_reduce] -= 1
                current_total -= 1

            # Store base_stats
            base_stats = stats.copy()

            # Check if character exists
            async with aiosqlite.connect('database/ronan.db') as db:
                async with db.execute(
                    "SELECT name FROM characters WHERE name = ?",
                    (name,)
                ) as cursor:
                    if await cursor.fetchone():
                        print(f"[ERROR] Character '{name}' already exists")
                        await interaction.response.send_message(
                            f"❌ Character '{name}' already exists!",
                            ephemeral=True
                        )
                        return

                # Save to database
                await db.execute(
                    """
                    INSERT INTO characters
                    (name, hp, max_hp, temp_hp, mp, max_mp, ac, proficiency, stats_json, base_stats_json, tier, grunt, current_form)
                    VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, 'base')
                    """,
                    (name, hp, hp, mp, mp, ac, config["prof"], json.dumps(stats), json.dumps(base_stats), tier, 1 if grunt else 0)
                )
                await db.commit()

            tier_label = tier.capitalize()
            grunt_label = " [GRUNT]" if grunt else ""
            print(f"[OK] Random character created: {name} ({archetype.capitalize()}, {tier_label}{grunt_label})")

            # Create success embed
            embed = discord.Embed(
                title="🎲 Random Character Created!",
                description=f"**{name}** - {archetype.capitalize()} ({tier_label}{grunt_label})",
                color=discord.Color.blue()
            )
            # AC tier label
            ac_labels = {1: "Tier 1 (Easy)", 2: "Tier 2 (Medium)", 3: "Tier 3 (Hard)"}
            ac_label = ac_labels.get(ac, f"Tier {ac}")

            embed.add_field(name="❤️ HP", value=f"{hp}/{hp}", inline=True)
            embed.add_field(name="💙 MP", value=f"{mp}/{mp}", inline=True)
            embed.add_field(name="🛡️ AC", value=ac_label, inline=True)
            embed.add_field(name="⭐ Proficiency", value=f"+{config['prof']}", inline=True)

            stat_text = "\n".join([f"**{k.upper()}**: {v}" for k, v in stats.items()])
            stat_total = sum(stats.values())
            embed.add_field(name="📊 Stats", value=f"{stat_text}\n**Total**: {stat_total}", inline=False)

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error creating random character: {e}", exc_info=True)
            print(f"[ERROR] /char random failed: {str(e)}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    """
    # COMMENTED OUT: Functionality moved to /char status
    @char_group.command(name="hp", description="Heal, damage, or add temp HP to a character")
    @app_commands.describe(
        name="Character name",
        amount="Amount (positive=heal, negative=damage)",
        temp="If true, adds temp HP instead of healing"
    )
    @app_commands.autocomplete(name=character_autocomplete)
    async def manage_hp(
        self,
        interaction: discord.Interaction,
        name: str,
        amount: int,
        temp: bool = False
    ):
        # [HP command code omitted - see git history if needed]
        pass
    """

    """
    # COMMENTED OUT: Functionality moved to /char status
    @char_group.command(name="stars", description="Add or subtract current stars for a character")
    @app_commands.describe(
        name="Character name",
        amount="Amount to add (positive) or subtract (negative)"
    )
    @app_commands.autocomplete(name=character_autocomplete)
    async def manage_stars(
        self,
        interaction: discord.Interaction,
        name: str,
        amount: int
    ):
        # [Stars command code omitted - see git history if needed]
        pass
    """

    @char_group.command(name="status", description="Check or update character resources")
    @app_commands.describe(
        character="Character name",
        hp="HP change (e.g., +10, -5) or 'senzu' to restore to max",
        mp="MP change (e.g., +10, -5) or 'senzu' to restore to max",
        stars="Stars change (e.g., +1, -1) or 'senzu' to restore to max",
        temp_hp="Temporary HP to add (replaces existing temp HP)",
        temp_mp="Temporary MP to add (replaces existing temp MP)",
        temp_stars="Temporary stars to add (replaces existing temp stars)",
        temp_duration="Rounds until temp resources expire (optional)"
    )
    @app_commands.autocomplete(character=character_autocomplete)
    async def character_status(
        self,
        interaction: discord.Interaction,
        character: str,
        hp: Optional[str] = None,
        mp: Optional[str] = None,
        stars: Optional[str] = None,
        temp_hp: Optional[int] = None,
        temp_mp: Optional[int] = None,
        temp_stars: Optional[int] = None,
        temp_duration: Optional[int] = None
    ):
        """Check character status or update resources"""
        # Defer ephemeral to prevent "user used command" bloat
        await interaction.response.defer(ephemeral=True)

        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Get character data including temp resources
                async with db.execute("""
                    SELECT hp, max_hp, mp, max_mp, current_stars, max_stars, ac,
                           temp_hp, temp_mp, temp_stars, hidden_resources
                    FROM characters WHERE name = ?
                """, (character,)) as cursor:
                    row = await cursor.fetchone()

                if not row:
                    print(f"[ERROR] Character '{character}' not found")
                    await interaction.followup.send(
                        f"❌ Character '{character}' not found!",
                        ephemeral=True
                    )
                    return

                old_hp, max_hp, old_mp, max_mp, old_stars, max_stars, ac, old_temp_hp, old_temp_mp, old_temp_stars, hidden_resources = row
                hidden_resources = bool(hidden_resources)
                old_temp_hp = old_temp_hp or 0
                old_temp_mp = old_temp_mp or 0
                old_temp_stars = old_temp_stars or 0

                # Check if in combat - use combat_state values for display if available
                async with db.execute("SELECT combat_active FROM initiative WHERE id = 1") as cursor:
                    init_row = await cursor.fetchone()
                    if init_row and init_row[0] == 1:
                        # In combat - check combat_state for current resources
                        async with db.execute("""
                            SELECT current_hp, current_mp, stars
                            FROM combat_state WHERE character_name = ?
                        """, (character,)) as cursor:
                            combat_row = await cursor.fetchone()
                            if combat_row:
                                old_hp = combat_row[0] if combat_row[0] is not None else old_hp
                                old_mp = combat_row[1] if combat_row[1] is not None else old_mp
                                old_stars = combat_row[2] if combat_row[2] is not None else old_stars
                                print(f"[COMBAT] Using combat_state for {character}: HP={old_hp}, MP={old_mp}, Stars={old_stars}")

                # Log actual DB values (not command kwargs)
                print(f"[CMD] {interaction.user.name} used /char status | {character}: HP={old_hp}/{max_hp}, MP={old_mp}/{max_mp}, Stars={old_stars}/{max_stars}, temp_hp={old_temp_hp}, temp_mp={old_temp_mp}, temp_stars={old_temp_stars} | Requested changes: hp={hp}, mp={mp}, stars={stars}, temp_hp={temp_hp}, temp_mp={temp_mp}, temp_stars={temp_stars}")

                # If no updates requested, show ephemeral status
                if hp is None and mp is None and stars is None and temp_hp is None and temp_mp is None and temp_stars is None:
                    # Build horizontal status embed (no title)
                    if hidden_resources:
                        status = f"❤️ `???`  💙 `???`  ⭐ `???`  🛡️ `???`"
                        print(f"[HIDDEN] {character} | HP: {old_hp}/{max_hp} | MP: {old_mp}/{max_mp} | Stars: {old_stars}/{max_stars} | AC: {ac}")
                    else:
                        status = f"❤️ {old_hp}/{max_hp}"
                        if old_temp_hp > 0:
                            status += f" (+{old_temp_hp} temp)"
                        status += f"  💙 {old_mp}/{max_mp}"
                        if old_temp_mp > 0:
                            status += f" (+{old_temp_mp} temp)"
                        status += f"  ⭐ {old_stars}/{max_stars}"
                        if old_temp_stars > 0:
                            status += f" (+{old_temp_stars} temp)"
                        status += f"  🛡️ {ac}"

                    embed = discord.Embed(description=status, color=discord.Color.blue())
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    print(f"[OK] Displayed status for {character}")
                    return

                # Parse updates
                new_hp = old_hp
                new_mp = old_mp
                new_stars = old_stars
                new_temp_hp = old_temp_hp
                new_temp_mp = old_temp_mp
                new_temp_stars = old_temp_stars
                deltas = []
                warnings = []

                # Regular resource updates (now support relative +/- syntax)
                if hp is not None:
                    if hp.lower() == "senzu":
                        new_hp = max_hp
                    else:
                        # Support relative syntax (+10, -5) or absolute (10)
                        hp_str = str(hp).strip()
                        if hp_str.startswith(('+', '-')):
                            # Relative change
                            delta = int(hp_str)
                            new_hp = max(0, min(old_hp + delta, max_hp))
                        else:
                            # Absolute value (backward compat)
                            new_hp = max(0, min(int(hp_str), max_hp))

                    if new_hp != old_hp:
                        deltas.append(f"❤️ {old_hp} → {new_hp}")

                if mp is not None:
                    if mp.lower() == "senzu":
                        new_mp = max_mp
                    else:
                        # Support relative syntax
                        mp_str = str(mp).strip()
                        if mp_str.startswith(('+', '-')):
                            delta = int(mp_str)
                            new_mp = max(0, min(old_mp + delta, max_mp))
                        else:
                            new_mp = max(0, min(int(mp_str), max_mp))

                    if new_mp != old_mp:
                        deltas.append(f"💙 {old_mp} → {new_mp}")

                if stars is not None:
                    if stars.lower() == "senzu":
                        new_stars = max_stars
                    else:
                        # Support relative syntax
                        stars_str = str(stars).strip()
                        if stars_str.startswith(('+', '-')):
                            delta = int(stars_str)
                            new_stars = max(0, min(old_stars + delta, max_stars))
                        else:
                            new_stars = max(0, min(int(stars_str), max_stars))

                    if new_stars != old_stars:
                        deltas.append(f"⭐ {old_stars} → {new_stars}")

                # Temporary resource updates (replaces existing temp resources)
                if temp_hp is not None:
                    new_temp_hp = max(0, temp_hp)  # No upper limit for temp resources
                    if old_temp_hp > 0 and new_temp_hp != old_temp_hp:
                        deltas.append(f"❤️ {old_hp}/{max_hp} (+{old_temp_hp} temp) → {new_hp}/{max_hp} (+{new_temp_hp} temp)")
                    elif new_temp_hp > 0:
                        deltas.append(f"❤️ {old_hp}/{max_hp} (+{new_temp_hp} temp)")

                if temp_mp is not None:
                    new_temp_mp = max(0, temp_mp)
                    if old_temp_mp > 0 and new_temp_mp != old_temp_mp:
                        deltas.append(f"💙 {old_mp}/{max_mp} (+{old_temp_mp} temp) → {new_mp}/{max_mp} (+{new_temp_mp} temp)")
                    elif new_temp_mp > 0:
                        deltas.append(f"💙 {old_mp}/{max_mp} (+{new_temp_mp} temp)")

                if temp_stars is not None:
                    new_temp_stars = max(0, temp_stars)
                    if old_temp_stars > 0 and new_temp_stars != old_temp_stars:
                        deltas.append(f"⭐ {old_stars}/{max_stars} (+{old_temp_stars} temp) → {new_stars}/{max_stars} (+{new_temp_stars} temp)")
                    elif new_temp_stars > 0:
                        deltas.append(f"⭐ {old_stars}/{max_stars} (+{new_temp_stars} temp)")

                # Update database
                await db.execute("""
                    UPDATE characters
                    SET hp = ?, mp = ?, current_stars = ?, temp_hp = ?, temp_mp = ?, temp_stars = ?
                    WHERE name = ?
                """, (new_hp, new_mp, new_stars, new_temp_hp, new_temp_mp, new_temp_stars, character))

                # Sync with combat_state if combat is active (critical for star sync!)
                async with db.execute("SELECT combat_active FROM initiative WHERE id = 1") as cursor:
                    init_row = await cursor.fetchone()
                    if init_row and init_row[0] == 1:
                        # Check if character is in the active combat
                        async with db.execute("SELECT 1 FROM combat_state WHERE character_name = ?", (character,)) as check:
                            if await check.fetchone():
                                await db.execute("""
                                    UPDATE combat_state
                                    SET current_hp = ?, current_mp = ?, stars = ?
                                    WHERE character_name = ?
                                """, (new_hp, new_mp, new_stars, character))
                                print(f"[SYNC] Updated combat_state for {character}: HP={new_hp}, MP={new_mp}, Stars={new_stars}")

                await db.commit()

                # Handle temp resource duration tracking
                if temp_duration is not None and (temp_hp is not None or temp_mp is not None or temp_stars is not None):
                    # Check if in combat to add effect
                    async with db.execute("SELECT combat_active FROM initiative WHERE id = 1") as cursor:
                        init_row = await cursor.fetchone()
                        if init_row and init_row[0] == 1:
                            # Get current round
                            async with db.execute("SELECT round_num FROM combat WHERE id = 1") as cursor:
                                combat_row = await cursor.fetchone()
                                current_round = combat_row[0] if combat_row else 1

                            # Remove existing "Temporary Resources" effect
                            async with db.execute("""
                                SELECT effects_json FROM combat_state WHERE character_name = ?
                            """, (character,)) as cursor:
                                state_row = await cursor.fetchone()
                                if state_row and state_row[0]:
                                    effects = json.loads(state_row[0])
                                    effects = [e for e in effects if e.get("name") != "Temporary Resources"]
                                else:
                                    effects = []

                            # Add new temp resource effect
                            effects.append({
                                "name": "Temporary Resources",
                                "duration": temp_duration,
                                "applied_round": current_round,
                                "temp_hp": new_temp_hp if temp_hp is not None else 0,
                                "temp_mp": new_temp_mp if temp_mp is not None else 0,
                                "temp_stars": new_temp_stars if temp_stars is not None else 0
                            })

                            await db.execute("""
                                UPDATE combat_state SET effects_json = ? WHERE character_name = ?
                            """, (json.dumps(effects), character))
                            await db.commit()

                            warnings.append(f"⚠️ temp resources expire in {temp_duration} rounds")
                        else:
                            warnings.append(f"⚠️ temp_duration requires active combat (resources are permanent)")

                # Build visible embed with flavor text
                await interaction.delete_original_response()

                # Determine embed type based on changes
                if hp is not None and hp != "senzu":
                    # HP change detected
                    hp_delta = new_hp - old_hp
                    if hp_delta > 0:
                        # Healing
                        embed = discord.Embed(
                            title=f"💚 Healing",
                            description=f"**{character}** heals {hp_delta} HP!",
                            color=discord.Color.green()
                        )
                    elif hp_delta < 0:
                        # Damage
                        damage = abs(hp_delta)
                        embed = discord.Embed(
                            title=f"💥 Damage",
                            description=f"**{character}** takes {damage} damage!",
                            color=discord.Color.red()
                        )
                    else:
                        embed = discord.Embed(
                            description=f"**{character}** HP unchanged",
                            color=discord.Color.light_gray()
                        )

                    # Add HP display
                    if not hidden_resources:
                        hp_display = f"❤️ {new_hp}/{max_hp}"
                        if new_temp_hp > 0:
                            hp_display += f" (+{new_temp_hp} temp)"
                        embed.add_field(name="HP", value=hp_display, inline=False)
                    else:
                        embed.add_field(name="HP", value="???", inline=False)
                        print(f"[HIDDEN] {character} | HP: {new_hp}/{max_hp}")

                elif stars is not None and stars != "senzu":
                    # Stars change detected
                    star_delta = new_stars - old_stars
                    if star_delta > 0:
                        embed = discord.Embed(
                            title=f"⭐ Stars Gained",
                            description=f"**{character}** gains {star_delta} star(s)!",
                            color=discord.Color.gold()
                        )
                    elif star_delta < 0:
                        embed = discord.Embed(
                            title=f"⭐ Stars Used",
                            description=f"**{character}** uses {abs(star_delta)} star(s)!",
                            color=discord.Color.orange()
                        )
                    else:
                        embed = discord.Embed(
                            description=f"**{character}** stars unchanged",
                            color=discord.Color.light_gray()
                        )

                    # Add stars display
                    if not hidden_resources:
                        star_display = "⭐" * new_stars + "✴️" * (max_stars - new_stars)
                        embed.add_field(name="Stars", value=f"{star_display} {new_stars}/{max_stars}", inline=False)
                    else:
                        embed.add_field(name="Stars", value="???", inline=False)
                        print(f"[HIDDEN] {character} | Stars: {new_stars}/{max_stars}")

                elif mp is not None and mp != "senzu":
                    # MP change detected
                    mp_delta = new_mp - old_mp
                    if mp_delta > 0:
                        # MP restored
                        embed = discord.Embed(
                            title=f"💙 MP Restored",
                            description=f"**{character}** recovers {mp_delta} MP!",
                            color=discord.Color.blue()
                        )
                    elif mp_delta < 0:
                        # MP spent
                        spent = abs(mp_delta)
                        embed = discord.Embed(
                            title=f"💙 MP Spent",
                            description=f"**{character}** spends {spent} MP!",
                            color=discord.Color.purple()
                        )
                    else:
                        embed = discord.Embed(
                            description=f"**{character}** MP unchanged",
                            color=discord.Color.light_gray()
                        )

                    # Add MP display
                    if not hidden_resources:
                        mp_display = f"💙 {new_mp}/{max_mp}"
                        if new_temp_mp > 0:
                            mp_display += f" (+{new_temp_mp} temp)"
                        embed.add_field(name="MP", value=mp_display, inline=False)
                    else:
                        embed.add_field(name="MP", value="???", inline=False)
                        print(f"[HIDDEN] {character} | MP: {new_mp}/{max_mp}")

                elif temp_hp is not None and temp_hp > 0:
                    # Temp HP added
                    embed = discord.Embed(
                        title=f"🛡️ Temp HP",
                        description=f"**{character}** gains {temp_hp} temporary HP!",
                        color=discord.Color.blue()
                    )
                    if not hidden_resources:
                        embed.add_field(name="HP", value=f"❤️ {new_hp}/{max_hp} (+{new_temp_hp} temp)", inline=False)
                    else:
                        embed.add_field(name="HP", value="???", inline=False)

                elif deltas:
                    # Multiple changes - compact format
                    description = f"**{character}**: {', '.join(deltas)}"
                    if warnings:
                        description += f"\n{' '.join(warnings)}"
                    embed = discord.Embed(description=description, color=discord.Color.green())
                else:
                    # No changes
                    embed = discord.Embed(description=f"**{character}**: no changes", color=discord.Color.light_gray())

                await interaction.channel.send(embed=embed)
                print(f"[OK] Updated {character}: hp={old_hp}→{new_hp}, mp={old_mp}→{new_mp}, stars={old_stars}→{new_stars}, temp_hp={old_temp_hp}→{new_temp_hp}, temp_mp={old_temp_mp}→{new_temp_mp}, temp_stars={old_temp_stars}→{new_temp_stars}")

        except ValueError as e:
            embed = discord.Embed(
                description="❌ Invalid value: use numbers, +/- for relative, or 'senzu'",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in char status: {e}", exc_info=True)
            print(f"[ERROR] /char status failed: {str(e)}")
            embed = discord.Embed(
                description=f"❌ Error: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @char_group.command(name="update", description="Update a character's stat or resource")
    @app_commands.describe(
        name="Character name",
        field="Field to update (hp, mp, ac (tier 1-3), proficiency, max_stars, threshold_damage, threshold_dc, hidden_resources, squishy, or stat name)",
        value="New value"
    )
    @app_commands.autocomplete(name=character_autocomplete)
    async def update_character(
        self,
        interaction: discord.Interaction,
        name: str,
        field: str,
        value: str
    ):
        """Update a character's field"""
        print(f"[CMD] {interaction.user.name} used /char update | name={name}, field={field}, value={value}")
        try:
            field = field.lower()

            async with aiosqlite.connect('database/ronan.db') as db:
                # Get character
                async with db.execute(
                    "SELECT * FROM characters WHERE name = ?",
                    (name,)
                ) as cursor:
                    row = await cursor.fetchone()

                if not row:
                    print(f"[ERROR] Character '{name}' not found")
                    await interaction.response.send_message(
                        f"❌ Character '{name}' not found!",
                        ephemeral=True
                    )
                    return

                # Parse existing data
                stats = json.loads(row[8])

                # Update based on field
                if field in ["hp", "mp", "ac", "proficiency", "max_stars", "threshold_damage", "threshold_dc", "hidden_resources", "squishy"]:
                    # Direct column updates
                    if field in ["hidden_resources", "squishy"]:
                        # Boolean fields
                        bool_value = value.lower() in ["true", "1", "yes"]
                        await db.execute(
                            f"UPDATE characters SET {field} = ? WHERE name = ?",
                            (1 if bool_value else 0, name)
                        )
                    elif field in ["threshold_damage", "threshold_dc"]:
                        # Optional integer fields (can be NULL)
                        int_value = int(value) if value.lower() != "null" else None
                        await db.execute(
                            f"UPDATE characters SET {field} = ? WHERE name = ?",
                            (int_value, name)
                        )
                    else:
                        # Required integer fields
                        int_value = int(value)

                        if field == "hp":
                            max_hp = row[2]
                            if int_value < 0 or int_value > max_hp:
                                raise ValueError(f"HP must be 0-{max_hp}")
                            await db.execute(
                                "UPDATE characters SET hp = ? WHERE name = ?",
                                (int_value, name)
                            )
                        elif field == "mp":
                            max_mp = row[4]
                            if int_value < 0 or int_value > max_mp:
                                raise ValueError(f"MP must be 0-{max_mp}")
                            await db.execute(
                                "UPDATE characters SET mp = ? WHERE name = ?",
                                (int_value, name)
                            )
                        elif field == "ac":
                            if int_value not in [1, 2, 3]:
                                raise ValueError("AC tier must be 1, 2, or 3")
                            await db.execute(
                                "UPDATE characters SET ac = ? WHERE name = ?",
                                (int_value, name)
                            )
                        elif field == "proficiency":
                            if int_value not in [2, 3, 4]:
                                raise ValueError("Proficiency must be 2, 3, or 4")
                            await db.execute(
                                "UPDATE characters SET proficiency = ? WHERE name = ?",
                                (int_value, name)
                            )
                        elif field == "max_stars":
                            if int_value < 3 or int_value > 6:
                                raise ValueError("max_stars must be 3-6")
                            await db.execute(
                                "UPDATE characters SET max_stars = ? WHERE name = ?",
                                (int_value, name)
                            )

                elif field in STAT_NAMES:
                    # Stat updates
                    int_value = int(value)
                    if int_value < 0 or int_value > 4:
                        raise ValueError("Stats must be 0-4")

                    stats[field] = int_value
                    await db.execute(
                        "UPDATE characters SET stats_json = ? WHERE name = ?",
                        (json.dumps(stats), name)
                    )
                else:
                    print(f"[ERROR] Unknown field '{field}'")
                    await interaction.response.send_message(
                        f"❌ Unknown field '{field}'. Valid fields: hp, mp, ac, proficiency, "
                        f"{', '.join(STAT_NAMES)}",
                        ephemeral=True
                    )
                    return

                await db.commit()

            print(f"[OK] Updated {name}: {field} = {value}")
            await interaction.response.send_message(
                f"✅ Updated **{name}**: {field} = {value}"
            )

        except ValueError as e:
            print(f"[ERROR] /char update validation failed: {str(e)}")
            await interaction.response.send_message(f"❌ Invalid value: {str(e)}", ephemeral=True)
        except Exception as e:
            logger.error(f"Error updating character: {e}", exc_info=True)
            print(f"[ERROR] /char update failed: {str(e)}")
            await interaction.response.send_message(
                f"❌ Error updating character: {str(e)}",
                ephemeral=True
            )

    @char_group.command(name="show", description="Display character sheet")
    @app_commands.describe(name="Character name")
    @app_commands.autocomplete(name=character_autocomplete)
    async def show_character(self, interaction: discord.Interaction, name: str):
        """Display character sheet"""
        print(f"[CMD] {interaction.user.name} used /char show with params: name={name}")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Get character data with explicit column selection
                async with db.execute(
                    """SELECT name, hp, max_hp, mp, max_mp, ac, proficiency, stats_json,
                       temp_hp, tier, grunt, base_stats_json, max_stars, temp_mp, ac_modifier, ac_modifier_source,
                       base_stats, stat_modifiers, roll_modifiers, current_form, current_stars, temp_stars, hidden_resources
                    FROM characters WHERE name = ?""",
                    (name,)
                ) as cursor:
                    row = await cursor.fetchone()

                if not row:
                    print(f"[ERROR] Character '{name}' not found")
                    await interaction.response.send_message(
                        f"❌ Character '{name}' not found!",
                        ephemeral=True
                    )
                    return

                # Parse character data
                char_name = row[0]
                current_hp = row[1]
                max_hp = row[2]
                current_mp = row[3]
                max_mp = row[4]
                ac = row[5]
                proficiency = row[6]
                stats = json.loads(row[7])
                temp_hp = row[8] if row[8] is not None else 0
                tier = row[9] if row[9] else "veteran"
                grunt = row[10] if row[10] else 0
                base_stats_json = row[11]
                base_stats = json.loads(base_stats_json) if base_stats_json else stats
                max_stars = row[12] if row[12] is not None else 5
                temp_mp = row[13] if row[13] is not None else 0
                ac_modifier = row[14] if row[14] is not None else 0
                ac_modifier_source = row[15] if row[15] else ""
                # New modifier columns
                base_stats_db = json.loads(row[16]) if row[16] else stats
                stat_modifiers = json.loads(row[17]) if row[17] else {"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0}
                roll_modifiers = json.loads(row[18]) if row[18] else {"attack_modifier": 0, "save_modifier": 0, "incoming_modifier": 0}
                current_form = row[19] if row[19] else "base"
                db_current_stars = row[20] if row[20] is not None else max_stars
                temp_stars = row[21] if row[21] is not None else 0
                hidden_resources = bool(row[22]) if row[22] is not None else False

                # Health bar helper (5 blocks)
                def generate_health_bar(current, maximum, temp=0):
                    """Generate 5-block health bar with Discord emojis
                    Fills left to right: permanent (green) from left, temp (white) from right, empty (black) in middle
                    """
                    if maximum <= 0:
                        return ":black_large_square:" * 5, 0

                    # Calculate blocks for permanent HP (out of 5)
                    hp_blocks = max(0, min(5, round((current / maximum) * 5)))

                    # Calculate missing blocks (empty space)
                    missing_blocks = max(0, 5 - hp_blocks)

                    # Calculate temp blocks - always show at least 1 if temp > 0
                    if temp > 0:
                        temp_blocks = max(1, round((temp / maximum) * 5))
                    else:
                        temp_blocks = 0

                    # Build bar: green from left, black in middle, white from right
                    # Temp blocks CAN exceed the 5-block limit to show overhealing
                    bar = (":green_square:" * hp_blocks +
                           ":black_large_square:" * missing_blocks +
                           ":white_large_square:" * temp_blocks)

                    # Calculate percentage
                    total_effective_hp = current + temp
                    percentage = int((total_effective_hp / maximum) * 100)

                    return bar, percentage

                # MP bar helper (5 blocks with temp MP support)
                def generate_mp_bar(current, maximum, temp=0):
                    """Generate 5-block MP bar with Discord emojis
                    Fills left to right: permanent (blue) from left, temp (white) from right, empty (black) in middle
                    """
                    if maximum <= 0:
                        return ":black_large_square:" * 5, 0

                    # Calculate blocks for permanent MP (out of 5)
                    mp_blocks = max(0, min(5, round((current / maximum) * 5)))

                    # Calculate missing blocks (empty space)
                    missing_blocks = max(0, 5 - mp_blocks)

                    # Calculate temp blocks - always show at least 1 if temp > 0
                    if temp > 0:
                        temp_blocks = max(1, round((temp / maximum) * 5))
                    else:
                        temp_blocks = 0

                    # Build bar: blue from left, black in middle, white from right
                    # Temp blocks CAN exceed the 5-block limit to show overhealing
                    bar = (":blue_square:" * mp_blocks +
                           ":black_large_square:" * missing_blocks +
                           ":white_large_square:" * temp_blocks)

                    # Calculate percentage
                    total_effective_mp = current + temp
                    percentage = int((total_effective_mp / maximum) * 100)

                    return bar, percentage

                # Check if in combat for stars and effects
                in_combat = False
                current_stars = db_current_stars  # Use database value as default
                effects = []
                async with db.execute("SELECT combat_active FROM initiative WHERE id = 1") as cursor:
                    init_row = await cursor.fetchone()
                    if init_row and init_row[0] == 1:
                        in_combat = True
                        # Get stars and effects from combat_state
                        async with db.execute(
                            "SELECT stars, effects_json FROM combat_state WHERE character_name = ?",
                            (char_name,)
                        ) as combat_cursor:
                            combat_row = await combat_cursor.fetchone()
                            if combat_row:
                                current_stars = combat_row[0]  # Override with combat state if in combat
                                if combat_row[1]:
                                    effects = json.loads(combat_row[1])

                # Calculate Save DC = 8 + prof + highest mental stat (using effective stats)
                effective_int = base_stats_db.get('int', 0) + stat_modifiers.get('int', 0)
                effective_wis = base_stats_db.get('wis', 0) + stat_modifiers.get('wis', 0)
                effective_cha = base_stats_db.get('cha', 0) + stat_modifiers.get('cha', 0)
                save_dc = 8 + proficiency + max(effective_int, effective_wis, effective_cha)

                # Build bars (returns bar and percentage separately)
                hp_bar, hp_pct = generate_health_bar(current_hp, max_hp, temp_hp)
                mp_bar, mp_pct = generate_mp_bar(current_mp, max_mp, temp_mp)

                # === RESOURCES SECTION ===
                # Check if resources should be hidden
                if hidden_resources:
                    # Show ??? for all resources
                    hp_line = f"❤️ **HP:** `???`"
                    stars_line = f"⭐ **Stars:** `???`"
                    mp_line = f"💙 **MP:** `???`"
                    ac_line = f"🛡️ **AC:** `???`"
                    # Log actual values for debugging
                    print(f"[HIDDEN] {char_name} | HP: {current_hp}/{max_hp} | MP: {current_mp}/{max_mp} | Stars: {current_stars}/{max_stars} | AC: {ac}")
                else:
                    # HP line with temp values
                    hp_line = f"❤️ **HP:** `{current_hp}/{max_hp}`"
                    if temp_hp > 0:
                        hp_line += f" `(+{temp_hp} temp)`"
                    hp_line += f"  {hp_bar} ({hp_pct}%)"

                    # Stars line with bar: yellow from left, black in middle, white from right
                    stars_pct = int((current_stars / max_stars) * 100) if max_stars > 0 else 0
                    empty_stars_count = max(0, max_stars - current_stars - temp_stars)

                    # Build star bar: filled from left, empty in middle, temp from right
                    filled_stars = ":yellow_square:" * current_stars
                    empty_stars = ":black_large_square:" * empty_stars_count
                    temp_star_display = ":white_large_square:" * temp_stars

                    stars_line = f"⭐ **Stars:** `{current_stars}/{max_stars}"
                    if temp_stars > 0:
                        stars_line += f" (+{temp_stars} temp)`  {filled_stars}{empty_stars}{temp_star_display} ({stars_pct}%)"
                    else:
                        # If no temp stars, use empty blocks instead of ✴️
                        empty_for_display = ":black_large_square:" * (max_stars - current_stars)
                        stars_line += f"`  {filled_stars}{empty_for_display} ({stars_pct}%)"

                    # MP line with temp values
                    mp_line = f"💙 **MP:** `{current_mp}/{max_mp}`"
                    if temp_mp > 0:
                        mp_line += f" `(+{temp_mp} temp)`"
                    mp_line += f"  {mp_bar} ({mp_pct}%)"

                    # AC line with modifiers - show tier and label
                    ac_labels = {1: "Tier 1 (Easy)", 2: "Tier 2 (Medium)", 3: "Tier 3 (Hard)"}
                    ac_label = ac_labels.get(ac, f"Tier {ac}")
                    ac_line = f"🛡️ **AC:** `{ac_label}`"
                    if ac_modifier != 0:
                        sign = '+' if ac_modifier > 0 else ''
                        effective_tier = max(1, min(3, ac + ac_modifier))  # Keep in 1-3 range
                        effective_label = ac_labels.get(effective_tier, f"Tier {effective_tier}")
                        ac_line += f" `→ {effective_label} ({sign}{ac_modifier} {ac_modifier_source})`"

                # Build resources value (skip MP if max_mp is 0)
                if max_mp == 0:
                    resources_value = f"{hp_line}\n{stars_line}\n{ac_line}"
                else:
                    resources_value = f"{hp_line}\n{stars_line}\n{mp_line}\n{ac_line}"

                # === STATS SECTION ===
                # Check if stats should be hidden
                if hidden_resources:
                    stats_col = "???"
                    info_col = "???"
                else:
                    # Calculate effective stats: base_stats + stat_modifiers
                    stats_lines = []
                    for stat_name in ['str', 'dex', 'con', 'int', 'wis', 'cha']:
                        base_val = base_stats_db.get(stat_name, 0)
                        mod_val = stat_modifiers.get(stat_name, 0)
                        effective_val = base_val + mod_val

                        if mod_val != 0:
                            sign = '+' if mod_val > 0 else ''
                            stats_lines.append(f"**{stat_name.upper()}:** `{effective_val}` `({sign}{mod_val})`")
                        else:
                            stats_lines.append(f"**{stat_name.upper()}:** `{effective_val}`")

                    # Format as two columns (3 stats each)
                    stats_col = f"{stats_lines[0]}  {stats_lines[3]}\n{stats_lines[1]}  {stats_lines[4]}\n{stats_lines[2]}  {stats_lines[5]}"

                    # Info column
                    info_col = f"**Proficiency:** `+{proficiency}`\n**Save DC:** `{save_dc}`"

                # Create embed with title
                # Show current form in title if not base
                title = f"━━━━━ {char_name} ━━━━━"
                if current_form != "base":
                    title = f"━━━━━ {char_name} ({current_form} form) ━━━━━"

                embed = discord.Embed(
                    title=title,
                    color=discord.Color.gold() if current_form != "base" else discord.Color.blue()
                )

                # Add tier to description (hide if resources hidden)
                if hidden_resources:
                    embed.description = "???"
                else:
                    tier_display = tier.capitalize() if tier else "Veteran"
                    embed.description = f"{tier_display}"

                # Add resources field
                embed.add_field(
                    name="━━━━━ Resources ━━━━━",
                    value=resources_value,
                    inline=False
                )

                # Add stats and info as inline fields
                embed.add_field(name="📊 Stats", value=stats_col, inline=True)
                embed.add_field(name="🎓 Info", value=info_col, inline=True)

                # Add roll modifiers section if any are non-zero
                if roll_modifiers['attack_modifier'] != 0 or roll_modifiers['save_modifier'] != 0 or roll_modifiers['incoming_modifier'] != 0:
                    mod_lines = []

                    if roll_modifiers['attack_modifier'] != 0:
                        sign = "+" if roll_modifiers['attack_modifier'] > 0 else ""
                        mod_lines.append(f"⚔️ Attack: {sign}{roll_modifiers['attack_modifier']} dice")

                    if roll_modifiers['save_modifier'] != 0:
                        sign = "+" if roll_modifiers['save_modifier'] > 0 else ""
                        mod_lines.append(f"🛡️ Saves: {sign}{roll_modifiers['save_modifier']} dice")

                    if roll_modifiers['incoming_modifier'] != 0:
                        sign = "+" if roll_modifiers['incoming_modifier'] > 0 else ""
                        mod_lines.append(f"🎯 Incoming: {sign}{roll_modifiers['incoming_modifier']} dice (attackers roll this many fewer/more)")

                    embed.add_field(name="🎲 Roll Modifiers", value="\n".join(mod_lines), inline=False)

                # Add effects section if any exist
                if effects:
                    effects_list = ", ".join([f"{effect.get('emoji', '🔮')} {effect['name']} ({effect['duration']} rounds)" for effect in effects])
                    embed.add_field(
                        name=f"🔮 Active Effects ({len(effects)})",
                        value=effects_list,
                        inline=False
                    )

                # Add deployables section showing owned deployables
                async with db.execute(
                    "SELECT deployable_name, hp, max_hp, stars, max_stars, hidden_resources FROM deployables WHERE owner_name = ?",
                    (char_name,)
                ) as cursor:
                    deployables = await cursor.fetchall()

                if deployables:
                    # Helper function for 3-block bars
                    def generate_3block_bar(current, maximum):
                        """Generate 3-block bar for deployables"""
                        if maximum <= 0:
                            return ":black_large_square:" * 3
                        blocks = round((current / maximum) * 3)
                        blocks = max(0, min(3, blocks))
                        filled = ":green_square:" * blocks
                        empty = ":black_large_square:" * (3 - blocks)
                        return filled + empty

                    deploy_lines = []
                    for dep_name, dep_hp, dep_max_hp, dep_stars, dep_max_stars, dep_hidden in deployables:
                        if dep_hidden:
                            # Show ??? for hidden deployables
                            deploy_lines.append(f"**{dep_name}** | ❤️ `???` | ⭐ `???`")
                        else:
                            # Show full stats
                            hp_bar = generate_3block_bar(dep_hp, dep_max_hp)
                            star_bar = generate_3block_bar(dep_stars, dep_max_stars)
                            deploy_lines.append(f"**{dep_name}** | ❤️ {hp_bar} `{dep_hp}/{dep_max_hp}` | ⭐ {star_bar} `{dep_stars}/{dep_max_stars}`")

                    embed.add_field(
                        name=f"🎭 Deployables ({len(deployables)})",
                        value="\n".join(deploy_lines),
                        inline=False
                    )

                print(f"[OK] Displayed character sheet for {name}")
                await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error showing character: {e}", exc_info=True)
            print(f"[ERROR] /char show failed: {str(e)}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @char_group.command(name="delete", description="Delete a character")
    @app_commands.describe(name="Character name")
    @app_commands.autocomplete(name=character_autocomplete)
    async def delete_character(self, interaction: discord.Interaction, name: str):
        """Delete a character"""
        print(f"[CMD] {interaction.user.name} used /char delete with params: name={name}")
        try:
            

            async with aiosqlite.connect('database/ronan.db') as db:
                # Check if exists
                async with db.execute(
                    "SELECT name FROM characters WHERE name = ?",
                    (name,)
                ) as cursor:
                    if not await cursor.fetchone():
                        print(f"[ERROR] Character '{name}' not found")
                        await interaction.response.send_message(
                            f"❌ Character '{name}' not found!",
                            ephemeral=True
                        )
                        return

            # Confirmation prompt with reactions
            embed = discord.Embed(
                title="⚠️ Confirm Deletion",
                description=f"Delete character **{name}**? This will also delete all forms and movesets.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)
            msg = await interaction.original_response()
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")

            def check(reaction, user):
                return user == interaction.user and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == msg.id

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
                if str(reaction.emoji) == "❌":
                    await interaction.followup.send("❌ Character deletion cancelled.")
                    return
            except:
                await interaction.followup.send("⏱️ Confirmation timed out. Character deletion cancelled.")
                return

            # Delete character and all related data
            async with aiosqlite.connect('database/ronan.db') as db:
                # Delete from movesets table
                await db.execute("DELETE FROM movesets WHERE character_name = ?", (name,))

                # Delete from effects table
                await db.execute("DELETE FROM effects WHERE character_name = ?", (name,))

                # Delete from forms table (CASCADE may not cover this)
                await db.execute("DELETE FROM forms WHERE character_name = ?", (name,))

                # Finally delete from characters table
                await db.execute("DELETE FROM characters WHERE name = ?", (name,))
                await db.commit()

            print(f"[OK] Deleted character: {name}")
            await interaction.followup.send(
                f"✅ Character **{name}** has been deleted."
            )

        except Exception as e:
            logger.error(f"Error deleting character: {e}", exc_info=True)
            print(f"[ERROR] /char delete failed: {str(e)}")
            await interaction.followup.send(
                f"❌ Error deleting character: {str(e)}",
                ephemeral=True
            )

    @char_group.command(name="log", description="Add a console log annotation for debugging")
    @app_commands.describe(message="Message to log to console")
    async def log_annotation(self, interaction: discord.Interaction, message: str):
        """Log a message to the console for debugging"""
        print(f"[LOG] {interaction.user.name}: {message}")
        await interaction.response.send_message(
            f"✅ Logged to console",
            ephemeral=True
        )

    @char_group.command(name="senzu", description="Fully restore all character resources (HP/MP/Stars/move uses)")
    @app_commands.describe(name="Character name")
    @app_commands.autocomplete(name=character_autocomplete)
    async def senzu_character(self, interaction: discord.Interaction, name: str):
        """Fully restore all resources for a character"""
        print(f"[CMD] {interaction.user.name} used /char senzu with params: name={name}")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Get character's max values
                async with db.execute(
                    "SELECT max_hp, max_mp, max_stars FROM characters WHERE name = ?",
                    (name,)
                ) as cursor:
                    row = await cursor.fetchone()

                if not row:
                    print(f"[ERROR] Character '{name}' not found")
                    await interaction.response.send_message(
                        f"❌ Character '{name}' not found!",
                        ephemeral=True
                    )
                    return

                max_hp, max_mp, max_stars = row

                # Restore all resources to max
                await db.execute("""
                    UPDATE characters
                    SET hp = ?, mp = ?, current_stars = ?, temp_hp = 0, temp_mp = 0, temp_stars = 0
                    WHERE name = ?
                """, (max_hp, max_mp, max_stars, name))

                # Restore move uses to max_uses
                await db.execute("""
                    UPDATE movesets
                    SET uses = max_uses
                    WHERE character_name = ? AND max_uses IS NOT NULL
                """, (name,))

                # Sync with combat_state if combat is active (critical for star sync!)
                async with db.execute("SELECT combat_active FROM initiative WHERE id = 1") as cursor:
                    init_row = await cursor.fetchone()
                    if init_row and init_row[0] == 1:
                        # Check if character is in the active combat
                        async with db.execute("SELECT 1 FROM combat_state WHERE character_name = ?", (name,)) as check:
                            if await check.fetchone():
                                await db.execute("""
                                    UPDATE combat_state
                                    SET current_hp = ?, current_mp = ?, stars = ?
                                    WHERE character_name = ?
                                """, (max_hp, max_mp, max_stars, name))
                                print(f"[SYNC] Updated combat_state for {name}: HP={max_hp}, MP={max_mp}, Stars={max_stars}")

                await db.commit()

                # Verify actual values after update
                async with db.execute(
                    "SELECT hp, mp, current_stars FROM characters WHERE name = ?",
                    (name,)
                ) as cursor:
                    verify_row = await cursor.fetchone()
                    actual_hp, actual_mp, actual_stars = verify_row if verify_row else (max_hp, max_mp, max_stars)

                print(f"[OK] Fully restored {name}: HP={actual_hp}/{max_hp}, MP={actual_mp}/{max_mp}, Stars={actual_stars}/{max_stars}")

                # Create embed with senzu bean gif
                embed = discord.Embed(
                    title="✨ Senzu Bean",
                    description=f"**{name}** is fully restored!",
                    color=discord.Color.green()
                )
                embed.add_field(name="❤️ HP", value=f"{actual_hp}/{max_hp}", inline=True)
                embed.add_field(name="💙 MP", value=f"{actual_mp}/{max_mp}", inline=True)
                embed.add_field(name="⭐ Stars", value=f"{actual_stars}/{max_stars}", inline=True)
                embed.set_image(url="attachment://SENZUBEAN.gif")

                # Send with gif attachment
                gif_file = discord.File("data/assets/SENZUBEAN.gif", filename="SENZUBEAN.gif")
                await interaction.response.send_message(embed=embed, file=gif_file)

        except Exception as e:
            logger.error(f"Error using senzu: {e}", exc_info=True)
            print(f"[ERROR] /char senzu failed: {str(e)}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

    @char_group.command(name="hide", description="Toggle hidden resources for a character or deployable")
    @app_commands.describe(name="Character or deployable name")
    @app_commands.autocomplete(name=character_and_deployable_autocomplete)
    async def hide_character(self, interaction: discord.Interaction, name: str):
        """Toggle hidden_resources boolean for a character or deployable"""
        print(f"[CMD] {interaction.user.name} used /char hide with params: name={name}")
        try:
            async with aiosqlite.connect('database/ronan.db') as db:
                # Check if character exists
                async with db.execute(
                    "SELECT hidden_resources FROM characters WHERE name = ?",
                    (name,)
                ) as cursor:
                    row = await cursor.fetchone()

                is_deployable = False
                if not row:
                    # Check if it's a deployable
                    async with db.execute(
                        "SELECT hidden_resources FROM deployables WHERE deployable_name = ?",
                        (name,)
                    ) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            is_deployable = True

                if not row:
                    print(f"[ERROR] '{name}' not found (neither character nor deployable)")
                    await interaction.response.send_message(
                        f"❌ '{name}' not found!",
                        ephemeral=True
                    )
                    return

                # Toggle the boolean (SQLite uses 0/1 for boolean)
                current_state = bool(row[0])
                new_state = not current_state

                if is_deployable:
                    await db.execute(
                        "UPDATE deployables SET hidden_resources = ? WHERE deployable_name = ?",
                        (1 if new_state else 0, name)
                    )
                else:
                    await db.execute(
                        "UPDATE characters SET hidden_resources = ? WHERE name = ?",
                        (1 if new_state else 0, name)
                    )
                await db.commit()

                state_text = "hidden" if new_state else "visible"
                entity_type = "deployable" if is_deployable else "character"
                print(f"[OK] {name} ({entity_type})'s resources are now {state_text}")
                await interaction.response.send_message(
                    f"✅ **{name}**'s resources are now **{state_text}**.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error toggling hidden resources: {e}", exc_info=True)
            print(f"[ERROR] /char hide failed: {str(e)}")
            await interaction.response.send_message(
                f"❌ Error toggling hidden resources: {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(CharacterCommands(bot))
