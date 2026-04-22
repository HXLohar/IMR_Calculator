"""IMR Mahjong Calculator — Graphical User Interface"""
import tkinter as tk
from tkinter import messagebox
import csv
import os
import sys
from collections import Counter
from typing import Optional, List, Dict, Set

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from main import parse_hand, validate_hand, find_all_explanations, Tile, TileType, CallType
from fan import score_hand

# ---------------------------------------------------------------------------
# Layout / dimension constants
# ---------------------------------------------------------------------------
LIB_W, LIB_H     = 44, 58   # tile image size in library
HTILE_W, HTILE_H  = 36, 50   # tile image size in hand display (smaller to fit 18)

BADGE_R   = 7                 # badge half-size (rectangle)
BADGE_PAD = 1
CELL_W = LIB_W + BADGE_R + BADGE_PAD * 2   # 53
CELL_H = LIB_H + BADGE_R + BADGE_PAD * 2   # 67
STEP   = CELL_W + 2                          # 55 – x-step between lib tiles

WIN_W   = 1280
WIN_H   = 720
LEFT_W  = 515
RIGHT_X = 520    # LEFT_W + 5px divider
RIGHT_W = WIN_W - RIGHT_X    # 760

IMG_DIR  = os.path.join(BASE_DIR, "images", "tiles")
DATA_DIR = os.path.join(BASE_DIR, "data")

BAMBOO_ROW = [f"{i}b" for i in range(1, 10)]
DOT_ROW    = [f"{i}d" for i in range(1, 10)]
CHAR_ROW   = [f"{i}c" for i in range(1, 10)]
HONOR_ROW  = ["E", "S", "W", "N", "R", "G", "Wh"]
TILE_ROWS  = [BAMBOO_ROW, DOT_ROW, CHAR_ROW, HONOR_ROW]

# Canonical sort order for "tiles" hand group
_TILE_ORDER: Dict[str, tuple] = {}
for _ri, _row in enumerate(TILE_ROWS):
    for _ci, _k in enumerate(_row):
        _TILE_ORDER[_k] = (_ri, _ci)

# Extra note flags appended to hand string for each option
OPT_NOTES: Dict[int, str] = {
    41: "+BOH", 42: "+BOE", 43: "+EW",
    44: "+DW",  45: "+AQ",  46: "+RQ",
    47: "+GTM", 49: "",
}

# Option button grid: 4 equal columns, 3 rows
_OPT_CW, _OPT_GX = 183, 4   # column width, x-gap
_OPT_RH, _OPT_GY = 36,  4   # row height,   y-gap
_OC = lambda c: c * (_OPT_CW + _OPT_GX)   # column x offset
_OR = lambda r: r * (_OPT_RH + _OPT_GY)   # row y offset

OPT_LAYOUT = [
    (41, _OC(0), _OR(0), _OPT_CW, _OPT_RH),            # 天和
    (42, _OC(1), _OR(0), _OPT_CW, _OPT_RH),            # 地和
    (43, _OC(2), _OR(0), _OPT_CW, _OPT_RH),            # 天聽
    (44, _OC(3), _OR(0), _OPT_CW, _OPT_RH),            # 報聽
    (45, _OC(0), _OR(1), _OPT_CW, _OPT_RH),            # 槓上開花
    (46, _OC(1), _OR(1), _OPT_CW, _OPT_RH),            # 搶槓和
    (47, _OC(2), _OR(1), _OPT_CW, _OPT_RH),            # 海底撈月
    (49, _OC(3), _OR(1), _OPT_CW, 2*_OPT_RH+_OPT_GY), # 自摸 (tall, spans rows 1+2)
]
OPT_INNER_W = 4 * _OPT_CW + 3 * _OPT_GX   # 744
OPT_INNER_H = 2 * (_OPT_RH + _OPT_GY) + _OPT_RH   # 116

# ---------------------------------------------------------------------------
# Tile key <-> Tile object
# ---------------------------------------------------------------------------
_WIND_K2V   = {"E": 1, "S": 2, "W": 3, "N": 4}
_DRAGON_K2V = {"Wh": 1, "G": 2, "R": 3}
_WIND_V2K   = {v: k for k, v in _WIND_K2V.items()}
_DRAGON_V2K = {v: k for k, v in _DRAGON_K2V.items()}


def key_to_tile(key: str) -> Tile:
    if key[-1] == "b":  return Tile(TileType.BAMBOO,    int(key[:-1]))
    if key[-1] == "d":  return Tile(TileType.DOT,       int(key[:-1]))
    if key[-1] == "c":  return Tile(TileType.CHARACTER, int(key[:-1]))
    if key in _WIND_K2V:   return Tile(TileType.WIND,   _WIND_K2V[key])
    if key in _DRAGON_K2V: return Tile(TileType.DRAGON, _DRAGON_K2V[key])
    raise ValueError(f"Unknown tile key: {key}")


def tile_to_key(tile: Tile) -> str:
    if tile.tile_type == TileType.BAMBOO:    return f"{tile.value}b"
    if tile.tile_type == TileType.DOT:       return f"{tile.value}d"
    if tile.tile_type == TileType.CHARACTER: return f"{tile.value}c"
    if tile.tile_type == TileType.WIND:      return _WIND_V2K[tile.value]
    if tile.tile_type == TileType.DRAGON:    return _DRAGON_V2K[tile.value]
    raise ValueError(f"Unknown tile: {tile}")


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------
def _open_csv(filepath: str) -> List[Dict]:
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5", "latin-1"):
        try:
            with open(filepath, "r", encoding=enc, newline="") as f:
                rows = list(csv.DictReader(f))
            return rows
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    return []


def load_strings(filepath: str) -> Dict[int, Dict[str, str]]:
    out: Dict[int, Dict[str, str]] = {}
    for row in _open_csv(filepath):
        try:
            sid = int(row["string_id"])
            out[sid] = {"en": row.get("en", ""), "ct": row.get("ct", "")}
        except (KeyError, ValueError):
            pass
    return out


def load_options(filepath: str) -> List[Dict]:
    out = []
    for row in _open_csv(filepath):
        try:
            oid = int(row["id"])

            def _ids(s):
                return [int(x.strip()) for x in str(s).split(",")
                        if x.strip().lstrip("-").isdigit()]

            out.append({
                "id":        oid,
                "must_have": _ids(row.get("must_have", "")),
                "conflict":  _ids(row.get("conflict",  "")),
            })
        except (KeyError, ValueError):
            pass
    return out


# ---------------------------------------------------------------------------
# Image manager
# ---------------------------------------------------------------------------
class ImageManager:
    def __init__(self):
        self._pil:   Dict[tuple, "Image.Image"]       = {}
        self._photo: Dict[tuple, "ImageTk.PhotoImage"] = {}
        self.lang = "ct"

    def set_lang(self, lang: str):
        if lang != self.lang:
            self.lang = lang
            self._pil.clear()
            self._photo.clear()

    def _pil_for(self, key: str) -> Optional["Image.Image"]:
        ck = (key, self.lang)
        if ck in self._pil:
            return self._pil[ck]
        if not PIL_AVAILABLE:
            return None
        candidates = []
        if self.lang == "en":
            candidates.append(os.path.join(IMG_DIR, f"{key}_.png"))
        candidates.append(os.path.join(IMG_DIR, f"{key}.png"))
        for path in candidates:
            if os.path.isfile(path):
                try:
                    img = Image.open(path).convert("RGBA")
                    self._pil[ck] = img
                    return img
                except Exception:
                    pass
        return None

    def get(self, key: str, w: int = LIB_W, h: int = LIB_H
            ) -> Optional["ImageTk.PhotoImage"]:
        ck = (key, w, h, self.lang)
        if ck in self._photo:
            return self._photo[ck]
        pil = self._pil_for(key)
        if pil is None:
            return None
        photo = ImageTk.PhotoImage(pil.resize((w, h), Image.LANCZOS))
        self._photo[ck] = photo
        return photo


# ---------------------------------------------------------------------------
# Library TileCanvas
# ---------------------------------------------------------------------------
class TileCanvas(tk.Canvas):
    """One clickable tile cell in the library, with optional count badge."""

    def __init__(self, parent: tk.Widget, key: str, app: "IMRApp", **kwargs):
        super().__init__(parent, width=CELL_W, height=CELL_H,
                         bd=0, highlightthickness=0, cursor="hand2",
                         bg="#f0f0f0", **kwargs)
        self.key = key
        self.app = app
        self._img_ref = None
        self.bind("<Button-1>", lambda e: app.on_lib_left(key))
        self.bind("<Button-3>", lambda e: app.on_lib_right(key))
        self.refresh()

    def refresh(self):
        self.delete("all")
        count = self.app.lib_sel.get(self.key, 0)
        ox = BADGE_R + BADGE_PAD   # tile top-left inside canvas
        oy = BADGE_R + BADGE_PAD

        img = self.app.imgr.get(self.key, LIB_W, LIB_H)
        if img:
            self._img_ref = img
            self.create_image(ox, oy, image=img, anchor="nw")
        else:
            self.create_rectangle(ox, oy, ox + LIB_W, oy + LIB_H,
                                  fill="lightgray", outline="gray")
            self.create_text(ox + LIB_W // 2, oy + LIB_H // 2,
                             text=self.key, font=("Arial", 7))

        if self.app._hand_counts()[self.key] >= 4:
            _ns = 18   # nein icon size
            nein = self.app.imgr.get("nein", _ns, _ns)
            if nein:
                self._nein_ref = nein
                nx = ox + LIB_W - _ns
                ny = oy + LIB_H - _ns
                self.create_image(nx, ny, image=nein, anchor="nw")

        if count > 0:
            # Square badge: top-right corner of tile, fully within canvas
            r  = BADGE_R
            cx = CELL_W - r - 1   # right edge flush with canvas
            cy = r + 1            # top edge flush with canvas
            self.create_rectangle(cx - r, cy - r, cx + r, cy + r,
                                  fill="black", outline="white", width=1)
            self.create_text(cx, cy, text=str(count),
                             fill="white", font=("Arial", 8, "bold"))


# ---------------------------------------------------------------------------
# Manual input dialog
# ---------------------------------------------------------------------------
class ManualDialog(tk.Toplevel):
    def __init__(self, parent: "IMRApp"):
        super().__init__(parent)
        self.title(parent.s(11))
        self.resizable(False, False)
        self.grab_set()
        self.result: Optional[str] = None

        tk.Label(self, text="Hand string:").pack(padx=10, pady=(10, 2), anchor="w")
        self.entry = tk.Entry(self, width=55, font=("Courier", 11))
        self.entry.pack(padx=10, pady=2)
        self.entry.focus_set()

        hint = (
            "Format: [calls]hand_tiles + winning_tile[*] [+notes]\n"
            "Examples:\n"
            "  [RRRR*][123b]4567899b + 9b*\n"
            "  19b19c19dESWNWhGR + R*\n"
            "  1122334455667b + 7b*"
        )
        tk.Label(self, text=hint, font=("Courier", 8), justify="left",
                 fg="gray").pack(padx=10, pady=4, anchor="w")

        btn_row = tk.Frame(self)
        btn_row.pack(pady=(0, 10))
        tk.Button(btn_row, text="OK",     width=8, command=self._ok   ).pack(side="left", padx=5)
        tk.Button(btn_row, text="Cancel", width=8, command=self.destroy).pack(side="left", padx=5)
        self.entry.bind("<Return>", lambda e: self._ok())

    def _ok(self):
        self.result = self.entry.get().strip()
        self.destroy()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sort_tile_keys(keys: List[str]) -> List[str]:
    return sorted(keys, key=lambda k: _TILE_ORDER.get(k, (99, 99)))


def _first_tiles_idx(hand_groups: List[Dict]) -> int:
    """Return index of the first 'tiles' group, or len(hand_groups) if none."""
    for i, g in enumerate(hand_groups):
        if g["type"] == "tiles":
            return i
    return len(hand_groups)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------
class IMRApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("IMR Mahjong Calculator")
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.resizable(False, False)
        self.configure(bg="#f0f0f0")

        self.strings  = load_strings(os.path.join(DATA_DIR, "lang.csv"))
        self.opt_list = load_options(os.path.join(DATA_DIR, "additional_options.csv"))
        self.opt_map  = {o["id"]: o for o in self.opt_list}

        self.lang = "ct"
        self.imgr = ImageManager()
        self.imgr.set_lang(self.lang)

        self.lib_sel:     Dict[str, int] = {}
        self.hand_groups: List[Dict]      = []
        self.winning_key: Optional[str]   = None
        self.is_self_drawn = False
        self.active_opts:  Set[int]        = set()
        self._score_is_placeholder    = True
        self._last_score_result       = None   # ScoringResult – for lang-switch redisplay
        self._last_outs_results       = None   # list – for lang-switch redisplay
        self._last_outs_is_concealed  = False
        # tk vars – created here because Tk window already exists after super()
        self._outs_min_var    = tk.IntVar(value=150)
        self._outs_bypass_var = tk.BooleanVar(value=True)
        self._last_outs_drawing_dead: list = []

        self._build()
        self._refresh_all()

    # ------------------------------------------------------------------
    def s(self, sid: int) -> str:
        d = self.strings.get(sid, {})
        return d.get(self.lang, d.get("en", f"[{sid}]"))

    # ------------------------------------------------------------------ counts
    def _hand_counts(self) -> Counter:
        c: Counter = Counter()
        for g in self.hand_groups:
            for k in g["keys"]:
                c[k] += 1
        if self.winning_key:
            c[self.winning_key] += 1
        return c

    def _total_counts(self) -> Counter:
        c = self._hand_counts()
        for k, v in self.lib_sel.items():
            c[k] += v
        return c

    # ------------------------------------------------------------------ library events
    def on_lib_left(self, key: str):
        if self._total_counts()[key] < 4:
            self.lib_sel[key] = self.lib_sel.get(key, 0) + 1
            self._refresh_lib_tile(key)

    def on_lib_right(self, key: str):
        if self.lib_sel.get(key, 0) > 0:
            self.lib_sel[key] -= 1
            self._refresh_lib_tile(key)

    def _selected_keys(self) -> List[str]:
        keys = []
        for row in TILE_ROWS:
            for k in row:
                keys.extend([k] * self.lib_sel.get(k, 0))
        return keys

    def _clear_lib(self):
        self.lib_sel.clear()
        for row in TILE_ROWS:
            for k in row:
                self._refresh_lib_tile(k)

    def _count_calls(self) -> int:
        return sum(1 for g in self.hand_groups
                   if g["type"] in ("straight", "triplet", "quad", "concealed_quad"))

    def _count_hand_tiles(self) -> int:
        for g in self.hand_groups:
            if g["type"] == "tiles":
                return len(g["keys"])
        return 0

    def _check_tile_limits_for_call(self) -> Optional[int]:
        cur_calls = self._count_calls()
        cur_hand  = self._count_hand_tiles()
        new_calls = cur_calls + 1
        if cur_hand > 13 - 3 * new_calls:
            return 112
        if new_calls > 4 - cur_hand // 3:
            return 113
        return None

    def _check_tile_limits_for_hand(self, adding: int) -> Optional[int]:
        cur_calls = self._count_calls()
        cur_hand  = self._count_hand_tiles()
        if cur_hand + adding > 13 - 3 * cur_calls:
            return 112
        return None

    # ------------------------------------------------------------------ action buttons
    def on_action(self, action: str):
        self._invalidate_score()
        sel = self._selected_keys()

        if action == "manual":
            dlg = ManualDialog(self)
            self.wait_window(dlg)
            if dlg.result:
                self._load_string(dlg.result)
            return

        if action == "hand":
            if not sel:
                messagebox.showwarning("", self.s(110))
                return
            err = self._check_tile_limits_for_hand(len(sel))
            if err:
                messagebox.showwarning("", self.s(err))
                self._clear_lib()
                return
            ti = _first_tiles_idx(self.hand_groups)
            if ti == len(self.hand_groups):
                self.hand_groups.append({"type": "tiles", "keys": []})
            self.hand_groups[ti]["keys"].extend(sel)
            self.hand_groups[ti]["keys"] = _sort_tile_keys(self.hand_groups[ti]["keys"])
            self._clear_lib()
            self._refresh_hand()
            return

        if action == "winning":
            if len(sel) != 1:
                messagebox.showwarning("", self.s(114))
                return
            self.winning_key = sel[0]
            self._clear_lib()
            self._refresh_hand()
            return

        # --- call: auto-detect straight / triplet / quad ---
        if action == "call":
            call_type = None
            if len(sel) == 3:
                if sel[0] == sel[1] == sel[2]:
                    call_type = "triplet"
                else:
                    ts = sorted([key_to_tile(k) for k in sel])
                    if (not ts[0].is_honor() and
                            ts[0].tile_type == ts[1].tile_type == ts[2].tile_type and
                            ts[1].value == ts[0].value + 1 and
                            ts[2].value == ts[0].value + 2):
                        call_type = "straight"
            elif len(sel) == 4:
                if sel[0] == sel[1] == sel[2] == sel[3]:
                    call_type = "quad"

            if call_type is None:
                messagebox.showwarning("", self.s(110))
                self._clear_lib()
                return
            err = self._check_tile_limits_for_call()
            if err:
                messagebox.showwarning("", self.s(err))
                self._clear_lib()
                return
            ins = _first_tiles_idx(self.hand_groups)
            self.hand_groups.insert(ins, {"type": call_type, "keys": list(sel)})
            self._clear_lib()
            self._refresh_hand()
            return

        # --- concealed quad ---
        if action == "concealed_quad":
            if len(sel) != 4 or not (sel[0] == sel[1] == sel[2] == sel[3]):
                messagebox.showwarning("", self.s(111))
                self._clear_lib()
                return
            err = self._check_tile_limits_for_call()
            if err:
                messagebox.showwarning("", self.s(err))
                self._clear_lib()
                return
            ins = _first_tiles_idx(self.hand_groups)
            self.hand_groups.insert(ins, {"type": "concealed_quad", "keys": list(sel)})
            self._clear_lib()
            self._refresh_hand()
            return

    # ------------------------------------------------------------------ hand click events
    def on_hand_click(self, gi: int, ti: int = -1):
        self._invalidate_score()
        grp = self.hand_groups[gi]
        if grp["type"] == "tiles" and ti >= 0:
            grp["keys"].pop(ti)
            if not grp["keys"]:
                self.hand_groups.pop(gi)
        else:
            self.hand_groups.pop(gi)
        self._refresh_hand()
        for row in TILE_ROWS:
            for k in row:
                self._refresh_lib_tile(k)

    def on_winning_click(self):
        self._invalidate_score()
        self.winning_key = None
        self._refresh_hand()
        for row in TILE_ROWS:
            for k in row:
                self._refresh_lib_tile(k)

    # ------------------------------------------------------------------ option toggles
    def on_option_toggle(self, oid: int):
        self._invalidate_score()
        if oid in self.active_opts:
            self.active_opts.discard(oid)
        else:
            self.active_opts.add(oid)
            opt = self.opt_map.get(oid, {})
            for mh in opt.get("must_have", []):
                self.active_opts.add(mh)
            for cf in opt.get("conflict", []):
                self.active_opts.discard(cf)
        self.is_self_drawn = 49 in self.active_opts
        self._refresh_opts()
        self._refresh_hand()

    # ------------------------------------------------------------------ hand string
    def _build_hand_str(self) -> str:
        parts = []
        for g in self.hand_groups:
            tile_s = "".join(g["keys"])
            t = g["type"]
            if t == "concealed_quad":
                parts.append(f"[{tile_s}*]")
            elif t in ("straight", "triplet", "quad"):
                parts.append(f"[{tile_s}]")
            else:
                parts.append(tile_s)
        if not self.winning_key:
            return ""
        win = self.winning_key + ("*" if self.is_self_drawn else "")
        result = "".join(parts) + " + " + win
        notes = sorted({OPT_NOTES[o] for o in self.active_opts if OPT_NOTES.get(o)})
        if notes:
            result += " " + " ".join(notes)
        return result

    # ------------------------------------------------------------------ manual input
    def _load_string(self, hand_str: str):
        parsed, err = parse_hand(hand_str)
        if err or parsed is None:
            messagebox.showerror(self.s(121), err or "Parse error")
            return

        self.hand_groups.clear()
        self.lib_sel.clear()
        self.active_opts.clear()
        self.winning_key = None

        type_map = {
            CallType.STRAIGHT:       "straight",
            CallType.TRIPLET:        "triplet",
            CallType.QUAD:           "quad",
            CallType.CONCEALED_QUAD: "concealed_quad",
        }
        for call in parsed.calls:
            keys = [tile_to_key(t) for t in call.tiles]
            self.hand_groups.append({"type": type_map[call.call_type], "keys": keys})

        if parsed.hand_tiles:
            self.hand_groups.append({
                "type": "tiles",
                "keys": _sort_tile_keys([tile_to_key(t) for t in parsed.hand_tiles]),
            })

        self.winning_key   = tile_to_key(parsed.winning_tile)
        self.is_self_drawn = parsed.is_self_drawn

        notes = parsed.additional_notes.upper()
        if "+BOH" in notes: self.active_opts.add(41)
        if "+BOE" in notes: self.active_opts.add(42)
        if "+EW"  in notes: self.active_opts.add(43)
        if "+DW"  in notes: self.active_opts.add(44)
        if "+AQ"  in notes: self.active_opts.add(45)
        if "+RQ"  in notes: self.active_opts.add(46)
        if "+GTM" in notes or "+LT" in notes: self.active_opts.add(47)
        if self.is_self_drawn:               self.active_opts.add(49)

        self._refresh_all()

    # ------------------------------------------------------------------ calculate
    def on_calculate(self):
        if not self.winning_key:
            self._show_score_msg(self.s(121), "red")
            return
        hand_str = self._build_hand_str()
        if not hand_str:
            return
        parsed, err = parse_hand(hand_str)
        if err or parsed is None:
            self._show_score_msg(f"{self.s(121)}: {err}", "red")
            return
        ok, val_err = validate_hand(parsed)
        if not ok:
            self._show_score_msg(f"{self.s(121)}: {val_err}", "red")
            return
        exps = find_all_explanations(parsed)
        if not exps:
            self._show_score_msg(self.s(121), "red")
            return

        best, best_score = None, -1
        for exp in exps:
            r = score_hand(exp)
            if r.total_score > best_score:
                best_score, best = r.total_score, r
        self._display_score(best)

    def on_calculate_outs(self):
        saved_winning    = self.winning_key
        saved_opts       = set(self.active_opts)
        saved_self_drawn = self.is_self_drawn

        hand_counts: Counter = Counter()
        for g in self.hand_groups:
            for k in g["keys"]:
                hand_counts[k] += 1

        is_concealed = not any(g["type"] in ("straight", "triplet", "quad")
                               for g in self.hand_groups)

        results = []
        drawing_dead = []
        all_keys = [k for row in TILE_ROWS for k in row]

        for tile_key in all_keys:
            remaining = 4 - hand_counts[tile_key]
            if remaining <= 0:
                # Check if this tile would complete a valid hand (drawing dead)
                self.winning_key = tile_key
                hs = self._build_hand_str()
                if hs:
                    p_dd, e_dd = parse_hand(hs)
                    if not e_dd and p_dd:
                        _, err_dd = validate_hand(p_dd)
                        if 'Drawing dead' in err_dd and find_all_explanations(p_dd):
                            drawing_dead.append(tile_key)
                continue

            self.winning_key = tile_key

            # Discard win
            self.active_opts   = saved_opts & {43, 44}
            self.is_self_drawn = False
            hs = self._build_hand_str()
            score_discard = None
            if hs:
                p2, e2 = parse_hand(hs)
                if not e2 and p2:
                    ok2, _ = validate_hand(p2)
                    if ok2:
                        exps2 = find_all_explanations(p2)
                        if exps2:
                            score_discard = max(
                                (score_hand(ex) for ex in exps2),
                                key=lambda r: r.total_score)

            # Self-drawn win
            self.active_opts   = (saved_opts & {43, 44}) | {49}
            self.is_self_drawn = True
            hs2 = self._build_hand_str()
            score_self = None
            if hs2:
                p3, e3 = parse_hand(hs2)
                if not e3 and p3:
                    ok3, _ = validate_hand(p3)
                    if ok3:
                        exps3 = find_all_explanations(p3)
                        if exps3:
                            score_self = max(
                                (score_hand(ex) for ex in exps3),
                                key=lambda r: r.total_score)

            if score_discard is not None or score_self is not None:
                results.append((tile_key, remaining, score_discard, score_self))

        self.winning_key   = saved_winning
        self.active_opts   = saved_opts
        self.is_self_drawn = saved_self_drawn

        self._display_outs(results, is_concealed, drawing_dead)

    def on_reset(self):
        self.lib_sel.clear()
        self.hand_groups.clear()
        self.winning_key   = None
        self.is_self_drawn = False
        self.active_opts.clear()
        self._refresh_all()
        self._show_score_msg(self.s(62), "gray")

    # ==================================================================
    # Build UI
    # ==================================================================
    def _build(self):
        BG = "#f0f0f0"
        self.configure(bg=BG)

        self._left = tk.Frame(self, bg=BG, width=LEFT_W, height=WIN_H)
        self._left.place(x=0, y=0)

        tk.Frame(self, bg="#bbbbbb", width=5, height=WIN_H).place(x=LEFT_W, y=0)

        self._right = tk.Frame(self, bg=BG, width=RIGHT_W, height=WIN_H)
        self._right.place(x=RIGHT_X, y=0)

        self._build_left()
        self._build_right()

    # ------------------------------------------------------------------
    def _build_left(self):
        p  = self._left
        BG = "#f0f0f0"

        self._lbl_tiles = tk.Label(p, text=self.s(10),
                                    font=("Arial", 11, "bold"), bg=BG)
        self._lbl_tiles.place(x=8, y=10)

        self._btn_manual = tk.Button(p, text=self.s(11), relief="raised", bd=2,
                                      command=lambda: self.on_action("manual"))
        self._btn_manual.place(x=310, y=6, width=170, height=30)

        row_y = [48, 120, 192, 264]
        self._tile_widgets: Dict[str, TileCanvas] = {}
        for ri, row in enumerate(TILE_ROWS):
            ry = row_y[ri]
            for ci, key in enumerate(row):
                tc = TileCanvas(p, key, self)
                tc.place(x=8 + ci * STEP, y=ry)
                self._tile_widgets[key] = tc

    # ------------------------------------------------------------------
    def _build_right(self):
        p  = self._right
        BG = "#f0f0f0"

        # Language button — top-right, spans both action rows
        _LANG_W = 70
        _LANG_H = 70   # spans y=6..76 (both action rows)
        self._btn_lang = tk.Button(p, text="\u6587/A", font=("Arial", 11, "bold"),
                                   command=self._show_lang_menu)
        self._btn_lang.place(x=RIGHT_W - _LANG_W - 2, y=6, width=_LANG_W, height=_LANG_H)

        # Action buttons: 2×2 grid in remaining width
        _avail = RIGHT_W - 4 - _LANG_W - 4   # subtract lang btn + gaps
        _bw  = _avail // 2
        _bw2 = _avail - _bw - 2
        btn_defs = [
            (20, "call",          0,       6, _bw,  32),
            (21, "concealed_quad",_bw + 2, 6, _bw2, 32),
            (22, "winning",       0,      44, _bw,  32),
            (23, "hand",          _bw + 2,44, _bw2, 32),
        ]
        self._action_btns: Dict[str, tk.Button] = {}
        for sid, act, bx, by, bw, bh in btn_defs:
            btn = tk.Button(p, text=self.s(sid),
                            command=lambda a=act: self.on_action(a))
            btn.place(x=bx, y=by, width=bw, height=bh)
            self._action_btns[act] = btn

        # Hand display LabelFrame
        self._hand_lf = tk.LabelFrame(p, text=self.s(30), font=("Arial", 9),
                                       bg=BG, padx=2, pady=2)
        self._hand_lf.place(x=0, y=84, width=RIGHT_W - 4, height=128)

        self._hand_canvas = tk.Canvas(self._hand_lf, height=80, bg="white",
                                       highlightthickness=1, highlightbackground="#aaa")
        self._hand_canvas.pack(side="top", fill="both", expand=True)

        self._hand_inner = tk.Frame(self._hand_canvas, bg="white")
        self._hand_window = self._hand_canvas.create_window(0, 0, anchor="nw",
                                                             window=self._hand_inner)
        self._hand_inner.bind("<Configure>", lambda e: self._center_hand())
        self._hand_canvas.bind("<Configure>", lambda e: self._center_hand())

        # Additional options LabelFrame
        self._opt_lf = tk.LabelFrame(p, text=self.s(40), font=("Arial", 9),
                                      bg=BG, padx=4, pady=4)
        self._opt_lf.place(x=0, y=220, width=RIGHT_W - 4, height=OPT_INNER_H + 36)

        self._opt_inner = tk.Frame(self._opt_lf, bg=BG,
                                    width=OPT_INNER_W, height=OPT_INNER_H)
        self._opt_inner.pack(anchor="w")
        self._opt_inner.pack_propagate(False)

        self._opt_btns: Dict[int, tk.Button] = {}
        self._build_options()

        # Calculate buttons: Score (65%) | Outs (~32%) | Settings (3%)
        _SETS_W  = 30
        _score_w = int((RIGHT_W - 4) * 0.65)
        _outs_w  = (RIGHT_W - 4) - _score_w - 2 - _SETS_W - 2
        self._btn_calc = tk.Button(p, text=self.s(60),
                                    font=("Arial", 14, "bold"),
                                    bg="#4a90d9", fg="white", relief="raised", bd=2,
                                    command=self.on_calculate)
        self._btn_calc.place(x=0, y=376, width=_score_w, height=40)

        self._btn_outs = tk.Button(p, text=self.s(61),
                                    font=("Arial", 10, "bold"),
                                    bg="#5ba85e", fg="white", relief="raised", bd=2,
                                    command=self.on_calculate_outs)
        self._btn_outs.place(x=_score_w + 2, y=376, width=_outs_w, height=40)

        self._btn_outs_cfg = tk.Button(p, text="...", font=("Arial", 9),
                                        bg="#5ba85e", fg="white", relief="raised", bd=2,
                                        command=self._show_outs_settings)
        self._btn_outs_cfg.place(x=_score_w + 2 + _outs_w + 2, y=376,
                                  width=_SETS_W, height=40)

        # Score area
        self._score_outer = tk.Frame(p, bg="#f8f8f8", relief="sunken", bd=1)
        self._score_outer.place(x=0, y=424, width=RIGHT_W - 4, height=248)
        self._score_inner = tk.Frame(self._score_outer, bg="#f8f8f8")
        self._score_inner.pack(fill="both", expand=True)
        tk.Label(self._score_inner, text=self.s(62), fg="gray",
                 bg="#f8f8f8").pack(padx=6, pady=6)

        # Reset button
        self._btn_reset = tk.Button(p, text=self.s(12), command=self.on_reset)
        self._btn_reset.place(x=RIGHT_W - 108, y=682, width=104, height=30)

    def _build_options(self):
        p  = self._opt_inner
        BG = "#f0f0f0"
        for oid, ox, oy, ow, oh in OPT_LAYOUT:
            if oid == 49:
                font = ("Arial", 13, "bold")
            else:
                font = ("Arial", 10)
            btn = tk.Button(p, text=self.s(oid), font=font,
                            relief="raised", bd=2, bg=BG,
                            wraplength=ow - 8, justify="center",
                            command=lambda o=oid: self.on_option_toggle(o))
            btn.place(x=ox, y=oy, width=ow, height=oh)
            self._opt_btns[oid] = btn

    # ==================================================================
    # Refresh helpers
    # ==================================================================
    def _refresh_all(self):
        self._refresh_lib()
        self._refresh_hand()
        self._refresh_opts()

    def _refresh_lib(self):
        for tc in self._tile_widgets.values():
            tc.refresh()

    def _refresh_lib_tile(self, key: str):
        if key in self._tile_widgets:
            self._tile_widgets[key].refresh()

    def _center_hand(self):
        self._hand_inner.update_idletasks()
        cw = self._hand_canvas.winfo_width()
        ch = self._hand_canvas.winfo_height()
        iw = self._hand_inner.winfo_reqwidth()
        ih = self._hand_inner.winfo_reqheight()
        x = max(0, (cw - iw) // 2)
        y = max(0, (ch - ih) // 2)
        self._hand_canvas.coords(self._hand_window, x, y)
        self._hand_canvas.configure(scrollregion=(0, 0, max(cw, iw), max(ch, ih)))

    def _refresh_hand(self):
        for w in self._hand_inner.winfo_children():
            w.destroy()

        for gi, grp in enumerate(self.hand_groups):
            self._draw_group(gi, grp)

        if self.hand_groups:
            tk.Label(self._hand_inner, text=" + ",
                     font=("Arial", 12, "bold"), bg="white").pack(side="left", anchor="center")

            # Winning tile — fixed-size Canvas so ★ doesn't change layout height
            _tw, _th = HTILE_W + 2, HTILE_H + 2
            wc = tk.Canvas(self._hand_inner, width=_tw, height=_th,
                           bg="white", highlightthickness=0, cursor="hand2")
            wc.pack(side="left", padx=1, anchor="center")
            if self.winning_key:
                img = self.imgr.get(self.winning_key, HTILE_W, HTILE_H)
                if img:
                    wc._img = img
                    wc.create_image(1, 1, anchor="nw", image=img)
                else:
                    wc.create_rectangle(1, 1, _tw - 1, _th - 1, outline="gray")
                    wc.create_text(_tw // 2, _th // 2, text=self.winning_key,
                                   font=("Arial", 7))
                if self.is_self_drawn:
                    wc.create_text(_tw - 2, _th - 2, anchor="se", text="\u2605",
                                   font=("Arial", 7, "bold"), fill="red")
                wc.bind("<Button-1>", lambda e: self.on_winning_click())
            else:
                img = self.imgr.get("tile_back", HTILE_W, HTILE_H)
                if img:
                    wc._img = img
                    wc.create_image(1, 1, anchor="nw", image=img)
                else:
                    wc.create_rectangle(1, 1, _tw - 1, _th - 1,
                                        outline="#bbb", dash=(3, 3))
                    wc.create_text(_tw // 2, _th // 2, text="?",
                                   font=("Arial", 9), fill="gray")

        self._center_hand()

    def _draw_group(self, gi: int, grp: Dict):
        is_call = grp["type"] in ("straight", "triplet", "quad", "concealed_quad")
        gf = tk.Frame(self._hand_inner, bg="white")
        gf.pack(side="left", padx=1, anchor="center")

        tile_row = tk.Frame(gf, bg="white")
        tile_row.pack(side="top")

        if grp["type"] == "concealed_quad":
            # Display as [back][tile][tile][back]
            display_keys = ["tile_back", grp["keys"][0], grp["keys"][1], "tile_back"]
            for key in display_keys:
                img = self.imgr.get(key, HTILE_W, HTILE_H)
                lbl = tk.Label(tile_row, bg="white", cursor="hand2", relief="groove", bd=1)
                if img:
                    lbl.config(image=img)
                    lbl._img = img
                else:
                    lbl.config(text=key, width=3, height=2, font=("Arial", 7))
                lbl.pack(side="left", padx=0)
                lbl.bind("<Button-1>", lambda e, g=gi: self.on_hand_click(g))
        else:
            for ti, key in enumerate(grp["keys"]):
                img = self.imgr.get(key, HTILE_W, HTILE_H)
                lbl = tk.Label(tile_row, bg="white", cursor="hand2", relief="groove", bd=1)
                if img:
                    lbl.config(image=img)
                    lbl._img = img
                else:
                    lbl.config(text=key, width=3, height=2, font=("Arial", 7))
                lbl.pack(side="left", padx=0)

                if grp["type"] == "tiles":
                    lbl.bind("<Button-1>", lambda e, g=gi, t=ti: self.on_hand_click(g, t))
                else:
                    lbl.bind("<Button-1>", lambda e, g=gi: self.on_hand_click(g))

        if is_call:
            color = "#2244cc" if grp["type"] == "concealed_quad" else "#cc2222"
            tk.Frame(gf, height=3, bg=color).pack(side="top", fill="x")

    def _refresh_opts(self):
        for oid, btn in self._opt_btns.items():
            if oid in self.active_opts:
                btn.configure(relief="sunken", bg="#90ee90")
            else:
                btn.configure(relief="raised", bg="SystemButtonFace")

    # ==================================================================
    # Score display
    # ==================================================================
    def _show_score_msg(self, msg: str, color: str = "black"):
        self._score_is_placeholder = True
        for w in self._score_inner.winfo_children():
            w.destroy()
        tk.Label(self._score_inner, text=msg, fg=color, bg="#f8f8f8",
                 wraplength=700, justify="left").pack(padx=6, pady=6)

    def _fan_style(self, score: int, is_bold: bool):
        size  = 14 if score >= 3000 else 12 if score >= 1000 else 10 if score >= 300 else 9
        font  = ("Arial", size, "bold") if is_bold else ("Arial", size)
        color = "red" if score >= 3000 else "black"
        return font, color

    def _display_score(self, result):
        self._score_is_placeholder = False
        self._last_score_result    = result
        self._last_outs_results    = None
        for w in self._score_inner.winfo_children():
            w.destroy()

        if not result.achieved_fans:
            tk.Label(self._score_inner,
                     text="無番" if self.lang == "ct" else "No Fan",
                     bg="#f8f8f8").pack(padx=6, pady=6)
            return

        # Most important: highest score; tie → smallest fan id
        main_af = min(result.achieved_fans, key=lambda af: (-af.score, af.fan.id))

        grid = tk.Frame(self._score_inner, bg="#f8f8f8")
        grid.pack(fill="x", padx=6, pady=4)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        MAX_COLS = 2
        MAX_ROWS = 5
        row = col = 0
        for af in result.achieved_fans:
            if row >= MAX_ROWS:
                break
            name    = af.fan.name_c if self.lang == "ct" else af.fan.name_e
            is_bold = (af is main_af)
            font, color = self._fan_style(af.score, is_bold)
            tk.Label(grid, text=f"{name}  {af.score:,}",
                     font=font, fg=color, bg="#f8f8f8", anchor="w"
                     ).grid(row=row, column=col, sticky="ew", padx=4, pady=1)
            col += 1
            if col >= MAX_COLS:
                col = 0
                row += 1

        tk.Frame(self._score_inner, height=2, bg="#888").pack(fill="x", padx=6, pady=4)

        total_row = tk.Frame(self._score_inner, bg="#f8f8f8")
        total_row.pack(fill="x", padx=6)
        tk.Label(total_row, text=self.s(63),
                 font=("Arial", 13, "bold"), bg="#f8f8f8").pack(side="left")
        tk.Label(total_row, text=f"  {result.total_score:,}",
                 font=("Arial", 17, "bold"), fg="#003388",
                 bg="#f8f8f8").pack(side="left", padx=8)

    def _format_fan_breakdown(self, result) -> str:
        parts = []
        for af in result.achieved_fans:
            name = af.fan.name_c if self.lang == "ct" else af.fan.name_e
            if result.is_excellence:
                if af.is_main:
                    parts.append(f"[[{name}]] {af.score:,}")
                else:
                    parts.append(f"[{name}] {af.fan.value:,}/2")
            else:
                parts.append(f"[{name}] {af.score:,}")
        return " + ".join(parts)

    def _tile_key_display(self, key: str) -> str:
        _SUIT_SID  = {"b": 100, "d": 101, "c": 102}
        _HONOR_SID = {"E": 103, "S": 104, "W": 105, "N": 106,
                      "R": 107, "G": 108, "Wh": 109}
        if self.lang == "en":
            return key
        if key[-1] in _SUIT_SID:
            return key[:-1] + self.s(_SUIT_SID[key[-1]])
        return self.s(_HONOR_SID.get(key, 200))

    def _display_outs(self, results, is_concealed: bool = False, drawing_dead: list = None):
        self._score_is_placeholder   = False
        self._last_outs_results      = results
        self._last_outs_is_concealed = is_concealed
        self._last_outs_drawing_dead = drawing_dead or []
        self._last_score_result      = None
        for w in self._score_inner.winfo_children():
            w.destroy()

        if not results and not drawing_dead:
            tk.Label(self._score_inner, text=self.s(120), fg="gray",
                     font=("Arial", 11), bg="#f8f8f8").pack(padx=6, pady=6)
            return

        if not results and drawing_dead:
            # Pure drawing dead hand — skip the outs header/avg and go straight to display
            text_frame = tk.Frame(self._score_inner, bg="#f8f8f8")
            text_frame.pack(fill="both", expand=True, padx=4, pady=6, side="top")
            txt = tk.Text(text_frame, font=("Courier", 9), bg="#f8f8f8",
                          relief="flat", bd=0, wrap="word", state="disabled")
            txt.pack(side="left", fill="both", expand=True)
            txt.configure(state="normal")
            label = self.s(202)
            txt.insert("end", f"─── {label} ───\n")
            for tile_key in drawing_dead:
                txt.insert("end",
                    f"{self._tile_key_display(tile_key)} ×0  — 0 outs remaining\n")
            txt.configure(state="disabled")
            return

        min_pts     = self._outs_min_var.get()
        bypass_chsd = self._outs_bypass_var.get()

        def _self_valid(sr):
            if sr is None: return False
            if sr.total_score >= min_pts: return True
            return bypass_chsd and is_concealed

        def _disc_valid(sr):
            return sr is not None and sr.total_score >= min_pts

        total_outs = sum(
            r[1] for r in results
            if _self_valid(r[3]) or _disc_valid(r[2])
        )

        # --- compute weights first so avg is available before any widget is packed ---
        total_weight = 0
        weighted_sum = 0.0
        display_rows = []   # (tile_key, remaining, score_self, score_discard, sv, dv)
        for tile_key, remaining, score_discard, score_self in results:
            sv = _self_valid(score_self)
            dv = _disc_valid(score_discard)
            if not sv and not dv:
                continue
            display_rows.append((tile_key, remaining, score_self, score_discard, sv, dv))
            if sv:
                total_weight += remaining
                weighted_sum += remaining * score_self.total_score
            if dv:
                total_weight += remaining * 3
                weighted_sum += remaining * 3 * score_discard.total_score
        avg = int(weighted_sum / total_weight) if total_weight else 0

        # Header at top
        header = tk.Frame(self._score_inner, bg="#f8f8f8")
        header.pack(fill="x", padx=6, pady=(4, 2), side="top")
        tk.Label(header, text=f"{self.s(200)}: {total_outs} {self.s(201)}",
                 font=("Arial", 11, "bold"), bg="#f8f8f8").pack(side="left")

        # Avg row at BOTTOM — packed before text so it always gets space
        tk.Frame(self._score_inner, height=1, bg="#aaa").pack(
            fill="x", padx=6, pady=2, side="bottom")
        avg_row = tk.Frame(self._score_inner, bg="#f8f8f8")
        avg_row.pack(fill="x", padx=6, pady=(0, 4), side="bottom")
        tk.Label(avg_row, text=self.s(212),
                 font=("Arial", 10, "bold"), bg="#f8f8f8").pack(side="left")
        tk.Label(avg_row, text=f"  {avg:,}",
                 font=("Arial", 13, "bold"), fg="#003388", bg="#f8f8f8").pack(side="left")

        # Scrollable text fills the middle
        text_frame = tk.Frame(self._score_inner, bg="#f8f8f8")
        text_frame.pack(fill="both", expand=True, padx=4, pady=2, side="top")
        txt = tk.Text(text_frame, font=("Courier", 9), bg="#f8f8f8",
                      relief="flat", bd=0, wrap="word", state="disabled")
        vsb = tk.Scrollbar(text_frame, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)

        txt.configure(state="normal")
        for tile_key, remaining, score_self, score_discard, sv, dv in display_rows:
            txt.insert("end", f"{self._tile_key_display(tile_key)} ×{remaining}\n")
            if score_self is not None:
                invalid_tag = f" ({self.s(216)})" if not sv else ""
                txt.insert("end",
                    f"  {self.s(210)}: {score_self.total_score:,}{invalid_tag}\n"
                    f"  {self._format_fan_breakdown(score_self)}\n")
            if score_discard is not None:
                invalid_tag = f" ({self.s(216)})" if not dv else ""
                txt.insert("end",
                    f"  {self.s(211)}: {score_discard.total_score:,}{invalid_tag}\n"
                    f"  {self._format_fan_breakdown(score_discard)}\n")
        if drawing_dead:
            if display_rows:
                txt.insert("end", "\n")
            label = "Drawing Dead 振聴" if self.lang == "ct" else "Drawing Dead"
            txt.insert("end", f"─── {label} ───\n")
            for tile_key in drawing_dead:
                txt.insert("end",
                    f"{self._tile_key_display(tile_key)} ×0  — 0 outs remaining\n")
        txt.configure(state="disabled")

    def _invalidate_score(self):
        if not self._score_is_placeholder:
            self._last_score_result  = None
            self._last_outs_results  = None
            self._show_score_msg(self.s(62), "gray")

    def _show_lang_menu(self):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="English",      command=lambda: self._set_lang("en"))
        menu.add_command(label="\u7e41\u9ad4\u4e2d\u6587", command=lambda: self._set_lang("ct"))
        btn = self._btn_lang
        menu.post(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())

    def _show_outs_settings(self):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=f"── {self.s(213)} ──", state="disabled")
        for val in (0, 50, 150, 300, 500):
            menu.add_radiobutton(
                label=str(val),
                variable=self._outs_min_var,
                value=val,
            )
        menu.add_separator()
        menu.add_checkbutton(
            label=self.s(215),
            variable=self._outs_bypass_var,
        )
        btn = self._btn_outs_cfg
        menu.post(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())

    # ==================================================================
    # Language switching
    # ==================================================================
    def _set_lang(self, lang: str):
        if lang == self.lang:
            return
        self.lang = lang
        self.imgr.set_lang(lang)
        self._update_texts()
        self._refresh_all()
        if self._score_is_placeholder:
            self._show_score_msg(self.s(62), "gray")
        elif self._last_score_result is not None:
            self._display_score(self._last_score_result)
        elif self._last_outs_results is not None:
            self._display_outs(self._last_outs_results, self._last_outs_is_concealed, self._last_outs_drawing_dead)

    def _update_texts(self):
        self._lbl_tiles.configure(text=self.s(10))
        self._btn_manual.configure(text=self.s(11))
        self._btn_calc.configure(text=self.s(60))
        self._btn_outs.configure(text=self.s(61))
        self._btn_reset.configure(text=self.s(12))
        self._hand_lf.configure(text=self.s(30))
        self._opt_lf.configure(text=self.s(40))
        # lang button label stays "文/A" regardless of language

        act_sids = {
            "call":           20,
            "concealed_quad": 21,
            "winning":        22,
            "hand":           23,
        }
        for act, sid in act_sids.items():
            if act in self._action_btns:
                self._action_btns[act].configure(text=self.s(sid))

        for oid, btn in self._opt_btns.items():
            btn.configure(text=self.s(oid))


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = IMRApp()
    app.mainloop()
