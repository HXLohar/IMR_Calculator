# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A mahjong hand scoring calculator for the **Innovative Mahjong Ruleset (IMR)**. It parses hand strings, finds all valid winning patterns, detects achieved scoring patterns (fans), and calculates the final score.

## Running the Project

```bash
python main.py                    # Interactive REPL
python main.py <hand>             # Analyze a single hand
python main.py --score <hand>     # Analyze with score output
python main.py --no-score         # Interactive without scoring
python main.py --test             # Run built-in test suite (16 cases)
python main.py --help             # Show help and notation guide
```

There is no separate test runner or build step — tests are embedded in `main.py` via `run_tests()` and `fan.py` via `run_fan_tests()`.

## Input Format

```
[calls]hand_tiles + winning_tile[*] [+flags]

[RRRR*][123b]4567899b + 9b* +LT     # concealed quad, self-drawn, last tile
19b19c19dESWNWhGR + R*              # Thirteen Orphans
1122334455667b + 7b*                # Seven Pairs
```

**English notation**: suits `b/c/d` (bamboo/character/dot), honors `E S W N R G Wh`  
**Japanese notation**: suits `s/p/m`, honors `1z–7z`  
`*` on winning tile = self-drawn; `+LT` = last tile win; calls in `[]`, `*` inside call = concealed quad

## Architecture

The pipeline is linear across two files:

**`main.py`** — parsing → validation → hand explanation  
- `parse_hand()` detects format and builds a `ParsedHand` (tiles + calls + winning tile + flags)
- `validate_hand()` checks tile counts and call legality
- `find_all_explanations()` generates every valid decomposition: 13 Orphans, 7 Pairs, or classic 4-group+pair patterns (TTTTp, TTTSp, TTSSp, TSSSp, SSSSp)
- Returns all valid `HandExplanation` objects (a hand may have multiple)

**`fan.py`** — fan detection → override resolution → scoring  
- `load_fans_from_csv()` loads ~60 fan definitions from `data/fan.csv` at startup
- `detect_fans()` checks each fan condition against a `HandExplanation`
- `apply_overrides()` removes lower-priority fans superseded by higher ones (transitive closure pre-computed)
- `calculate_score()` sums fan points with IMR rules: excellence fans halve secondary fans; regular fans cap at 3000 pts with excess halved
- Main API: `score_hand(explanation)` returns a `ScoringResult`

**`data/fan.csv`** — source of truth for all fan definitions (id, points, names in English/Chinese, override relationships, hand format constraints)

## Fan Categories (IDs)

| Range | Category |
|-------|----------|
| 101–124 | Excellence fans (special scoring) |
| 201–218 | Flush and number patterns |
| 251–265 | Quad/triplet patterns |
| 301–309 | Straight patterns |
| 401–413 | Hand type fans (all-triplets, 7-pairs, etc.) |
| 501 | Self-drawn |

## Key Data Structures

- `Tile`: `(type: TileType, value: int)` — immutable, value semantics
- `Call`: `(type: CallType, tiles: list[Tile], is_concealed: bool)`
- `ParsedHand`: everything from the input string
- `HandExplanation`: one valid decomposition with groups, pair, calls, winning tile, flags
- `Fan` / `AchievedFan` / `ScoringResult`: scoring layer
