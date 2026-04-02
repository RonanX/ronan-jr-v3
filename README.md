Ronan Jr v3 - Starfall Lite RPG Bot

A custom Discord bot built to automate Starfall Lite, a streamlined, narrative-focused action TTRPG system.

Unlike heavy, math-dense RPG bots, Ronan Jr is designed to stay out of the way. It tracks the core vitals, handles the dice pool math, and manages status effects, letting players focus on the narrative action instead of juggling spreadsheets.

What is Starfall Lite?

Starfall Lite is a homebrew system built for fast, anime-style combat. It uses a d6 dice pool system where you only ever look at the highest die.

Attacks: Roll d6s equal to your Stat Rating (0-4).

Advantage/Disadvantage: Add or remove d6s from your pool.

Saves: Standard 1d20 + Stat + Proficiency. Advantage/Disadvantage adds extra d20s.

Defense Tiers: Targets have Defense Tiers (Tier 1, Tier 2, or Tier 3) instead of flat numerical AC.

Bot Features

The bot automates the tedious parts of combat while leaving the creative stuff to the players:

Character Management: Track HP, MP, Base Stats, and Proficiency.

Dynamic Action Economy: Automatically tracks the 5-Star system per turn. Light attacks cost 1★, heavy attacks cost 4-5★.

Combat States: Separate tracking for volatile combat data (Temp HP, current stars, active modifiers) vs. base character sheets.

Dynamic Status Effects: A robust effect system that handles Buffs, Debuffs, DoTs (Damage over Time), and Resource Generation. Presets accept custom values (e.g., apply a custom poison that does exactly X damage, or a buff that restores Y MP).

Transformations/Forms: Swap to alternate stat blocks mid-fight.

Deployables: Summon turrets, clones, or pets with their own HP and Star pools that act independently in combat.

Core Mechanics (Automated)

🎲 The Dice Pool & Tiers

When you attack, the bot rolls your pool and compares the highest die against the target's Defense Tier:

Tier 1 (Easy): 4-6 is a clean hit. 3 is a hit with a cost. 1-2 is a miss.

Tier 2 (Medium): 5-6 is a clean hit. 4 is a hit with a cost. 1-3 is a miss.

Tier 3 (Hard): 6 is a clean hit. 5 is a hit with a cost. 1-4 is a miss.

🌟 The Star System (Action Economy)

Players get 5 Stars at the start of their turn. The bot deducts stars as moves are executed.

Combos: As long as you hit and have stars, you can keep attacking.

Breaks: If an attack misses, your combo breaks. The bot knows this and your turn ends for attacks (utilities can still be used).

The "Honor System" (What players track manually)

To keep the bot fast and flexible, it doesn't hard-lock you out of complex mechanics. Homebrew characters often have wild abilities, so the bot relies on players to manually track the following in the narrative chat:

Cooldowns: Characters have moves with 1-3 round cooldowns. The bot will not stop you from spamming a move; players must track their own cooldowns.

Reactions & Triggers: The system uses "on hit" or "reaction" moves heavily. Players manually execute these commands out-of-turn when the narrative calls for it.

Positioning: Starfall Lite is "Theater of the Mind." There is no grid or range tracking in the bot.

Getting Started

Requirements

Python 3.10+

discord.py

aiosqlite

Setup

Clone the repository.

Install dependencies: pip install -r requirements.txt

Create a .env file in the root directory and add your bot token: DISCORD_TOKEN=your_token_here

Run the database initialization to build the schema: python database/init_db.py

Start the bot: python bot.py