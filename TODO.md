# Ronan Jr v3 - Testing & Deployment Checklist

## 🔴 Critical - Database Migration

- [ ] **Fix deployables table schema**
  - Current columns: `name`, `owner`, `duration`, `owner_name`
  - Need: `id`, `deployable_name`, `owner_name`, `hp`, `max_hp`, `stars`, `max_stars`, `available_until_round`, `created_round`
  - Options:
    - Run migration script to alter table
    - Or delete table and let code recreate it on first `/deploy create`
  - Location: `database/ronan.db`

---

## 🟡 High Priority - Discord Testing

### Form Transformation
- [ ] Test `/form transform` with character that has 5 stars
  - Verify stars are properly detected (not shown as 0)
  - Check transform succeeds when stars available
  - Check transform fails when stars insufficient
  - Verify logging shows costs and stat changes in one line

### Attack Command
- [ ] Test `/attack` with attack_type dropdown
  - [ ] Test light attack (1 star, base damage 4)
  - [ ] Test medium attack (2 stars, base damage 8)
  - [ ] Test heavy attack (4 stars, base damage 14)
  - [ ] Test auto-damage calculation (leave damage blank)
  - [ ] Test with roll_stat parameter
  - [ ] Test hide_ac parameter

### Damage Threshold System
- [ ] Set threshold on a character: `/char` commands to set threshold_damage and threshold_dc
- [ ] Test damage below threshold - should NOT show warning
- [ ] Test damage at/above threshold - should show CON save warning
- [ ] Verify warning appears in `/attack` embeds
- [ ] Verify warning appears in `/move use` embeds (attack and save types)

### Deployables - Phase 1
- [ ] Test `/deploy create` basic functionality
  - [ ] Create deployable without any optional parameters
  - [ ] Create deployable with duration (in combat)
  - [ ] Create deployable without duration (permanent)
  - [ ] Verify HP and Stars set correctly

- [ ] Test `/deploy attack`
  - [ ] Verify owner parameter is first and required
  - [ ] Test autocomplete for deployable (filtered by owner)
  - [ ] Test light/medium/heavy attack types
  - [ ] Test auto-damage calculation (uses owner's stats)
  - [ ] Verify stars deducted from deployable, not owner
  - [ ] Check embed format is correct

### Deployables - Phase 2
- [ ] Test `/move use` with deployable parameter
  - [ ] Verify deployable autocomplete (filtered by character/owner)
  - [ ] Test move execution with deployable
  - [ ] Verify stars deducted from deployable
  - [ ] Verify MP/HP deducted from owner (not deployable)
  - [ ] Check embed shows "Deployable (Owner's) → Move → Target"
  - [ ] Test attack move type
  - [ ] Test save move type
  - [ ] Test utility move type

### Deployables - Phase 3
- [ ] Test `/deploy create` with resource costs
  - [ ] Test with resource_type=MP
  - [ ] Test with resource_type=HP
  - [ ] Test with resource_type=Stars
  - [ ] Verify validation (both resource_cost and resource_type required together)
  - [ ] Test with insufficient resources (should fail)
  - [ ] Test with sufficient resources (should succeed and deduct)
  - [ ] Verify embed shows cost: "💸 Cost: 💙 20 MP"

### Deployables - Phase 4 (Already tested above in Damage Threshold)
- [ ] Verify damage threshold works for attacks against characters
- [ ] Verify no threshold check for attacks against deployables

### Deployables - Phase 5
- [ ] Test `/deploy create` with mp_scaling
  - [ ] Verify mp_scaling requires resource_type=MP
  - [ ] Test with mp_scaling=True and no resource_type (should fail)
  - [ ] Test with mp_scaling=True, resource_type=MP, resource_cost=25
    - Base HP=10, Stars=2 → Should become HP=15, Stars=7
  - [ ] Verify embed shows scaling: "15/15 (10+5)"
  - [ ] Test with different MP amounts (10, 25, 50)

---

## 🟢 Nice to Have - Additional Testing

### Error Handling
- [ ] Test commands with missing required parameters
- [ ] Test commands with invalid character names
- [ ] Test commands with invalid target names
- [ ] Verify [ERROR] logs appear in console for all error cases

### Edge Cases
- [ ] Character with 0 stars tries to transform
- [ ] Character with 0 MP tries to create deployable with MP cost
- [ ] Deployable with 0 stars tries to use move
- [ ] Attack against non-existent target
- [ ] Move use against deployable target
- [ ] Creating deployable with same name as existing one

### UI/UX
- [ ] Verify all embeds use horizontal format (v2 defer pattern)
- [ ] Check all autocomplete filters work correctly
- [ ] Verify embed colors are appropriate (green/orange/red/purple)
- [ ] Check all emoji icons display correctly in Discord

---

## 📝 Documentation

- [ ] Update command documentation if needed
- [ ] Document new parameters and their usage
- [ ] Create example commands for common scenarios
- [ ] Update DEPLOYABLES_PLAN.md to mark phases as complete

---

## 🚀 Deployment

- [ ] Commit any final fixes
- [ ] Push to remote repository
- [ ] Deploy bot to server
- [ ] Test in live Discord environment
- [ ] Monitor logs for any unexpected errors

---

## 📊 Known Issues to Monitor

- **Database Schema**: Deployables table may need recreation on first use
- **Windows Console**: Emoji rendering in logs (cosmetic only)
- **Threshold Columns**: Make sure threshold_damage and threshold_dc migration ran successfully

---

## ✅ Completed This Session

- [x] Fixed form transform star validation bug
- [x] Enhanced transform logging (costs + stat changes)
- [x] Added attack_type dropdown to /attack
- [x] Implemented auto-damage calculation
- [x] Added ~100 [ERROR] logs across all cogs
- [x] Removed combat requirement from /deploy create
- [x] Phase 1: /deploy attack overhaul
- [x] Phase 2: /move use with deployable parameter
- [x] Phase 3: Resource costs on /deploy create
- [x] Phase 4: Damage threshold system
- [x] Phase 5: MP scaling on /deploy create
- [x] All syntax checks passed
- [x] All logic verification tests passed
- [x] Git commits created for all features

---

**Total Features Implemented**: 11
**Total Git Commits**: 5
**Total Lines Changed**: ~500+
**Test Coverage**: Logic verified, ready for Discord UI testing
