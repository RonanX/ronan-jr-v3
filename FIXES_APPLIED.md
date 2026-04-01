# Fixes Applied - Session Summary

## ✅ COMPLETED FIXES

### 1. Form Transform Stat Display Fix
**Issue**: Stats weren't showing modifiers in `/char show` after transformation
**Fix**:
- Updated `/char show` to calculate effective stats as `base_stats + stat_modifiers`
- Shows modifiers in parentheses: `STR: 5 (+2)` or `DEX: 3 (-1)`
- Save DC now uses effective stats instead of base stats
**Location**: `cogs/character.py` lines 1273-1288, 1233-1237

### 2. Attack Command Base Damage Fix
**Issue**: Auto-damage was adding stat TWICE (in calc + when rolling)
**Fix**:
- Auto-damage now just uses base damage (4/8/14 for light/medium/heavy)
- Stat is added once during roll calculation (line 1347)
- Formula: `total_damage = base_damage + effective_stat` (when rolling)
**Location**: `cogs/combat.py` lines 1220-1224

### 3. Attack Command Star Costs
**Issue**: Attacks didn't cost stars outside of combat
**Fix**:
- Stars now validated and spent ALWAYS (in combat and out)
- Gets stars from `combat_state` if in combat, `characters.current_stars` otherwise
- Validates before attack, deducts after successful attack
**Location**: `cogs/combat.py` lines 1174-1210, 1372-1385

### 4. Deployables Table Schema Migration
**Issue**: Table had old schema (`name`, `owner`, `duration`) vs code expecting new schema
**Fix**:
- Created migration script `database/migrate_deployables_table.py`
- Drops old table, creates new schema with proper columns
- New schema: `id`, `deployable_name`, `owner_name`, `hp`, `max_hp`, `stars`, `max_stars`, `available_until_round`, `created_round`, `ac`, `archetype`, `mp`, `max_mp`
- Migration ran successfully
**Location**: `database/migrate_deployables_table.py`

### 5. Deploy Create Redesign
**Issue**: Parameters were confusing (resource_cost/resource_type/mp_scaling)
**Fix**:
- Removed: `resource_cost`, `resource_type`, `mp_scaling`
- Added: `ac` (required), `archetype` (required, dropdown), `mp` (optional, default 0)
- Changed to separate cost parameters: `hp_cost`, `mp_cost`, `star_cost` (all optional)
- Validates each cost independently
- Only deducts if owner has enough resources
- Embed shows archetype in description, all costs in one field
**Location**: `cogs/deployables.py` lines 96-266

---

## 🔴 REMAINING CRITICAL TASKS

### 1. Add `hidden_resources` Column and `/char hide` Command
**Requirement**:
- Add `hidden_resources` BOOLEAN column to characters table (default FALSE)
- Add `/char hide [name]` toggle command
- Command flips the boolean and confirms state via ephemeral message
- When `hidden_resources` is TRUE, replace HP/MP/Stars/AC with `???` in:
  - `/char show`
  - `/char status`
  - `/init next` (turn start embed)
  - `/attack` results (target's HP display)
  - `/move use` results
  - `/char hp` response embed
  - Any other embed showing HP/MP/Stars/AC
- Still process numbers normally in database
- Print debug log: `[HIDDEN] charactername | HP: 32/55 | MP: 80/150`

**Implementation Steps**:
1. Create migration script to add `hidden_resources` column
2. Add `/char hide` command to `cogs/character.py`
3. Update all embeds to check `hidden_resources` before displaying stats
4. Add debug logging for hidden character updates

### 2. Add Threshold/Hidden_Resources/Squishy to `/char create` and `/char update`
**Requirement**:
- Add `threshold_damage`, `threshold_dc`, `hidden_resources`, `squishy` parameters to both commands
- All should be optional with sensible defaults
- `threshold_damage` and `threshold_dc` should be paired (both or neither)
- Update parameter descriptions

### 3. QOL Improvements to `/char show`
**Requirements**:

**A. Add Archetype and Tier to Description**
- Add line below title: `Archetype · Tier` (e.g., "Bruiser · Veteran")
- Don't change existing field layout

**B. Hide 0/0 MP Line**
- If `max_mp` is 0, skip the MP line entirely in resources section

**C. Fix Temp HP/MP/Stars Bar Display**
- Bar length always = max_hp squares
- Fill left to right: green (current HP), then black (empty)
- If temp HP exists: replace rightmost empty BLACK squares with WHITE squares, working inward
- If temp HP exceeds empty slots, add white squares beyond max_hp
- Apply same logic to MP bars (white) and star bars (white square emoji)

**D. Add Deployables Section**
- After stats section, query deployables owned by character
- If none exist, skip section
- If any exist, add field titled "Deployables"
- Format per deployable (2 lines):
  ```
  ━━ [name] • [archetype] ━━
  ❤️ [hp]/[max_hp] [3-square hp bar]  ⭐ [stars]/[max_stars]
  ```
- If deployable has `max_mp > 0`, add MP to second line:
  ```
  ❤️ [hp]/[max_hp] [3-square hp bar]  💙 [mp]/[max_mp] [3-square mp bar]  ⭐ [stars]/[max_stars]
  ```
- Use 3 squares for deployable bars (green/black/gold)
- Include temp HP/MP support in deployable bars
- If >3 deployables, show first 3 + note: "(+X more)"

---

## 📋 TESTING CHECKLIST

### Form Transformation
- [ ] Transform with enough stars - should work, show modifiers in `/char show`
- [ ] Transform without enough stars - should fail with error
- [ ] Check stat display shows modifiers: `STR: 5 (+2)`
- [ ] Verify Save DC uses effective stats

### Attack Command
- [ ] Light attack without damage param - should use base 4 + stat
- [ ] Medium attack without damage param - should use base 8 + stat
- [ ] Heavy attack without damage param - should use base 14 + stat
- [ ] Attack outside combat - should validate and spend stars
- [ ] Attack with insufficient stars - should fail
- [ ] Verify stars deducted correctly in logs

### Deployables
- [ ] `/deploy create` with new parameters (ac, archetype required)
- [ ] Create with hp_cost - should validate and deduct
- [ ] Create with mp_cost - should validate and deduct
- [ ] Create with star_cost - should validate and deduct
- [ ] Create with all costs - should deduct all
- [ ] Create with insufficient resources - should fail
- [ ] Verify embed shows archetype and costs correctly

---

## 🔧 TECHNICAL NOTES

### Star Cost Tracking
Stars are now tracked in two places:
- `characters.current_stars` - persistent, used outside combat
- `combat_state.stars` - temporary, used during combat

Attack command checks combat status and uses appropriate source.

### Stat Modifiers System
Stats are stored as:
- `base_stats` - permanent base values
- `stat_modifiers` - temporary modifiers from forms/effects
- Effective stat = `base_stat + stat_modifier`

All combat calculations should use effective stats.

### Deployables Schema
New columns added:
- `ac` (INTEGER) - deployable's armor class
- `archetype` (TEXT) - Striker/Tank/Support/Balanced
- `mp`, `max_mp` (INTEGER) - mana if deployable has spells

---

## 📝 FILES MODIFIED

1. `cogs/character.py` - Stat display fix, Save DC calculation
2. `cogs/combat.py` - Auto-damage fix, star costs outside combat
3. `cogs/deployables.py` - Complete `/deploy create` redesign
4. `database/migrate_deployables_table.py` - NEW migration script

All files pass syntax checks ✅
