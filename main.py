"""
Mahjong Hand Parser and Evaluator
Supports both Japanese (s/p/m, 1z-7z) and English (b/c/d, E/S/W/N/R/G/Wh) formats.
"""

import re
from typing import List, Dict, Tuple, Optional, Set
from collections import Counter
from itertools import combinations
from dataclasses import dataclass, field
from enum import Enum


class TileType(Enum):
    BAMBOO = 'bamboo'      # 条 (b/s)
    CHARACTER = 'character' # 万 (c/m)
    DOT = 'dot'            # 饼 (d/p)
    WIND = 'wind'          # 风 (E/S/W/N or 1z-4z)
    DRAGON = 'dragon'      # 三元 (R/G/Wh or 5z-7z)


@dataclass
class Tile:
    """Represents a single Mahjong tile."""
    tile_type: TileType
    value: int  # 1-9 for suits, 1-4 for winds (E=1,S=2,W=3,N=4), 1-3 for dragons (Wh=1,G=2,R=3)

    def __hash__(self):
        return hash((self.tile_type, self.value))

    def __eq__(self, other):
        if not isinstance(other, Tile):
            return False
        return self.tile_type == other.tile_type and self.value == other.value

    def __lt__(self, other):
        type_order = [TileType.CHARACTER, TileType.DOT, TileType.BAMBOO, TileType.WIND, TileType.DRAGON]
        if self.tile_type != other.tile_type:
            return type_order.index(self.tile_type) < type_order.index(other.tile_type)
        return self.value < other.value

    def __repr__(self):
        return self.to_english()

    def is_honor(self) -> bool:
        return self.tile_type in (TileType.WIND, TileType.DRAGON)

    def is_terminal(self) -> bool:
        """Check if tile is 1 or 9 of a suit."""
        return not self.is_honor() and self.value in (1, 9)

    def is_terminal_or_honor(self) -> bool:
        return self.is_honor() or self.is_terminal()

    def to_english(self) -> str:
        """Convert tile to English notation."""
        if self.tile_type == TileType.BAMBOO:
            return f"{self.value}b"
        elif self.tile_type == TileType.CHARACTER:
            return f"{self.value}c"
        elif self.tile_type == TileType.DOT:
            return f"{self.value}d"
        elif self.tile_type == TileType.WIND:
            winds = {1: 'E', 2: 'S', 3: 'W', 4: 'N'}
            return winds[self.value]
        elif self.tile_type == TileType.DRAGON:
            dragons = {1: 'Wh', 2: 'G', 3: 'R'}
            return dragons[self.value]

    def to_japanese(self) -> str:
        """Convert tile to Japanese notation."""
        if self.tile_type == TileType.BAMBOO:
            return f"{self.value}s"
        elif self.tile_type == TileType.CHARACTER:
            return f"{self.value}m"
        elif self.tile_type == TileType.DOT:
            return f"{self.value}p"
        elif self.tile_type == TileType.WIND:
            return f"{self.value}z"
        elif self.tile_type == TileType.DRAGON:
            return f"{self.value + 4}z"  # 5z, 6z, 7z


class CallType(Enum):
    STRAIGHT = 'straight'      # Chi/Chow - 3 consecutive tiles
    TRIPLET = 'triplet'        # Pon/Pung - 3 identical tiles
    QUAD = 'quad'              # Open Kan/Kong - 4 identical tiles
    CONCEALED_QUAD = 'concealed_quad'  # Closed Kan/Kong - 4 identical tiles (concealed)


@dataclass
class Call:
    """Represents a called/melded group of tiles."""
    call_type: CallType
    tiles: List[Tile]

    def __repr__(self):
        tiles_str = ''.join(t.to_english() for t in self.tiles)
        if self.call_type == CallType.CONCEALED_QUAD:
            return f"[{tiles_str}*]"
        return f"[{tiles_str}]"


@dataclass
class Group:
    """Represents a group in hand explanation (straight, triplet, quad, or pair)."""
    group_type: str  # 'straight', 'triplet', 'quad', 'pair'
    tiles: List[Tile]
    is_call: bool = False
    is_concealed_quad: bool = False

    def __repr__(self):
        tiles_str = format_tiles_compact(self.tiles)
        if self.is_call:
            if self.is_concealed_quad:
                return f"[{tiles_str}*]"
            return f"[{tiles_str}]"
        return f"({tiles_str})"


@dataclass
class ParsedHand:
    """Parsed mahjong hand."""
    calls: List[Call]
    hand_tiles: List[Tile]  # Tiles not in calls
    winning_tile: Tile
    is_self_drawn: bool  # True if winning tile was self-drawn (tsumo)
    additional_notes: str
    format_type: str  # 'japanese' or 'english'


@dataclass
class HandExplanation:
    """One possible way to explain/decompose a hand."""
    explanation_id: int
    pattern_type: str  # '13O', '7P', 'TTTTp', 'TTTSp', 'TTSSp', 'TSSSp', 'SSSSp'
    groups: List[Group]
    pair: Optional[List[Tile]]
    additional_notes: str
    is_self_drawn: bool
    winning_tile: Tile

    def __repr__(self):
        groups_str = ''.join(str(g) for g in self.groups)
        if self.pair:
            pair_str = f"({format_tiles_compact(self.pair)})"
            groups_str += pair_str
        drawn_mark = "*" if self.is_self_drawn else ""
        return f"id={self.explanation_id}, type='{self.pattern_type}', hand=\"{groups_str}{drawn_mark} +{self.additional_notes}\""


def format_tiles_compact(tiles: List[Tile]) -> str:
    """Format tiles in compact notation (e.g., 123b instead of 1b2b3b)."""
    if not tiles:
        return ""

    # Group by type
    sorted_tiles = sorted(tiles)

    result = []
    current_type = None
    current_values = []

    for tile in sorted_tiles:
        if tile.tile_type != current_type:
            if current_type is not None:
                result.append(_format_group(current_type, current_values))
            current_type = tile.tile_type
            current_values = [tile.value]
        else:
            current_values.append(tile.value)

    if current_type is not None:
        result.append(_format_group(current_type, current_values))

    return ''.join(result)


def _format_group(tile_type: TileType, values: List[int]) -> str:
    """Format a group of tiles of the same type."""
    if tile_type == TileType.BAMBOO:
        return ''.join(str(v) for v in values) + 'b'
    elif tile_type == TileType.CHARACTER:
        return ''.join(str(v) for v in values) + 'c'
    elif tile_type == TileType.DOT:
        return ''.join(str(v) for v in values) + 'd'
    elif tile_type == TileType.WIND:
        winds = {1: 'E', 2: 'S', 3: 'W', 4: 'N'}
        return ''.join(winds[v] for v in values)
    elif tile_type == TileType.DRAGON:
        dragons = {1: 'Wh', 2: 'G', 3: 'R'}
        return ''.join(dragons[v] for v in values)


# =============================================================================
# PARSING FUNCTIONS
# =============================================================================

def detect_format(input_str: str) -> Optional[str]:
    """Detect whether input is Japanese or English format."""
    # Remove calls and whitespace for analysis
    clean = re.sub(r'\[.*?\]', '', input_str)
    clean = re.sub(r'\s+', '', clean)

    # Check for Japanese suit indicators (s/p/m after digits or 1-7z)
    # Pattern: digit(s) followed by s, p, or m (case insensitive)
    has_japanese_suits = bool(re.search(r'\d[spmSPM]', clean))
    has_japanese_honors = bool(re.search(r'[1-7]z', clean, re.IGNORECASE))
    has_japanese = has_japanese_suits or has_japanese_honors

    # Check for English suit indicators (b/c/d after digits)
    has_english_suits = bool(re.search(r'\d[bcdBCD]', clean))
    # Check for English honor tiles (standalone E/S/W/N/R/G or Wh)
    # These should not be preceded by a digit (to avoid matching 1s, 2p, etc.)
    has_english_honors = bool(re.search(r'(?<!\d)(?:Wh|[ESWNRG])(?![a-z])', clean))
    has_english = has_english_suits or has_english_honors

    if has_japanese and has_english:
        return None  # Mixed format - invalid
    elif has_japanese:
        return 'japanese'
    elif has_english:
        return 'english'
    else:
        return None


def parse_tiles_japanese(tile_str: str) -> List[Tile]:
    """Parse Japanese notation tiles (e.g., '123s456p789m1234567z')."""
    tiles = []

    # Pattern: numbers followed by suit indicator
    pattern = r'(\d+)([spzmSPZM])'

    for match in re.finditer(pattern, tile_str):
        numbers = match.group(1)
        suit = match.group(2).lower()

        for num in numbers:
            value = int(num)

            if suit == 's':  # Bamboo (索/条)
                if 1 <= value <= 9:
                    tiles.append(Tile(TileType.BAMBOO, value))
            elif suit == 'p':  # Dot (筒/饼)
                if 1 <= value <= 9:
                    tiles.append(Tile(TileType.DOT, value))
            elif suit == 'm':  # Character (萬/万)
                if 1 <= value <= 9:
                    tiles.append(Tile(TileType.CHARACTER, value))
            elif suit == 'z':  # Honor
                if 1 <= value <= 4:  # Winds
                    tiles.append(Tile(TileType.WIND, value))
                elif 5 <= value <= 7:  # Dragons
                    tiles.append(Tile(TileType.DRAGON, value - 4))

    return tiles


def parse_tiles_english(tile_str: str) -> List[Tile]:
    """Parse English notation tiles (e.g., '123b456d789cESWNRGWh')."""
    tiles = []

    # First parse numbered tiles: digits followed by suit (b/c/d)
    pattern_suit = r'(\d+)([bcdBCD])'
    for match in re.finditer(pattern_suit, tile_str):
        numbers = match.group(1)
        suit = match.group(2).lower()

        for num in numbers:
            value = int(num)
            if 1 <= value <= 9:
                if suit == 'b':
                    tiles.append(Tile(TileType.BAMBOO, value))
                elif suit == 'd':
                    tiles.append(Tile(TileType.DOT, value))
                elif suit == 'c':
                    tiles.append(Tile(TileType.CHARACTER, value))

    # Remove suit patterns to parse honors
    remaining = re.sub(pattern_suit, '', tile_str)

    # Parse honor tiles
    # Wh must be parsed before W
    honor_patterns = [
        (r'Wh', TileType.DRAGON, 1),   # White dragon
        (r'G', TileType.DRAGON, 2),     # Green dragon
        (r'R', TileType.DRAGON, 3),     # Red dragon
        (r'E', TileType.WIND, 1),       # East wind
        (r'S', TileType.WIND, 2),       # South wind
        (r'W', TileType.WIND, 3),       # West wind
        (r'N', TileType.WIND, 4),       # North wind
    ]

    for pattern, tile_type, value in honor_patterns:
        count = len(re.findall(pattern, remaining))
        for _ in range(count):
            tiles.append(Tile(tile_type, value))
        remaining = re.sub(pattern, '', remaining)

    return tiles


def parse_tiles(tile_str: str, format_type: str) -> List[Tile]:
    """Parse tiles based on detected format."""
    if format_type == 'japanese':
        return parse_tiles_japanese(tile_str)
    else:
        return parse_tiles_english(tile_str)


def parse_call(call_str: str, format_type: str) -> Optional[Call]:
    """Parse a single call (e.g., '[123b]' or '[RRRR*]')."""
    # Remove brackets
    inner = call_str.strip('[]')

    # Check for concealed quad marker
    is_concealed = inner.endswith('*')
    if is_concealed:
        inner = inner[:-1]

    tiles = parse_tiles(inner, format_type)

    if not tiles:
        return None

    # Determine call type
    if len(tiles) == 3:
        if tiles[0] == tiles[1] == tiles[2]:
            return Call(CallType.TRIPLET, tiles)
        else:
            # Check if it's a valid straight
            sorted_tiles = sorted(tiles)
            if (not sorted_tiles[0].is_honor() and
                sorted_tiles[0].tile_type == sorted_tiles[1].tile_type == sorted_tiles[2].tile_type and
                sorted_tiles[1].value == sorted_tiles[0].value + 1 and
                sorted_tiles[2].value == sorted_tiles[0].value + 2):
                return Call(CallType.STRAIGHT, sorted_tiles)
            return None  # Invalid call
    elif len(tiles) == 4:
        if tiles[0] == tiles[1] == tiles[2] == tiles[3]:
            call_type = CallType.CONCEALED_QUAD if is_concealed else CallType.QUAD
            return Call(call_type, tiles)
        return None  # Invalid quad

    return None  # Invalid call length


def parse_hand(input_str: str) -> Tuple[Optional[ParsedHand], str]:
    """
    Parse a complete mahjong hand input.
    Returns (ParsedHand, error_message) - ParsedHand is None if parsing fails.
    """
    # Normalize whitespace
    input_str = input_str.strip()

    # Detect format
    format_type = detect_format(input_str)
    if format_type is None:
        return None, "Cannot detect format or mixed Japanese/English notation"

    # Split into main hand and additional notes
    # Format: hand_part + winning_tile +additional_notes
    # Example: [RRRR*][123b]4567899b + 9b* +LT

    parts = input_str.split('+')
    if len(parts) < 2:
        return None, "Missing winning tile (should have '+' separator)"

    hand_part = parts[0].strip()
    winning_part = parts[1].strip()
    additional_notes = ('+' + '+'.join(parts[2:])).strip() if len(parts) > 2 else ""

    # Parse winning tile
    is_self_drawn = winning_part.endswith('*')
    if is_self_drawn:
        winning_part = winning_part[:-1].strip()

    winning_tiles = parse_tiles(winning_part, format_type)
    if len(winning_tiles) != 1:
        return None, f"Winning tile must be exactly one tile, got {len(winning_tiles)}"
    winning_tile = winning_tiles[0]

    # Extract calls
    call_pattern = r'\[[^\]]+\]'
    call_matches = re.findall(call_pattern, hand_part)

    calls = []
    for call_str in call_matches:
        call = parse_call(call_str, format_type)
        if call is None:
            return None, f"Invalid call: {call_str}"
        calls.append(call)

    # Remove calls from hand_part to get remaining tiles
    remaining_hand = re.sub(call_pattern, '', hand_part)
    hand_tiles = parse_tiles(remaining_hand, format_type)

    return ParsedHand(
        calls=calls,
        hand_tiles=hand_tiles,
        winning_tile=winning_tile,
        is_self_drawn=is_self_drawn,
        additional_notes=additional_notes,
        format_type=format_type
    ), ""


# =============================================================================
# STEP 1: VALIDATION
# =============================================================================

def validate_hand(parsed: ParsedHand) -> Tuple[bool, str]:
    """
    Validate the parsed hand.
    Returns (is_valid, error_message).
    """
    # Count quads
    num_quads = sum(1 for c in parsed.calls if c.call_type in (CallType.QUAD, CallType.CONCEALED_QUAD))

    # Total tiles should be 13 + num_quads + 1 (winning tile)
    total_tiles = sum(len(c.tiles) for c in parsed.calls) + len(parsed.hand_tiles) + 1
    expected_tiles = 14 + num_quads

    if total_tiles != expected_tiles:
        return False, f"Expected {expected_tiles} tiles (13+{num_quads}+1), got {total_tiles}"

    # Check number of calls (max 4)
    if len(parsed.calls) > 4:
        return False, f"Too many calls: {len(parsed.calls)} (max 4)"

    # Count all tiles to check for duplicates (max 4 of each tile)
    all_tiles: List[Tile] = []
    for call in parsed.calls:
        all_tiles.extend(call.tiles)
    all_tiles.extend(parsed.hand_tiles)
    all_tiles.append(parsed.winning_tile)

    tile_counts = Counter(all_tiles)
    for tile, count in tile_counts.items():
        if count > 4:
            # Check if this is drawing dead: winning tile already maxed out in hand
            if tile == parsed.winning_tile and Counter(parsed.hand_tiles)[tile] == 4:
                return False, f"Drawing dead: 0 outs for {tile} (all 4 already in hand)"
            return False, f"Too many copies of {tile}: {count} (max 4)"

    # Validate additional flags
    notes = parsed.additional_notes.upper()
    has_non_quad_calls = any(
        c.call_type in (CallType.STRAIGHT, CallType.TRIPLET) for c in parsed.calls
    )
    has_quads = any(
        c.call_type in (CallType.QUAD, CallType.CONCEALED_QUAD) for c in parsed.calls
    )
    if '+BOH' in notes and parsed.calls:
        return False, "Blessing of Heaven (+BOH) requires no calls or concealed quads"
    if '+BOE' in notes and parsed.calls:
        return False, "Blessing of Earth (+BOE) requires no calls or concealed quads"
    if '+EW' in notes and has_non_quad_calls:
        return False, "Eastern Wind tenpai (+EW) cannot have open calls (quads only)"
    if '+DW' in notes and has_non_quad_calls:
        return False, "Declare Waiting (+DW) cannot have open calls (quads only)"
    if '+AQ' in notes and not has_quads:
        return False, "After Quad (+AQ) requires at least 1 quad"

    # Validate each call
    for call in parsed.calls:
        if call.call_type == CallType.STRAIGHT:
            tiles = sorted(call.tiles)
            if tiles[0].is_honor():
                return False, f"Straight cannot contain honor tiles: {call}"
            if not (tiles[0].tile_type == tiles[1].tile_type == tiles[2].tile_type):
                return False, f"Straight must be same suit: {call}"
            if not (tiles[1].value == tiles[0].value + 1 and tiles[2].value == tiles[0].value + 2):
                return False, f"Straight must be consecutive: {call}"
        elif call.call_type in (CallType.TRIPLET, CallType.QUAD, CallType.CONCEALED_QUAD):
            if not all(t == call.tiles[0] for t in call.tiles):
                return False, f"Triplet/Quad must be identical tiles: {call}"

    return True, ""


# =============================================================================
# STEP 2: HAND EXPLANATION
# =============================================================================

def find_all_explanations(parsed: ParsedHand) -> List[HandExplanation]:
    """
    Find all possible ways to explain/decompose the hand into a winning pattern.
    """
    explanations = []
    explanation_id = 1

    # Combine hand tiles with winning tile for analysis
    all_hand_tiles = parsed.hand_tiles + [parsed.winning_tile]

    # Check for special patterns first

    # 1. Thirteen Orphans (国士無双)
    if not parsed.calls:  # Must have no calls
        thirteen_result = check_thirteen_orphans(all_hand_tiles)
        if thirteen_result:
            exp = HandExplanation(
                explanation_id=explanation_id,
                pattern_type='13O',
                groups=thirteen_result,
                pair=None,
                additional_notes=parsed.additional_notes,
                is_self_drawn=parsed.is_self_drawn,
                winning_tile=parsed.winning_tile
            )
            explanations.append(exp)
            explanation_id += 1

    # 2. Seven Pairs (七対子)
    if not parsed.calls:  # Must have no calls
        seven_pairs_result = check_seven_pairs(all_hand_tiles)
        if seven_pairs_result:
            exp = HandExplanation(
                explanation_id=explanation_id,
                pattern_type='7P',
                groups=seven_pairs_result,
                pair=None,
                additional_notes=parsed.additional_notes,
                is_self_drawn=parsed.is_self_drawn,
                winning_tile=parsed.winning_tile
            )
            explanations.append(exp)
            explanation_id += 1

    # 3. Classic patterns (4 groups + 1 pair)
    classic_results = find_classic_explanations(parsed)
    for pattern_type, groups, pair in classic_results:
        exp = HandExplanation(
            explanation_id=explanation_id,
            pattern_type=pattern_type,
            groups=groups,
            pair=pair,
            additional_notes=parsed.additional_notes,
            is_self_drawn=parsed.is_self_drawn,
            winning_tile=parsed.winning_tile
        )
        explanations.append(exp)
        explanation_id += 1

    return explanations


def check_thirteen_orphans(tiles: List[Tile]) -> Optional[List[Group]]:
    """
    Check if tiles form Thirteen Orphans (国士無双).
    Requires: 1m9m1p9p1s9s + all 7 honor tiles + 1 duplicate for pair.
    """
    if len(tiles) != 14:
        return None

    required_tiles = [
        Tile(TileType.CHARACTER, 1), Tile(TileType.CHARACTER, 9),
        Tile(TileType.DOT, 1), Tile(TileType.DOT, 9),
        Tile(TileType.BAMBOO, 1), Tile(TileType.BAMBOO, 9),
        Tile(TileType.WIND, 1), Tile(TileType.WIND, 2),
        Tile(TileType.WIND, 3), Tile(TileType.WIND, 4),
        Tile(TileType.DRAGON, 1), Tile(TileType.DRAGON, 2), Tile(TileType.DRAGON, 3)
    ]

    tile_counts = Counter(tiles)
    required_counts = Counter(required_tiles)

    # Must have all required tiles
    for tile in required_tiles:
        if tile_counts[tile] < 1:
            return None

    # Must have exactly one pair (one tile appears twice)
    pair_tile = None
    for tile in required_tiles:
        if tile_counts[tile] == 2:
            pair_tile = tile
            break

    if pair_tile is None:
        return None

    # Verify total count
    total = sum(tile_counts[t] for t in required_tiles)
    if total != 14:
        return None

    # Create group representation
    groups = [Group('thirteen_orphans', sorted(tiles), is_call=False)]
    return groups


def check_seven_pairs(tiles: List[Tile]) -> Optional[List[Group]]:
    """
    Check if tiles form Seven Pairs (七対子).
    A tile appearing 4 times counts as 2 pairs (Premium/Deluxe pair).
    """
    if len(tiles) != 14:
        return None

    tile_counts = Counter(tiles)

    # Each tile must appear exactly 2 or 4 times (4 = deluxe/premium pair)
    for count in tile_counts.values():
        if count not in (2, 4):
            return None

    # Total pairs must equal 7
    total_pairs = sum(count // 2 for count in tile_counts.values())
    if total_pairs != 7:
        return None

    # Create group representation — 4-of-a-kind produces 2 pair groups
    groups = []
    for tile in sorted(tile_counts.keys()):
        num_pairs = tile_counts[tile] // 2
        for _ in range(num_pairs):
            groups.append(Group('pair', [tile, tile], is_call=False))

    return groups


def find_classic_explanations(parsed: ParsedHand) -> List[Tuple[str, List[Group], List[Tile]]]:
    """
    Find all classic pattern explanations (4 groups + 1 pair).
    Returns list of (pattern_type, groups, pair).
    """
    results = []

    # Convert calls to groups
    call_groups = []
    num_triplets_quads = 0
    num_straights = 0

    for call in parsed.calls:
        if call.call_type == CallType.STRAIGHT:
            group = Group('straight', call.tiles, is_call=True)
            num_straights += 1
        elif call.call_type == CallType.TRIPLET:
            group = Group('triplet', call.tiles, is_call=True)
            num_triplets_quads += 1
        elif call.call_type in (CallType.QUAD, CallType.CONCEALED_QUAD):
            is_concealed = call.call_type == CallType.CONCEALED_QUAD
            group = Group('quad', call.tiles, is_call=True, is_concealed_quad=is_concealed)
            num_triplets_quads += 1
        call_groups.append(group)

    # Combine hand tiles with winning tile
    remaining_tiles = parsed.hand_tiles + [parsed.winning_tile]

    # Number of groups we need to find from remaining tiles
    groups_needed = 4 - len(call_groups)

    # Find all possible decompositions of remaining tiles
    decompositions = find_decompositions(remaining_tiles, groups_needed)

    for groups, pair in decompositions:
        all_groups = call_groups + groups

        # Count pattern type
        total_t = num_triplets_quads + sum(1 for g in groups if g.group_type in ('triplet', 'quad'))
        total_s = num_straights + sum(1 for g in groups if g.group_type == 'straight')

        # Determine pattern type
        pattern_type = 'T' * total_t + 'S' * total_s + 'p'

        results.append((pattern_type, all_groups, pair))

    return results


def find_decompositions(tiles: List[Tile], groups_needed: int) -> List[Tuple[List[Group], List[Tile]]]:
    """
    Find all ways to decompose tiles into specified number of groups plus one pair.
    """
    results = []
    tile_counts = Counter(tiles)

    # Find all possible pairs first
    possible_pairs = [tile for tile, count in tile_counts.items() if count >= 2]

    for pair_tile in possible_pairs:
        # Remove pair from tiles
        remaining_counts = tile_counts.copy()
        remaining_counts[pair_tile] -= 2
        if remaining_counts[pair_tile] == 0:
            del remaining_counts[pair_tile]

        # Convert back to list
        remaining_list = []
        for tile, count in remaining_counts.items():
            remaining_list.extend([tile] * count)

        # Check if remaining tiles can form exactly groups_needed groups
        if len(remaining_list) != groups_needed * 3:
            continue

        # Find all ways to form groups from remaining tiles
        group_combinations = find_groups(remaining_counts, groups_needed)

        for groups in group_combinations:
            pair = [pair_tile, pair_tile]
            results.append((groups, pair))

    return results


def find_groups(tile_counts: Counter, num_groups: int, memo: dict = None) -> List[List[Group]]:
    """
    Recursively find all ways to form num_groups groups (straights or triplets) from tiles.
    """
    if num_groups == 0:
        if sum(tile_counts.values()) == 0:
            return [[]]
        return []

    if sum(tile_counts.values()) < num_groups * 3:
        return []

    # Create hashable key for memoization
    key = (tuple(sorted(tile_counts.items())), num_groups)
    if memo is None:
        memo = {}
    if key in memo:
        return memo[key]

    results = []

    # Get the smallest tile to try to form a group with
    available_tiles = sorted([t for t, c in tile_counts.items() if c > 0])
    if not available_tiles:
        return []

    first_tile = available_tiles[0]

    # Try to form a triplet with the first tile
    if tile_counts[first_tile] >= 3:
        new_counts = tile_counts.copy()
        new_counts[first_tile] -= 3
        if new_counts[first_tile] == 0:
            del new_counts[first_tile]

        sub_results = find_groups(new_counts, num_groups - 1, memo)
        for sub in sub_results:
            group = Group('triplet', [first_tile, first_tile, first_tile], is_call=False)
            results.append([group] + sub)

    # Try to form a straight starting with the first tile
    if not first_tile.is_honor() and first_tile.value <= 7:
        next1 = Tile(first_tile.tile_type, first_tile.value + 1)
        next2 = Tile(first_tile.tile_type, first_tile.value + 2)

        if tile_counts.get(next1, 0) >= 1 and tile_counts.get(next2, 0) >= 1:
            new_counts = tile_counts.copy()
            new_counts[first_tile] -= 1
            new_counts[next1] -= 1
            new_counts[next2] -= 1

            # Clean up zero counts
            for t in [first_tile, next1, next2]:
                if new_counts.get(t, 0) == 0 and t in new_counts:
                    del new_counts[t]

            sub_results = find_groups(new_counts, num_groups - 1, memo)
            for sub in sub_results:
                group = Group('straight', [first_tile, next1, next2], is_call=False)
                results.append([group] + sub)

    memo[key] = results
    return results


# =============================================================================
# MAIN INTERFACE
# =============================================================================

def analyze_hand(input_str: str) -> Dict:
    """
    Main function to analyze a mahjong hand.
    Returns a dictionary with validation results and explanations.
    """
    result = {
        'input': input_str,
        'is_valid': False,
        'error': '',
        'parsed': None,
        'explanations': []
    }

    # Parse the hand
    parsed, error = parse_hand(input_str)
    if parsed is None:
        result['error'] = error
        return result

    result['parsed'] = parsed

    # Validate the hand
    is_valid, error = validate_hand(parsed)
    if not is_valid:
        result['error'] = error
        return result

    result['is_valid'] = True

    # Find all explanations
    explanations = find_all_explanations(parsed)
    result['explanations'] = explanations

    if not explanations:
        result['error'] = "No valid winning pattern found"
        result['is_valid'] = False

    return result


def format_result(result: Dict, show_scoring: bool = False) -> str:
    """Format analysis result for display."""
    lines = []
    lines.append(f"Input: {result['input']}")
    lines.append(f"Valid: {result['is_valid']}")

    if result['error']:
        lines.append(f"Error: {result['error']}")

    if result['parsed']:
        p = result['parsed']
        lines.append(f"Format: {p.format_type}")
        lines.append(f"Calls: {p.calls}")
        lines.append(f"Hand tiles: {p.hand_tiles}")
        lines.append(f"Winning tile: {p.winning_tile} ({'self-drawn' if p.is_self_drawn else 'ron'})")
        if p.additional_notes:
            lines.append(f"Additional notes: {p.additional_notes}")

    if result['explanations']:
        lines.append(f"\nExplanations ({len(result['explanations'])} found):")
        for exp in result['explanations']:
            lines.append(f"  {exp}")

        # Show scoring if requested
        if show_scoring:
            try:
                from fan import score_hand, format_scoring_result
                lines.append(f"\n--- Scoring ---")
                for i, exp in enumerate(result['explanations'], 1):
                    score_result = score_hand(exp)
                    lines.append(f"\nExplanation {i} ({exp.pattern_type}):")
                    lines.append(format_scoring_result(score_result, 'c'))
            except ImportError:
                lines.append("\n(Scoring module not available)")

    return '\n'.join(lines)


# =============================================================================
# INTERACTIVE MODE
# =============================================================================

def interactive_mode(show_scoring: bool = True):
    """Run the hand analyzer in interactive mode."""
    print("=" * 60)
    print("Mahjong Hand Analyzer (IMR Calculator)")
    print("=" * 60)
    print("\nSupported formats:")
    print("  English: b/c/d = bamboo/character/dot, E/S/W/N/R/G/Wh = honors")
    print("  Japanese: s/p/m = bamboo/dot/character, 1z-7z = honors")
    print("\nFormat: [calls]hand_tiles + winning_tile[*] +notes")
    print("  * after winning tile = self-drawn (tsumo)")
    print("  * after call = concealed quad")
    print("  +LT = Last Tile Win, +AQ = After Quad, +RQ = Robbing Quad")
    print("\nExample: [RRRR*][123b]4567899b + 9b* +LT")
    print("Enter 'quit' or 'q' to exit.\n")

    while True:
        try:
            hand_input = input("Enter hand: ").strip()
            if hand_input.lower() in ('quit', 'q', 'exit'):
                print("Goodbye!")
                break
            if not hand_input:
                continue

            result = analyze_hand(hand_input)
            print("\n" + format_result(result, show_scoring=show_scoring) + "\n")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")


def run_tests():
    """Run the test suite."""
    test_hands = [
        # Original example - quad of Red dragons (15 tiles: 4+3+7+1=15 with 1 quad)
        ("[RRRR*][123b]4567899b + 9b* +LT", "Valid hand with concealed quad"),

        # Same hand, expanded notation
        ("[RRRR*][1b2b3b]4b5b6b7b8b9b9b + 9b* +LT", "Same hand, expanded notation"),

        # Seven pairs (14 tiles: 13+1)
        ("1122334455667b + 7b*", "Seven pairs hand"),

        # Simple winning hand - all concealed (14 tiles: 3+3+3+3+2)
        ("123b456b789b1112c + 2c*", "Simple hand with triplet"),

        # All triplets (14 tiles: 9 from calls + 5 hand)
        ("[111b][222b][333b]4445b + 5b", "All triplets hand"),

        # Invalid - 5 copies of same tile (1111b + 11b + 1b = 7 copies of 1b)
        ("[1111b*]2345678911b + 1b", "Invalid: 5 copies of 1b"),

        # Japanese format - valid hand (5z=White dragon) (15 tiles with 1 quad)
        ("[5555z*][123s]4567899s + 9s* +LT", "Japanese format with white dragon quad"),
        # Japanese format - simple hand (14 tiles: 3+3+3+3+2)
        ("123s456s789s1112m + 2m*", "Japanese format simple hand"),

        # Thirteen Orphans (14 tiles: 13 unique + 1 pair)
        ("19b19c19dESWNWhGR + R*", "Thirteen Orphans"),

        # Mixed suit hand (14 tiles: 3+3+3+3+2)
        ("123b456c789dWWEE + E", "Mixed suit hand"),

        # Invalid - wrong call format
        ("[124b]111222333b + 3b", "Invalid: non-consecutive straight"),

        # Two concealed quads (16 tiles: 8 from quads + 8 hand)
        ("[1111b*][2222b*]3334455b + 5b*", "Two concealed quads"),

        # New test cases from claude2.txt
        # Test 1: 678b33344455cRR + 5c
        # Expected: 2 explanations - SSSSp and TTTSp
        ("678b33344455cRR + 5c", "SSSSp and TTTSp patterns"),

        # Test 2: 3344556677899d + 8d (fixed: original had 78899, should be 77899)
        # Expected: 4 explanations - SSSSp (3) and Seven Pairs
        ("3344556677899d + 8d", "Multiple SSSSp and Seven Pairs"),

        # Test 3: 2222333344455c + 4c
        # Expected: 4 explanations - TTTSp, SSSSp(2) and Seven Pairs
        ("2222333344455c + 4c", "TTTSp, SSSSp, Seven Pairs"),

        # Test 4: 3355b2288c23445d + 6d
        # Expected: False win (bluff) - no valid pattern
        ("3355b2288c23445d + 6d", "Invalid: False win (bluff) - 4 pairs and 2 groups cannot win"),
    ]

    passed = 0
    failed = 0
    for hand, description in test_hands:
        print("=" * 60)
        print(f"Test: {description}")
        result = analyze_hand(hand)
        print(format_result(result))
        if "Invalid" in description:
            if not result['is_valid']:
                passed += 1
                print("[PASS - Expected invalid]")
            else:
                failed += 1
                print("[FAIL - Should be invalid]")
        else:
            if result['is_valid'] and result['explanations']:
                passed += 1
                print("[PASS]")
            else:
                failed += 1
                print("[FAIL - Should be valid]")
        print()

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            run_tests()
        elif sys.argv[1] == "--interactive" or sys.argv[1] == "-i":
            interactive_mode(show_scoring=True)
        elif sys.argv[1] == "--no-score":
            interactive_mode(show_scoring=False)
        elif sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print("IMR Mahjong Hand Analyzer")
            print("Usage:")
            print("  python main.py                    Interactive mode with scoring")
            print("  python main.py --test             Run test suite")
            print("  python main.py --no-score         Interactive mode without scoring")
            print("  python main.py <hand>             Analyze a single hand")
            print("  python main.py --score <hand>     Analyze with scoring")
        elif sys.argv[1] == "--score":
            hand_input = ' '.join(sys.argv[2:])
            result = analyze_hand(hand_input)
            print(format_result(result, show_scoring=True))
        else:
            # Treat as hand input (with scoring by default)
            hand_input = ' '.join(sys.argv[1:])
            result = analyze_hand(hand_input)
            print(format_result(result, show_scoring=True))
    else:
        # Default to interactive mode with scoring
        interactive_mode(show_scoring=True)
