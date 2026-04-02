# CLAUDE.md - Ronan Jr v3 Context

## Overall Bot Summary
Ronan Jr v3 is a custom Discord RPG bot built for a homebrew tabletop system called "Starfall Lite". It handles character management, movesets, forms/transformations, combat state (HP/MP/Stars), deployables (pets/clones), and status effects. The bot automates the specific mechanics of Starfall Lite, primarily its unique d6 "keep highest" dice pool system and 5-star action economy, using an async SQLite database to track persistent state.

## Core File Map
* `bot.py`: The main entry point. Initializes the Discord bot, loads all functional cogs, and resets the combat initiative flag on startup.
* `database/init_db.py`: Defines the entire SQLite schema. Run this to initialize or reset the database structure.
* `utils/dice.py`: The mathematical heart of the bot. Handles all RNG, including the d6 dice pool logic, advantage/disadvantage modifier stacking, AC tier thresholds, and d20 saving throws.
* `utils/effects.py`: Manages the application, tracking, and removal of status effects (buffs/debuffs/DoTs). It handles injecting modifier changes directly into the character database profiles.
* `cogs/*.py`: Feature-specific Discord command modules (character, combat, moves, deployables, forms, help, misc).

## Database Schema (SQLite)
The database uses `aiosqlite` and is stored at `database/ronan.db`. 
* `characters`: Stores base stats (HP, MP, AC, stats_json), current state (temp_hp, current_stars), and dynamic modifiers (stat_modifiers, roll_modifiers) serialized as JSON.
* `forms`: Stores alternate stat blocks for character transformations. Linked to characters via foreign key.
* `movesets`: Stores custom attacks and abilities as JSON arrays. Linked to characters/forms.
* `initiative`: A singleton table (enforced via `id = 1`) that tracks global combat state, round numbers, and the turn order array.
* `combat_state`: Tracks volatile per-character combat data (current hp/mp, stars, active effects).
* `deployables`: Tracks standalone combat entities (clones, turrets) tied to an owner, including their own HP, stars, and expiration rounds.

## Established Code Patterns
* **Database Interactions:** Uses `aiosqlite` with async context managers (`async with db.execute(...)`). Always commits after updates. Optional `db` connection passing is used in `utils` to avoid nested connections/locks.
* **Stat Serialization:** Dynamic modifiers (stats, rolls) are stored as JSON strings in the database and must be parsed with `json.loads()` before modification, then re-serialized with `json.dumps()`.
* **Discord Setup:** Uses standard `discord.ext.commands.Bot` subclassing and `cogs` for organization.
* **Helper Utilities:** Core combat math and state manipulation are decoupled from Discord commands and live in the `utils/` folder to allow for easy unit testing.

## ⚠️ Don't Touch Without Asking ⚠️
* **The Initiative Singleton:** The `initiative` table relies on a strict `id = 1` constraint. Do not attempt to insert multiple rows or change how the combat active flag is toggled, as it will break the turn order logic.
* **Effect Contribution Logic:** In `utils/effects.py`, the `apply_effect` and `remove_effect` functions directly mutate the `stat_modifiers`, `roll_modifiers`, and `ac_modifier` JSON strings in the `characters` table. Modifying how these apply without perfectly mirroring the removal logic will cause permanent stat bloat or negative stats on characters.
* **Dice Pool Math:** The logic in `utils/dice.py` ensures a minimum of 1 die is always rolled regardless of negative modifiers. Do not alter the base pooling logic unless explicitly requested.

## Known Quirks
* **Legacy Effect Fields:** In `utils/effects.py`, there are several legacy database fields (`dot_damage`, `dot_type`, `resource_change`) still being mapped alongside their modern equivalents (`dot_value`, `resource_type`, `resource_value`). Be careful to use the modern fields when adding new effects.
* **Save Tiers vs Standard DC:** `roll_save` in `utils/dice.py` has branching logic to handle both a 3-tier difficulty system and a standard numeric DC system via the `use_tier` flag. 
* **String to Int Typing:** Some resource values in effects are parsed as strings (e.g., `dot_value: "3"`) while others are integers. Rely on `utils.value_parser` to handle these safely.