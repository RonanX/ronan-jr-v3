# Ronan Jr v3 - Starfall Lite Combat Bot

A Discord bot for the **Starfall Lite** tabletop RPG system - built for speed and simplicity.

## What is This?

Ronan Jr v3 is a combat tracker for **Starfall Lite**, a custom dice pool RPG designed for fast-paced action roleplay. This is a complete rewrite from v2, focusing on essential features and streamlined gameplay.

**Core Philosophy:** v2 had 200+ features. v3 has ~30. That's intentional.

## Current Features (Phase 1-6 Complete)

### ✅ Character Management
- **Character Creation**: `/char create` - Full stat allocation (6 stats, 0-4 each, total 12-16)
- **Character Viewing**: `/char show` - Vertical layout with health bars, stats, effects, and current form
- **Character Updates**: `/char update` - Modify HP, MP, stars, AC, stats
- **Character Deletion**: `/char delete` - Remove characters with confirmation
- **Max Stars System**: Characters have configurable max_stars (default 3)

### ✅ Dice Pool System
- **Unified Dice Pools**: Roll Xd6 where X = stat rating (0-4) + modifiers
- **Advantage/Disadvantage**: Roll double dice, keep better/worse half
- **Critical Hits**: Multiple 6s in kept dice = crit (doubles damage)
- **AC Tier System**:
  - AC 10-12: 4+ clean, 3 cost, 1-2 miss
  - AC 13-15: 5+ clean, 4 cost, 1-3 miss
  - AC 16-18: 6 clean, 5 cost, 1-4 miss
- **Minimum 1d6**: Stats/modifiers below 1 still roll 1d6

### ✅ Combat System
- **Initiative Tracking**: `/init start/add/show/next/end`
- **Turn Advancement**: Auto-refreshes stars, ticks effects, removes expired deployables
- **Attack System**: `/attack [light/medium/heavy] [stat] [target]`
  - Light: 1 star, Medium: 2 stars, Heavy: 4 stars
  - Dice pool vs AC, damage projection, cost validation
- **Save System**: `/save [character] [type] [dc]` - 1d20 + stat vs DC
- **Resource Management**: Stars refresh on turn, MP/HP tracked
- **Combat State**: Save/load combat with `/save` and `/load`

### ✅ Effect System (Contribution-Based)
- **Effect Application**: `/effect add [character] [name] [duration]`
- **Effect Tracking**: Effects track their contributions (stat_modifiers, roll_modifiers, ac_modifier)
- **Clean Removal**: Removing effect subtracts its contributions exactly
- **Effect Stacking**: Multiple effects stack numerically
- **Preset Effects**: burning (🔥 5 fire DoT), stunned (💫 -999 attack), advantage (⬆️ +999 attack), disadvantage (⬇️ -999 attack), poisoned (🤢 3 poison DoT)
- **DoT Display**: Effects show DoT damage but don't auto-apply (manual `/damage`)
- **Duration Expiry**: Effects expire at START of specified round
- **Effect Refresh**: Reapplying same effect refreshes duration

### ✅ Moveset System
- **Move Creation**: `/move create` - Create moves with category, costs, damage, hits, saves
- **Move Editing**: `/move edit` - Update any move property
- **Move Listing**: `/move list` - Category-organized display (light/medium/heavy/utility)
- **Move Deletion**: `/move delete` - Remove with confirmation
- **Move Help**: `/move help` - Comprehensive documentation
- **Auto Star Costs**: light=1⭐, medium=2⭐, heavy=4⭐, utility=0⭐
- **Cost Parsing**: Flexible "mp:10, hp:5, stars:2" format
- **Per-Form Movesets**: Each character form has independent moveset

### ✅ Move Execution
- **Move Usage**: `/move use [move] [target]` - Execute saved moves
- **Attack Moves**: Dice pool rolling, AC checks, multihit calculation, damage projection
- **Save Moves**: Auto-calculate DC (8 + prof + highest mental stat), target rolls save, half_on_save support
- **Utility Moves**: Resource spending, effect application, buff display
- **Multihit Logic**: clean=all hits, cost=half rounded up, miss=0 hits
- **Cost Validation**: Pre-checks stars/MP/HP before execution
- **Compact Embeds**: 3-4 line output format

### ✅ Moveset Importing
- **Text Import**: `/moveset import` - Paste text format, auto-detects format
  - Format: "Move Name - category, stat:X, damage:Y, hits:Z, properties"
  - Fuzzy keyword matching (dmg/damage, hit/hits, etc.)
- **JSON Import**: Supports JSON array format
- **Preview System**: Shows parsed moves before confirmation
- **Validation**: Checks duplicates, unreasonable values
- **Batch Import**: Creates all moves at once
- **Export**: `/moveset export` - Export to JSON (file if >1800 chars)
- **Bulk Delete**: `/moveset clear` - Clear all moves with confirmation

### ✅ Deployables System
- **Deployable Creation**: `/deploy create [name] [hp] [stars] [duration]`
- **Deployable Actions**: `/deploy attack` - Uses owner's stats for moves
- **Deployable Damage**: `/deploy damage` - Auto-removes at HP=0
- **Deployable Listing**: `/deploy list` - Filter by owner
- **Deployable Removal**: `/deploy remove` - Manual dismissal
- **Turn Integration**: Refresh deployable stars on owner's turn, auto-expire by round
- **Targeting**: `/attack` can target deployables (uses owner's AC)

### ✅ Transformation System
- **Form Creation**: `/form add` - Create forms with stats, AC, transformation costs, duration
- **Form Listing**: `/form list` - Show all forms with properties
- **Transformation**: `/form transform` - Stat swapping via stat_modifiers (new - base)
- **Revert**: `/form revert` - Return to base form (if cancellable)
- **Form Deletion**: `/form delete` - Remove form and its movesets
- **Cost Support**: "mp:10, hp:5, stars:2" format for transformation costs
- **Duration Tracking**: Auto-revert after duration expires
- **DoT Recoil**: Optional dot_damage and dot_type for transformation maintenance costs
- **Effect Preservation**: Effects persist through transformations
- **Display Integration**: `/char show` displays current form in title with gold color

### ✅ Modifier Stacking
- **Stat Modifiers**: stat_modifiers track effect contributions, stack numerically
- **Roll Modifiers**: attack_modifier (outgoing attacks), incoming_modifier (attacks against you), save_modifier (your saves)
- **AC Modifiers**: ac_modifier stacks on base AC
- **Effect Contributions**: Each effect tracks what it adds, cleanly removed
- **Effective Stats**: base_stats + stat_modifiers = effective stats for rolls

### ✅ Help System
- **Contextual Help**: `/help [topic]` - 10 help topics with detailed info
- **Topics**: start, characters, combat, dice, attacks, moves, deployables, forms, saveload, commands
- **Inline Documentation**: `/move help` provides move-specific help

### ✅ Testing Coverage (75/95 tests passing)
- **Dice System**: 24 tests - pools, advantage/disadvantage, crits, tier checks
- **Combat Math**: 24 tests - damage, multihit, save DC, cost validation, modifier stacking
- **Preset Effects**: 8 tests - all 5 preset effects verified
- **Edge Cases**: 5 tests - boundary values (stat 0-4)
- **Integration Tests**: 14 tests (async fixture warnings, logic is sound)

## System Mechanics

### Dice Pool Combat
- **Not d20 vs AC** - Roll dice pool, use highest single die
- **Stat Ratings**: 0-4 (0 still rolls 1d6 minimum)
- **Pool Size**: stat + modifiers (minimum 1d6)
- **Results**: Compare highest die to AC tier thresholds

### 5-Star Action Economy
- **Stars per Turn**: Configurable max_stars (default 3)
- **Star Costs**: light=1, medium=2, heavy=4
- **Auto-Refresh**: Stars reset to max at start of your turn
- **Combo System**: Clean hits keep attacking, misses break combo

### Flat Damage System
- **No Damage Dice**: Moves have base damage + stat modifier
- **Example**: 10 base damage + 3 combat stat = 13 damage
- **Crits Double**: (base + stat) × 2
- **Multihit**: damage_per_hit × hits_landed

### Multihit Mechanics
- **One Roll**: Single dice pool determines all hits
- **Clean Hit**: All hits land
- **Hit with Cost**: Half hits (rounded up)
- **Miss**: 0 hits land

### Resource Types
- **Stars (⭐)**: Action economy, refreshes per turn
- **MP (💙)**: Mana for moves/transformations
- **HP (❤️)**: Health, character dies at 0

## What Got Cut from v2

- ❌ Firebase (using local SQLite)
- ❌ Dual effect systems (unified contribution system)
- ❌ Parent-child linking (deployables act on owner's turn instead)
- ❌ Currency/shops
- ❌ Complex move phases (instant execution only)
- ❌ Compound effects (use multiple simple effects)
- ❌ Heat tracking
- ❌ Complex stacking mechanics

## Project Structure

```
ronan-jr-v3/
├── bot.py                    # Main bot entry point
├── .env                      # Discord token (create this)
├── database/
│   ├── init_db.py           # Database setup
│   ├── migrate_*.py         # Migration scripts
│   └── ronan.db             # SQLite database
├── cogs/
│   ├── character.py         # Character management
│   ├── combat.py            # Combat & initiative
│   ├── moves.py             # Moveset & move execution
│   ├── deployables.py       # Deployable system
│   ├── forms.py             # Transformation system
│   └── help.py              # Help commands
├── utils/
│   ├── dice.py              # Dice pool mechanics
│   ├── effects.py           # Effect contribution system
│   ├── move_execution.py    # Move execution utilities
│   ├── moveset_parser.py    # Text/JSON moveset parsing
│   └── constants.py         # System constants
├── data/
│   └── saves/               # Combat save files
└── tests/                   # Test suite (pytest)
    ├── test_dice.py
    ├── test_combat_math.py
    ├── test_effects.py
    ├── test_combat_flow.py
    └── test_edge_cases.py
```

## Quick Start

### 1. Setup
```bash
# Install dependencies
pip install discord.py python-dotenv aiosqlite pytest pytest-asyncio

# Create .env file with your bot token
echo "DISCORD_TOKEN=your_token_here" > .env

# Initialize database
python database/init_db.py

# Run migrations
python database/migrate_movesets.py
python database/migrate_deployables.py
python database/migrate_forms_extended.py

# Start bot
python bot.py
```

### 2. First Time in Discord
```
!sync  # Sync slash commands (owner only)
```

### 3. Create Characters
```
/char create hin hp:55 mp:150 ac:14 max_stars:3
# Then set stats: strength:4, dexterity:4, constitution:2, intelligence:1, wisdom:1, charisma:0

/char create vi hp:45 mp:120 ac:13 max_stars:3
# Then set stats: strength:4, dexterity:3, constitution:2, intelligence:2, wisdom:1, charisma:0
```

### 4. Create Movesets
```
/move create
# Follow prompts, or use /moveset import for bulk creation

/moveset import
# Paste text format:
# Tempest Fang - medium, stat:combat, damage:10, hits:3
# Shadow Step - utility, mp_cost:15, description:Teleport
```

### 5. Run Combat
```
/init start
/init add hin
/init add vi

/init next  # Advance to first turn

# Use basic attack
/attack medium combat vi

# Or use saved move
/move use "Tempest Fang" vi

/init next  # Next turn
```

### 6. Use Advanced Features
```
# Add effects
/effect add hin burning 3

# Deploy summons
/deploy create "Shadow Clone" 20 2 5

# Transform
/form transform hin "Dragon Form"

# Save combat
/save battle1
```

## Commands Reference

### Character Management
- `/char create [name] [hp] [mp] [ac] [movement] [max_stars]` - Create character
- `/char show [character]` - Display character sheet
- `/char update [character]` - Modify stats/resources
- `/char delete [character]` - Remove character

### Combat & Initiative
- `/init start` - Begin combat
- `/init add [character]` - Add to initiative (rolls 1d20 + mobility)
- `/init show` - Display initiative order
- `/init next` - Advance turn (refreshes stars, ticks effects)
- `/init end` - End combat (confirmation required)

### Attacks & Saves
- `/attack [light/medium/heavy] [stat] [target]` - Roll attack
- `/save [character] [type] [dc]` - Saving throw
- `/damage [target] [amount] [type]` - Apply damage

### Moveset System
- `/move create` - Create new move
- `/move edit [name]` - Edit move properties
- `/move list [character] [form]` - Show moveset
- `/move delete [name]` - Remove move
- `/move use [move] [target]` - Execute move
- `/move help` - Move system documentation
- `/moveset import` - Bulk import (text/JSON)
- `/moveset export [character] [form]` - Export to JSON
- `/moveset clear [character] [form]` - Delete all moves

### Effect System
- `/effect add [character] [name] [duration]` - Apply effect
- `/effect list [character]` - Show active effects
- `/effect remove [character] [name]` - Remove effect

### Deployables
- `/deploy create [name] [hp] [stars] [duration]` - Summon deployable
- `/deploy attack [deployable] [stat] [target]` - Deployable attacks using owner's stats
- `/deploy damage [deployable] [amount]` - Damage deployable
- `/deploy list [owner]` - Show deployables
- `/deploy remove [deployable]` - Dismiss deployable

### Transformations
- `/form add [character] [form]` - Create form
- `/form list [character]` - Show forms
- `/form transform [character] [form]` - Transform (costs resources)
- `/form revert [character]` - Return to base
- `/form delete [character] [form]` - Remove form

### Resource Management
- `/stars spend [character] [amount]` - Spend stars
- `/stars show [character]` - Display stars

### Save/Load
- `/save [filename]` - Save combat state
- `/load [filename]` - Load combat state

### Help
- `/help [topic]` - Get help (topics: start, characters, combat, dice, attacks, moves, deployables, forms, saveload, commands)

## Testing

Run the test suite:
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_dice.py -v

# Current coverage: 75/95 tests passing (79%)
```

## Design Principles

### DO:
- ✅ Keep output condensed (one embed per action)
- ✅ Track simple data (HP, stars, effect durations)
- ✅ Auto-refresh resources on turn advance
- ✅ Validate before executing
- ✅ Use contribution-based effects
- ✅ Test core mechanics

### DON'T:
- ❌ Implement complex stacking mechanics
- ❌ Build multi-phase systems
- ❌ Add features not in Starfall Lite
- ❌ Recreate v2's complexity
- ❌ Add shops, currency, or heat tracking
- ❌ Skip testing before moving on

## Current Capabilities Summary

**Character System:**
- Full stat allocation (6 stats, configurable max_stars)
- Vertical display with health bars
- Form system with stat swapping
- Effect tracking with contributions

**Combat System:**
- Dice pool combat (tier-based AC system)
- Initiative with turn advancement
- Attack/save mechanics
- Star-based action economy
- Combat save/load

**Moveset System:**
- Individual move storage per character/form
- Move creation with full property support
- Move execution (attack/save/utility)
- Text/JSON bulk import with fuzzy parsing
- Export functionality

**Effect System:**
- Contribution-based (stat/roll/AC modifiers)
- Clean application/removal
- Preset effects (burning, stunned, advantage, disadvantage, poisoned)
- DoT tracking
- Duration-based expiry

**Deployable System:**
- Independent HP/stars
- Uses owner's stats
- Auto-expiry by round
- Can be targeted by attacks

**Transformation System:**
- Stat swapping via modifiers
- Per-form movesets
- Resource costs (MP/HP/stars)
- Duration tracking with auto-revert
- DoT recoil support

**Data Persistence:**
- SQLite database
- Combat state save/load
- Character/move/form storage

## Bot Capabilities for Character Sheet Design

**Use this as a reference when designing character sheets to ensure compatibility with the bot's systems.**

### Character Stats & Resources

**Stats (6 total):**
- **Names**: str, dex, con, int, wis, cha
- **Range**: 0-4 per stat (0 still rolls 1d6 minimum)
- **Point Budget**: 12-16 total across all 6 stats
- **Usage**: Determines dice pool size (stat + modifiers)

**Resources:**
- **HP**: Any positive integer (50-80 typical for balanced characters)
- **MP**: Any positive integer (80-150 typical for balanced characters)
- **Stars**: Default 3, configurable 1-5 (action economy per turn)
- **AC**: 10-18 typical range
  - 10-12: Easy to hit (rushdown/berserker)
  - 13-15: Medium defense (balanced)
  - 16-18: Hard to hit (evasive/tank)
- **Movement**: Any integer (not currently used in mechanics)
- **Proficiency**: +2 to +4 typical (affects save DC calculation)

### Move Design Guidelines

**Categories & Star Costs:**
- **Light**: 1⭐ - Quick attacks, small spells (5-10 damage typical)
- **Medium**: 2⭐ - Standard attacks, moderate spells (10-15 damage typical)
- **Heavy**: 4⭐ - Ultimate attacks, powerful spells (20-30 damage typical)
- **Utility**: 0⭐ - Buffs, movement, heals (no damage, pure effects)

**Move Properties:**
- `stat`: Which stat to use for attack rolls (str/dex/con/int/wis/cha)
- `damage`: Base damage (before stat modifier)
- `hits`: Number of hits (1-4 typical, multihit uses half on "hit with cost")
- `mp_cost`: MP cost (0-50 typical)
- `hp_cost`: HP cost (0-20 typical, for recoil/blood magic)
- `save_type`: For save moves (str/dex/con/int/wis/cha)
- `save_dc`: Manual DC or auto-calculated (8 + prof + highest mental stat)
- `save_effect`: Text description of effect on failed save
- `half_on_save`: Boolean - half damage on successful save?
- `bonus_on_hit`: Text description of additional effect on hit
- `description`: Flavor text for utility moves

**Move Import Formats:**
- **Text**: `"Move Name - category, stat:X, damage:Y, hits:Z, mp:W"`
- **JSON**: `{"name": "Move Name", "category": "medium", "stat": "dex", "damage": 10}`
- **Supports fuzzy keywords**: dmg/damage, hit/hits, mp_cost/mp/mana, etc.

**Damage Formula:**
- **Base damage**: Set in move
- **Stat bonus**: Uses character's effective stat (base + modifiers)
- **Final damage**: `(base_damage + stat_bonus) × hits_landed`
- **Crits**: Double total damage if multiple 6s rolled

**Move Scope Limitations:**
- ❌ **No complex targeting** (single target only, no AoE)
- ❌ **No conditional effects** (effects are always applied, no "on crit" logic)
- ❌ **No cooldowns** (not implemented yet)
- ❌ **No resource generation** (moves only spend resources)
- ❌ **No move chains** (each move is independent)
- ✅ **Simple effects OK** (stat/roll modifiers, DoT, duration-based expiry)

### Form/Transformation Design

**Form Properties:**
- `stats_json`: Full stat block for the form (6 stats, 0-4 each)
- `ac`: Custom AC for the form
- `transformation_cost`: "mp:X, hp:Y, stars:Z" format
- `duration`: Rounds until auto-revert (0 = permanent until manual revert)
- `cancellable`: Can the user manually revert? (true/false)
- `dot_damage`: Damage per turn while transformed (recoil)
- `dot_type`: Damage type (fire, poison, etc.)

**Form Limitations:**
- ❌ **No hybrid forms** (one form at a time)
- ❌ **No form-specific resources** (shares HP/MP/stars with base)
- ❌ **No conditional triggers** (manual transformation only)
- ✅ **Per-form movesets** (each form has independent moveset)
- ✅ **Stat swapping** (uses stat_modifiers for clean revert)

### Effect System Capabilities

**Effect Types:**
- **Stat Modifiers**: Modify base stats (str/dex/con/int/wis/cha) by ±1 to ±4
- **Roll Modifiers**:
  - `attack_modifier`: Affects outgoing attacks (advantage = +999, disadvantage = -999)
  - `incoming_modifier`: Affects attacks against you
  - `save_modifier`: Affects your saving throws
- **AC Modifier**: Flat bonus/penalty to AC
- **DoT**: Damage over time (doesn't auto-apply, shows in turn display)
- **Duration**: Expires at START of specified round

**Effect Scope Limitations:**
- ❌ **No complex stacking** (all modifiers stack numerically)
- ❌ **No conditional effects** (always active once applied)
- ❌ **No triggered effects** ("on hit", "on damage taken", etc.)
- ❌ **No effect interactions** (effects don't check for each other)
- ✅ **Contribution tracking** (effects cleanly remove their contributions)
- ✅ **Preset effects** (burning, stunned, advantage, disadvantage, poisoned)

### Deployable System Capabilities

**Deployable Properties:**
- `hp`: Independent HP pool (dies at 0)
- `max_hp`: Maximum HP
- `stars`: Independent star pool (refreshes on owner's turn)
- `max_stars`: Maximum stars
- `available_until_round`: Auto-expires after X rounds
- **Uses owner's stats** for attacks (owner's str/dex/con/int/wis/cha)
- **Uses owner's AC** when targeted
- **Can use deployable moves** (separate moveset from owner)

**Deployable Limitations:**
- ❌ **No independent stats** (uses owner's stats)
- ❌ **No independent AC** (uses owner's AC)
- ❌ **No MP pool** (only HP and stars)
- ❌ **No shared resources** (can't spend owner's HP/MP)
- ✅ **Auto-expiry** by round
- ✅ **Can be targeted** by attacks

### Resource Management Features

**Temp Resources:**
- `temp_hp`: Temporary HP (depletes before regular HP, no upper limit)
- `temp_mp`: Temporary MP (depletes before regular MP, no upper limit)
- `temp_stars`: Temporary stars (depletes before regular stars, no upper limit)
- `temp_duration`: Rounds until temp resources expire
- **Replaces existing** (not additive - new temp HP replaces old temp HP)

**Character Status Command:**
- **Read-only**: `/char status [character]` - Shows current resources (ephemeral)
- **Relative updates**: `/char status [character] hp:+10 mp:-15` - Add/subtract
- **Absolute updates**: `/char status [character] hp:50` - Set to value
- **Senzu bean**: `/char status [character] hp:senzu` - Restore to max
- **Temp resources**: `/char status [character] temp_hp:20 temp_duration:3`

### What to Avoid When Planning Characters

**Feature Requests that Won't Work:**
- ❌ Multi-target/AoE attacks (single target only)
- ❌ Cooldown-based abilities (not implemented)
- ❌ Combo systems requiring move order (each move independent)
- ❌ Conditional damage ("deals extra damage if target is burning")
- ❌ Resource generation ("restore 5 MP on hit")
- ❌ Complex triggered effects ("when you take damage, gain advantage")
- ❌ Parent-child deployable chains (one level only)
- ❌ Currency/shops/inventory (v2 features, cut from v3)

**Safe Character Concepts:**
- ✅ Stat-focused builds (high str rushdown, high int caster, etc.)
- ✅ MP-intensive casters (many medium/heavy moves with MP costs)
- ✅ HP-sacrifice builds (moves with hp_cost for extra power)
- ✅ Transformation-based characters (multiple forms with different movesets)
- ✅ Deployable summoners (can create multiple deployables)
- ✅ DoT-focused builds (burning, poison effects on moves)
- ✅ Multihit combos (moves with 2-4 hits)
- ✅ Save-or-suck builds (high DC save moves with effects)

### Import/Export Workflow

**Recommended Workflow:**
1. Design character stats/resources in spreadsheet
2. Plan moveset with categories and costs
3. Use `/char create` to create character
4. Use `/moveset import` with text format for bulk move creation
5. Use `/form add` for transformation forms
6. Test in combat, adjust as needed
7. Use `/moveset export` to save JSON backup

**Example Text Import Format:**
```
Tempest Fang - medium, stat:dex, damage:10, hits:3, mp:15
Shadow Step - utility, mp:20, description:Teleport behind target
Dragon's Breath - heavy, stat:int, damage:25, save_type:dex, save_dc:15, half_on_save:true
Quick Strike - light, stat:str, damage:5
```

**Bulk Import Tips:**
- Use consistent naming (hyphens, underscores, or spaces work)
- Include category for auto star costs (light/medium/heavy/utility)
- Add `mp:X` or `hp:X` for additional costs
- Use `hits:X` for multihit moves (2-4 typical)
- Use `save_type` and `save_dc` for save moves
- Keep descriptions short (shows in utility move embeds)

---

**Questions? Use `/help` in Discord or check STARFALL_LITE.md for system mechanics.**
