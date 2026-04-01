# Deployables System Overhaul Plan

## Current Issues

1. **`/deploy attack` lacks owner parameter** - searches through ALL deployables instead of filtering by owner
2. **Deployables use owner's movesets** - but there's a `deployable_moves` table that's unused
3. **No clear workflow** for how deployables should work in practice

## Design Questions to Answer

### Q1: How should deployables use moves?

**Option A: Use owner's moveset** (current partial implementation)
- Deployable uses moves from owner's character sheet
- Simpler - no need to manage separate movesets
- Makes sense thematically (clone/summon uses caster's abilities)

**Option B: Deployables have their own movesets**
- Use the `deployable_moves` table
- More flexible - deployable can have unique moves
- More complex - need `/deploy addmove` command

**Recommendation:** **Option A** for now - simpler and thematically appropriate. Keep `deployable_moves` table for future expansion.

### Q2: How should `/deploy attack` work?

**Current issues:**
- No owner filter means it could search ALL deployables across all combats
- Uses `deployable_moves` table which is empty

**Proposed design (matching `/attack`):**
```
/deploy attack
  owner: Character (required, autocomplete)
  deployable: Deployable name (required, filtered by owner)
  attack_type: light/medium/heavy (required, dropdown)
  target: Target character (required, autocomplete)
  damage: Damage amount (optional - auto-calculates like /attack)
```

**Benefits:**
- Matches `/attack` command structure
- Owner filter prevents ambiguity
- Auto-damage calculation reduces mental math
- Uses owner's stats for the attack (thematic)

### Q3: What other deployable commands are needed?

**Current commands:**
- `/deploy create` - ✅ Works (with duration now optional)
- `/deploy attack` - ⚠️ Needs overhaul
- `/deploy damage` - ❓ Need to verify
- `/deploy list` - ❓ Need to verify
- `/deploy remove` - ❓ Need to verify

**Missing commands:**
- `/deploy show` - Display deployable stats/info
- `/deploy status` - Update deployable HP/stars (like `/char status`)

## Implementation Plan

### Phase 1: Fix `/deploy attack`

**Changes needed:**
1. Add `owner` parameter (required, first parameter)
2. Add `attack_type` parameter (dropdown: light/medium/heavy)
3. Make `damage` parameter optional with auto-calculation
4. Change `deployable` autocomplete to filter by owner
5. Remove `move_name` parameter (use attack_type instead)
6. Use owner's stats for attack roll
7. Spend deployable's stars (not owner's)
8. Update to use v2 defer pattern (defer ephemeral → delete → channel.send)

**Signature:**
```python
async def attack_with_deployable(
    interaction,
    owner: str,              # NEW - filters deployables
    deployable: str,         # EXISTING - now filtered by owner
    attack_type: str,        # NEW - light/medium/heavy dropdown
    target: str,             # EXISTING
    damage: int = None,      # CHANGED - now optional
    roll_stat: str = None,   # NEW - optional stat override
    hide_ac: bool = False    # NEW - matches /attack
)
```

### Phase 2: Add `/deploy show`

Show deployable info:
- Owner
- HP/Max HP
- Stars/Max Stars
- Duration remaining (if applicable)
- Created round

### Phase 3: Add `/deploy status`

Update deployable resources (matching `/char status`):
```
/deploy status
  deployable: Deployable name
  hp: HP change (+10, -5, or senzu)
  stars: Stars change
```

### Phase 4: Verify other commands

- `/deploy list` - Should show all active deployables (with owner info)
- `/deploy damage` - Verify it works correctly
- `/deploy remove` - Verify it works correctly

## Database Schema

**Current `deployables` table:** (after fix_deployables_schema.py)
```sql
CREATE TABLE deployables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_name TEXT NOT NULL,
    deployable_name TEXT NOT NULL,
    hp INTEGER NOT NULL,
    max_hp INTEGER NOT NULL,
    stars INTEGER NOT NULL,
    max_stars INTEGER NOT NULL,
    available_until_round INTEGER NOT NULL,
    created_round INTEGER NOT NULL,
    FOREIGN KEY (owner_name) REFERENCES characters(name) ON DELETE CASCADE
)
```

**`deployable_moves` table:** (currently unused)
- Keep for future expansion
- If we add custom deployable abilities later, this table is ready

## Testing Checklist

After implementation:
- [ ] `/deploy create owner:test name:turret hp:20 stars:3` - permanent deployable
- [ ] `/deploy create owner:test name:clone hp:30 stars:5 duration:3` - temporary (in combat)
- [ ] `/deploy attack owner:test deployable:turret attack_type:light target:enemy` - auto damage
- [ ] `/deploy attack owner:test deployable:turret attack_type:medium target:enemy damage:15` - manual damage
- [ ] `/deploy show deployable:turret` - view stats
- [ ] `/deploy status deployable:turret hp:-10` - take damage
- [ ] `/deploy list` - see all deployables
- [ ] `/deploy remove deployable:turret` - delete deployable

## Future Enhancements (Phase 5+)

- Custom deployable movesets using `deployable_moves` table
- Deployable AC modifier (separate from owner)
- Deployable abilities (passive effects)
- `/deploy transform` for shapeshifting deployables
- Multi-target deployable attacks
