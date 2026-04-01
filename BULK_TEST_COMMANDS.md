# Bulk Test Commands for UI/UX Overhaul

Test these commands in Discord to verify the horizontal embed format with deferred responses.

## Setup
1. Make sure you have combat started: `/init start`
2. Have at least 2 characters in the database with moves, forms, etc.

## Test Checklist

### ✅ `/char status` - Resource Management
**Read-only (ephemeral):**
```
/char status character:Alicia
```
- Should show ephemeral embed (only you see it)
- Should NOT have "user used /char status" message above it
- Format: `❤️ HP/MAX  💙 MP/MAX  ⭐ STARS/MAX  🛡️ AC`

**Update with relative values (visible):**
```
/char status character:Alicia hp:+10
/char status character:Alicia hp:-15
/char status character:Alicia mp:+20 stars:-1
```
- Should defer ephemeral (no "user used command" message)
- Should send VISIBLE embed (everyone sees it, no reply indicator)
- Format: `Alicia: ❤️ 45 → 55, 💙 80 → 100`

**Senzu bean:**
```
/char status character:Alicia hp:senzu mp:senzu stars:senzu
```
- Should restore all to max
- Format: `Alicia: ❤️ 45 → 60, 💙 80 → 110, ⭐ 3 → 5`

**Temp resources:**
```
/char status character:Alicia temp_hp:15 temp_duration:3
/char status character:Alicia temp_stars:2
```
- Should add temp resources with (+X temp) notation
- Format: `Alicia: ❤️ 60/60 (+15 temp)`

---

### ✅ `/init next` - Turn Advancement
```
/init next
```
- Should defer (no "user used command")
- Should show embed with title "🎯 {Character}'s Turn!"
- Should have horizontal resource line: `❤️ HP/MAX (+temp)  💙 MP/MAX  ⭐ STARS/MAX`
- Should show star refresh if applicable
- Should show DoT ticks, effect expiry, etc.

---

### ✅ `/move use` - Attack Move
```
/move use character:Alicia move_name:[attack move] target:Hinobi
```
**Expected for MISS:**
- Defer (no "user used command")
- Embed title: `⚔️ Alicia → [move] → Hinobi`
- Description: "💨 **MISS** - Combo breaks!"
- Field "🎲 Roll": `5d6 [4,3,2,5,1] → 5 vs AC 14`
- Field "💸 Cost": `⭐2 💙10`

**Expected for HIT:**
- Defer (no "user used command")
- Embed title: `⚔️ Alicia → [move] → Hinobi`
- Color: Green (clean hit) or Orange (hit with cost)
- Field "🎲 Roll": `5d6 [6,5,4,3,2] → 6 vs AC 14 - ✅ Clean Hit`
- Field "Damage": `💥 25 damage\nHinobi: ❤️ 60 → 35`
- Field "⚠️ Effect" (if bonus_on_hit exists)

**Expected for MULTIHIT:**
- Field "🎲 Roll": Shows hits landed (e.g., "3/4 hits land")
- Field "Damage": `💥 30 damage (10/hit × 3)`

---

### ✅ `/move use` - Save Move
```
/move use character:Alicia move_name:[save move] target:Hinobi
```
**Expected:**
- Defer (no "user used command")
- Embed title: `⚔️ Alicia → [move] → Hinobi`
- Color: Blue (success) or Red (fail)
- Field "🎲 Save": `Hinobi rolls DEX save (DC 15)\n4d6 [5,4,3,2] = 5 → ❌ Fail`
- Field "Damage": `💥 20 damage\nHinobi: ❤️ 35 → 15`
- Field "⚠️ Effect" (only on failed save)

---

### ✅ `/move use` - Utility Move
```
/move use character:Alicia move_name:[utility move]
```
**Expected:**
- Defer (no "user used command")
- Embed title: `🛠️ Alicia → [move]`
- Color: Purple
- Field "💸 Cost": `💙 80 → 60, ⭐ 5 → 3`
- Field "Effect": Description text

---

### ✅ `/form transform` - Transformation
```
/form transform character:Hinobi form:Speed Breaker
```
**Expected:**
- Defer (no "user used command")
- Embed title: `✨ Hinobi transforms into Speed Breaker form!`
- Color: Gold
- Field "💸 Cost": `💙 100 → 80, ❤️ 60 → 50`
- Field "📊 Changes": `STR: 3→5, DEX: 4→6 | 🛡️ AC: 12→14`
- Field "⚠️ Warnings": `⏱️ Reverts in 5 rounds` or `💢 10 fire DoT/turn`

---

### ✅ `/form revert` - Revert to Base
```
/form revert character:Hinobi
```
**Expected:**
- Defer (no "user used command")
- Embed title: `🔄 Hinobi reverts to base form`
- Color: Blue

---

### ✅ `/deploy attack` - Deployable Attack
(Requires deployable to be spawned first)
```
/deploy attack deployable:[name] move_name:[move] target:Hinobi
```
**Expected for HIT:**
- Defer (no "user used command")
- Embed title: `⚔️ [Deployable] (Alicia's) → [move] → Hinobi`
- Same format as `/move use` attack, but with deployable attribution

---

## Common Issues to Check

### ❌ "This interaction has already been responded to before"
- Means there's a `await interaction.response.send_message()` after a defer
- Should be `await interaction.followup.send()` instead

### ❌ "User used /command" message appears above embed
- Means the defer is missing or came too late
- Should have `await interaction.response.defer()` near the start
- For read-only commands, use `defer(ephemeral=True)`

### ❌ Embed has weird reply indicator/line above it
- Means the defer wasn't ephemeral when it should be
- For updates that should be visible: `defer(ephemeral=True)` then `followup.send(embed, ephemeral=False)`

### ❌ Plain text instead of embed
- Means we forgot to wrap the message in `discord.Embed()`
- Should be `embed = discord.Embed(description=..., color=...)` then `followup.send(embed=embed)`

---

## Quick Test Script

Run these in order:
```
/char status character:Alicia
/char status character:Alicia hp:-20
/char status character:Alicia hp:+10 mp:-15
/init start
/init next
/move use character:Alicia move_name:[attack] target:Hinobi
/move use character:Alicia move_name:[save] target:Hinobi
/move use character:Alicia move_name:[utility]
/form transform character:Hinobi form:[form_name]
/form revert character:Hinobi
/init next
```

All commands should:
1. NOT show "user used /command" message
2. Use embeds (not plain text)
3. Show horizontal format with deltas where applicable
4. Use proper colors (green/orange/red/blue/purple/gold)
