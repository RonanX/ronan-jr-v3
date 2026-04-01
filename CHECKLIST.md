# Ronan Jr v3 - Development Checklist

## ✅ Completed Features

### Hidden Resources System
- [x] Add `hidden_resources` column to characters table
- [x] Add `hidden_resources` column to deployables table
- [x] Implement `/char hide` toggle (works for characters AND deployables)
- [x] Hide HP/MP/Stars/AC in embeds when hidden_resources is True
- [x] Hide Stats/Proficiency/Tier/Save DC when hidden_resources is True
- [x] Add debug logging for hidden characters: `[HIDDEN] name | HP: X/Y | MP: A/B`
- [x] Add `hidden_resources` parameter to `/char create`
- [x] Add `hidden_resources` parameter to `/deploy create`

### Threshold & Squishy System
- [x] Add `threshold_damage`, `threshold_dc`, `squishy` to `/char create`
- [x] Add support for threshold/squishy in `/char update`
- [x] Threshold warnings in `/attack` when damage exceeds threshold

### Commands
- [x] `/char log` - Console annotations for debugging
- [x] `/char senzu` - Fully restore resources with senzu bean gif
- [x] `/deploy move_use` - Use deployable's moves (with owner_pays parameter)
- [x] `/deploy move_list` - List moves for a deployable
- [x] Comment out `/char hp` and `/char stars` (moving to `/char status`)

### Combat & Targeting
- [x] Fix `/attack` star cost validation with debug logging
- [x] Allow `/attack` to target deployables
- [x] Allow `/move use` to target deployables

### QOL Improvements
- [x] Add tier display to `/char show` description
- [x] Hide MP line in `/char show` if max_mp is 0
- [x] Fix temp resource bars (fill left to right: permanent → empty → temp)
- [x] Add deployables section to `/char show` with 3-block HP/Stars bars
- [x] Deploy create redesigned (ac, archetype, mp; separate cost parameters)

## 🔄 In Progress

### Character Status Redesign
- [ ] Redesign `/char status` with HP/MP/Stars management
- [ ] Add concise embeds with flavor text from old `/char hp` and `/char stars`
- [ ] Keep all original functionality (damage, healing, temp resources, star management)
- [ ] Use visual style of old commands but more condensed

## 📋 Backlog / Future Improvements

### Autocomplete Improvements
- [ ] Add fuzzy search to autocomplete
- [ ] Make autocomplete case-insensitive
- [ ] Include deployables in attack/target autocomplete

### Combat Embeds
- [ ] Condense `/attack` embed output (optional - discuss with user)
- [ ] Consider more compact move use results

### Move System
- [ ] Test deployable move execution fully
- [ ] Add move uses/slots restoration to `/char senzu`
- [ ] Verify move damage application to deployables

### Testing Needed
- [ ] Test damage threshold system
- [ ] Test squishy flag functionality
- [ ] Test all hidden resources scenarios
- [ ] Test deployable moves in combat
- [ ] Test deployable targeting in attacks and moves

## 🐛 Known Issues
- None currently reported

## 💡 Ideas for Later
- Improve autocomplete performance
- Add bulk character operations
- Export/import character data
- Combat analytics/statistics
- Move cooldown system

---

**Last Updated:** 2026-02-22
