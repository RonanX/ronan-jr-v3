# Deployables System Test Summary - Phases 1-5

## Test Status: ⚠️ DATABASE SCHEMA MISMATCH

The code expects these deployables columns:
- `deployable_name`, `owner_name`, `available_until_round`, `created_round`, `id`

The database has these columns:
- `name`, `owner`, `owner_name`, `duration`

**The database schema needs to be updated before the bot can run.**

---

## What Each Phase Would Test

### ✅ Phase 1: /deploy attack
**Purpose**: Deployable attacks using owner's stats for rolls, deployable's stars for costs

**Test Coverage**:
- Auto-damage calculation: `base_damage[attack_type] + max(owner_STR, owner_DEX)`
- Example: medium attack (8 base) + 5 STR = 13 damage
- Deployable uses owner's stats for attack rolls
- Stars deducted from deployable, not owner

**Expected Results**:
```
Owner stats: STR 5, DEX 3
Attack type: medium
Auto-damage: 8 (base) + 5 (highest offensive) = 13
Deployable uses owner's stats for attack rolls
```

---

### ✅ Phase 2: /move use with deployable
**Purpose**: Deployables can execute moves using their own stars but owner's stats/MP

**Test Coverage**:
- Stars deducted from deployable (not character)
- MP/HP deducted from owner (not deployable)
- Embed shows: "TestDrone1 (TestCharAlice's) → Fireball → Bob"

**Expected Results**:
```
Deployable: TestDrone1 (Stars: 3)
Move cost: 2 stars
Stars deducted from deployable: 3 → 1
MP/HP costs deduct from owner (TestCharAlice), not deployable
```

---

### ✅ Phase 3: Resource costs on /deploy create
**Purpose**: Creating deployables costs MP/HP/Stars from owner

**Test Coverage**:
- MP cost validation (owner has enough MP)
- MP deduction from owner character
- Deployable created with specified stats
- Embed shows cost: "💸 Cost: 💙 10 MP"

**Expected Results**:
```
Initial MP: 40
MP cost: 10
MP deducted correctly: 40 → 30 (cost: 10)
Deployable created: TestDrone1 (HP: 15, Stars: 3)
```

---

### ✅ Phase 4: Damage threshold system
**Purpose**: Characters with threshold settings require CON saves when taking high damage

**Test Coverage**:
- Threshold data stored in characters table
- Damage below threshold: no warning
- Damage at/above threshold: CON save required
- Embed shows: "⚠️ Damage Threshold: Bob must make a DC 11 CON save or suffer additional effects!"

**Expected Results**:
```
TestCharBob threshold: 10 damage, DC 11 CON save
8 damage < 10 threshold: No CON save needed
15 damage ≥ 10 threshold: DC 11 CON save required!
```

---

### ✅ Phase 5: MP scaling on /deploy create
**Purpose**: Spending more MP creates stronger deployables

**Test Coverage**:
- Scaling formula: `final_stat = base_stat + (MP_spent / 5)`
- Both HP and Stars scale
- Embed shows bonus: "20/20 (15+5)"

**Expected Results**:
```
Base stats: HP 10, Stars 2
MP spent: 25 → Bonus: +5 HP, +5 Stars
Scaling correct: HP 10+5=15, Stars 2+5=7
```

---

## Code Verification

All 5 phases have been implemented in the codebase:

1. **Phase 1**: [deployables.py:202-406](../cogs/deployables.py#L202-L406) - /deploy attack command
2. **Phase 2**: [moves.py:936-1116](../cogs/moves.py#L936-L1116) - /move use with deployable parameter
3. **Phase 3**: [deployables.py:148-226](../cogs/deployables.py#L148-L226) - Resource cost validation and deduction
4. **Phase 4**:
   - [combat.py:1240-1456](../cogs/combat.py#L1240-L1456) - /attack threshold checking
   - [moves.py:1137-1318](../cogs/moves.py#L1137-L1318) - /move use threshold checking
5. **Phase 5**: [deployables.py:228-271](../cogs/deployables.py#L228-L271) - MP scaling logic

---

## Next Steps

1. **Run database migration** to update deployables table schema
2. **Test in Discord** to verify UI and interaction flow
3. **Check autocomplete** filtering (deployables by owner, by character)
4. **Verify embeds** display correctly with all new fields

---

## Syntax Verification

All Python files compile successfully:
- ✅ `cogs/combat.py`
- ✅ `cogs/moves.py`
- ✅ `cogs/deployables.py`
- ✅ `database/add_threshold_columns.py` (executed successfully)
