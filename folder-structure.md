### Project Structure

```plaintext
ronan-jr-v3
├── __pycache__/
│   └── bot.cpython-313.pyc [3.82 KB]
├── cogs/
│   ├── __pycache__/
│   │   ├── character.cpython-312.pyc [32.98 KB]
│   │   ├── character.cpython-313.pyc [50.45 KB]
│   │   ├── combat.cpython-312.pyc [91.16 KB]
│   │   ├── combat.cpython-313.pyc [92.04 KB]
│   │   ├── deployables.cpython-313.pyc [29.96 KB]
│   │   ├── forms.cpython-313.pyc [35.64 KB]
│   │   ├── help.cpython-312.pyc [12.88 KB]
│   │   ├── help.cpython-313.pyc [12.51 KB]
│   │   ├── moves.cpython-312.pyc [33.84 KB]
│   │   └── moves.cpython-313.pyc [72.03 KB]
│   ├── character.py [49.26 KB]
│   ├── combat.py [78.24 KB]
│   ├── deployables.py [22.43 KB]
│   ├── forms.py [25.89 KB]
│   ├── help.py [14.40 KB]
│   └── moves.py [59.55 KB]
├── data/
│   └── saves/
│       ├── corrupt.json [13 bytes]
│       └── test_save.json [867 bytes]
├── database/
│   ├── __pycache__/
│   │   ├── init_db.cpython-312.pyc [4.62 KB]
│   │   └── init_db.cpython-313.pyc [4.60 KB]
│   ├── init_db.py [3.60 KB]
│   ├── migrate_db.py [1.51 KB]
│   ├── migrate_deployables.py [2.95 KB]
│   ├── migrate_effects_table.py [1.00 KB]
│   ├── migrate_forms_extended.py [1.83 KB]
│   ├── migrate_max_stars.py [1.32 KB]
│   ├── migrate_modifiers.py [2.71 KB]
│   ├── migrate_movesets.py [1.89 KB]
│   ├── migrate_temp_ac.py [2.09 KB]
│   ├── migrate_temp_hp.py [624 bytes]
│   ├── migrate_tier_system.py [1.77 KB]
│   └── ronan.db [68.00 KB]
├── tests/
│   ├── __pycache__/
│   │   ├── test_character_system.cpython-313-pytest-9.0.2.pyc [21.53 KB]
│   │   ├── test_combat_system.cpython-313-pytest-9.0.2.pyc [22.67 KB]
│   │   ├── test_effects_system.cpython-313-pytest-9.0.2.pyc [23.01 KB]
│   │   └── test_saves_system.cpython-313-pytest-9.0.2.pyc [23.60 KB]
│   ├── test_attacks.py [10.34 KB]
│   ├── test_character_system.py [7.53 KB]
│   ├── test_characters.py [9.04 KB]
│   ├── test_characters_simple.py [6.88 KB]
│   ├── test_combat.py [10.96 KB]
│   ├── test_combat_system.py [9.20 KB]
│   ├── test_deployables.py [10.95 KB]
│   ├── test_dice.py [2.93 KB]
│   ├── test_dice_unified.py [5.76 KB]
│   ├── test_effects_system.py [10.46 KB]
│   ├── test_moves.py [13.03 KB]
│   ├── test_polish.py [9.46 KB]
│   ├── test_saveload.py [11.99 KB]
│   └── test_saves_system.py [6.07 KB]
├── utils/
│   ├── __pycache__/
│   │   ├── constants.cpython-312.pyc [2.40 KB]
│   │   ├── constants.cpython-313.pyc [2.54 KB]
│   │   ├── dice.cpython-313.pyc [4.45 KB]
│   │   ├── effects.cpython-313.pyc [9.67 KB]
│   │   ├── helpers.cpython-313.pyc [10.20 KB]
│   │   ├── move_execution.cpython-313.pyc [5.73 KB]
│   │   └── moveset_parser.cpython-313.pyc [12.04 KB]
│   ├── constants.py [1.44 KB]
│   ├── dice.py [3.95 KB]
│   ├── effects.py [6.25 KB]
│   ├── helpers.py [6.51 KB]
│   ├── move_execution.py [5.17 KB]
│   └── moveset_parser.py [10.64 KB]
├── PROMPT1_IMPLEMENTATION.md [9.25 KB]
├── QUICK_START.md [5.24 KB]
├── README.md [4.88 KB]
├── STARFALL_LITE.md [27.44 KB]
├── bot.py [2.40 KB]
└── requirements.txt [45 bytes]
```


### Summary

```plaintext
Root Folder: ronan-jr-v3
Total Folders: 11
Total Files: 70
File Types:
  - .py Files: 38
  - .md Files: 4
  - .txt Files: 1
  - .pyc Files: 24
  - .json Files: 2
  - .db Files: 1
Largest File: combat.cpython-313.pyc [92.04 KB]
Smallest File: corrupt.json [13 bytes]
Total Project Size: 1.13 MB
Ignored Files and Folders:
  - bot.log
```
