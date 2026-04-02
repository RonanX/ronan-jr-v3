# Starfall Lite - Mechanics & Architecture Guide

## Section 1: Starfall Lite Mechanics Reference
Starfall Lite is a streamlined, narrative-focused action TTRPG system. It prioritizes fast resolution and eliminates complex math or grid-based movement.

### Core Mechanics
* **Dice Pools (Attacks):** Uses d6s. The number of dice rolled equals the relevant Stat Rating (0-4) plus any modifiers (advantage/disadvantage). 
* **Resolution:** You only ever look at the **single highest die** in the pool. More dice just means better odds of rolling a 5 or 6. You always roll at least 1 die, even with heavy penalties.
* **Advantage/Disadvantage:** These stack linearly. +1 advantage adds 1d6 to the pool. -1 disadvantage removes 1d6. They cancel each other out.
* **Saves:** Uses 1d20 + stat rating + proficiency bonus. Advantage/disadvantage on saves adds extra d20s to the roll, keeping the highest or lowest respectively.

### Combat Resolution
* **Action Economy:** Characters get **5 Stars** at the start of their turn. Light attacks cost 1, medium cost 2, heavy cost 4-5. Movement/dashing costs 1.
* **Combos:** If an attack hits, you can continue attacking as long as you have stars. If an attack misses, your combo breaks and your turn ends for attacks (utility moves can still be used).
* **AC Thresholds:** Target defenses are categorized into Tiers, not flat numbers:
    * **Tier 1 (Easy):** 4-6 clean hit, 3 hit with cost, 1-2 miss.
    * **Tier 2 (Medium):** 5-6 clean hit, 4 hit with cost, 1-3 miss.
    * **Tier 3 (Hard):** 6 clean hit, 5 hit with cost, 1-4 miss.
* **Damage:** There are no damage dice. Damage is a flat base number + the character's relevant stat modifier (except light attacks, which have no stat modifier).

### Characters & States
* **Stats:** STR, DEX, CON, INT, WIS, CHA. Rated 0 to 4.
* **Status Effects:** Kept simple. Effects do not stack in complexity (e.g., no "burning poison"). Buffs and debuffs apply flat additions or subtractions to the dice pool size (attack_modifier, incoming_modifier, save_modifier).
* **Deployables:** Summons or items that have their own HP and star pool, but act on the owner's turn to prevent clogging the initiative order.

---

## Section 2: Code Architecture Reference
The bot is built in Python using `discord.py` and `aiosqlite` for asynchronous database operations.

### Structural Flow
1.  **Entry Point (`bot.py`):** Initializes the bot, establishes intents, clears stale combat states from the DB, and loads feature cogs.
2.  **Cogs (`cogs/`):** Command interfaces. They parse user input from Discord, call the relevant utility functions to perform the logic, and format the results into Discord embeds.
3.  **Core Logic (`utils/`):** * `dice.py`: Pure functions for calculating dice pools, d20 saves, and checking threshold results. 
    * `effects.py`: DB wrapper functions that handle the complex logic of applying buff/debuff modifiers to a character's JSON stat blocks and tracking expiration rounds.
4.  **Data Layer (`database/`):** Contains `init_db.py` to establish the schema. The DB relies heavily on JSON serialization for dynamic fields (like stat arrays or movesets) to avoid overly wide SQL tables.

### Key Implementation Details
* **Effect Contributions:** When an effect is applied, its specific modifiers (e.g., -1 to attack rolls) are merged into the character's `roll_modifiers` JSON object in the database. When the effect expires, that exact contribution is mathematically subtracted. *This is fragile and must be kept in sync.*
* **State Separation:** Base stats are kept separate from current combat state. `characters` holds the theoretical max values, while `combat_state` and the effects tables handle volatile data that gets wiped or modified during a fight.
* **Connection Handling:** Database connections are frequently opened and closed locally within utility functions. Functions that might be called in a loop (like expiring multiple effects) accept an optional `db` parameter to reuse an existing connection and avoid deadlocks.