---
name: UI implementation progress
description: Progress tracker for ui.py GUI implementation task
type: project
---

# UI Implementation Progress

## Status: COMPLETE

## All tasks done
- [x] WhWhWhWh: already worked in parse_tiles_english (no count=1 bug)
- [x] fan.py: already using data/fan.csv via _DEFAULT_FAN_CSV
- [x] BUGFIX main.py line 372: additional_notes now prepends '+' so '+AQ', '+BOH' etc. work
- [x] ui.py: rewritten with place() absolute coordinates
- [x] All 16 main.py tests pass
- [x] Fan 407 (Win After a Quad) now detects correctly

## Architecture summary
- Window: 1065×720, fixed, not resizable
- Left panel (tile library): place(x=0, y=0, w=515, h=720)
  - Tile cells: 53×67px each, step 55px
  - 4 rows at y=48, 120, 192, 264
- Divider: 5px at x=515
- Right panel: place(x=520, y=0, w=545, h=720)
  - All child widgets use place() with absolute coords
  - Option buttons use place() within inner frame

## Known remaining issues (minor)
- Score area has no scrollbar - may overflow with many fans
- Option inner frame size hardcoded (382×108) - fine for current 9 options
