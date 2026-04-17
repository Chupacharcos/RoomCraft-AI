"""
Room layout optimizer: Constructive placement + Group-based Simulated Annealing.

Architecture:
1. Constructive layout: place furniture semantically (wall-huggers → anchors → satellites)
2. SA refinement with group perturbation: move desk+chairs as a rigid unit
"""
import random
import math
import copy
from typing import List, Optional, Tuple, Dict

from core.scorer import score_layout, score_breakdown, get_highlight
from core.constraints import is_valid_placement, generate_soft_warnings
from core.geometry import (get_rotated_dims, compute_min_clearance_cm,
                           compute_light_coverage, count_conflicts)

# ── Semantic role definitions ─────────────────────────────────────────────────

# anchor_type → set of satellite types that should be placed adjacent to it
_ANCHOR_SATELLITES: Dict[str, set] = {
    'desk':         {'chair', 'chair_arm'},
    'dining_table': {'chair', 'chair_arm'},
    'bed_double':   {'nightstand'},
    'bed_single':   {'nightstand'},
}

# These types MUST hug a wall
_WALL_TYPES = {
    'bookshelf', 'shelf', 'wardrobe', 'wardrobe_sliding',
    'dresser', 'tv_unit',
}

# These types PREFER a wall (desk, beds)
_WALL_PREFER = {'desk', 'bed_double', 'bed_single'}

_ALL_SAT_TYPES = {t for sats in _ANCHOR_SATELLITES.values() for t in sats}


# ── Public entry point ────────────────────────────────────────────────────────

def optimize(room: dict, furniture_list: List[dict], n_layouts: int = 5,
             iterations: int = 10000, fixed_positions: dict = None) -> List[dict]:
    n_items = len(furniture_list)
    if n_items >= 7:
        iterations = min(iterations, 3000)
        n_attempts = 10
    elif n_items >= 4:
        iterations = min(iterations, 5000)
        n_attempts = 12
    else:
        n_attempts = 20

    groups = _build_groups(furniture_list)
    best_layouts = []

    for _ in range(n_attempts):
        layout = _constructive_layout(room, furniture_list, fixed_positions)
        if layout is None:
            continue

        current = layout
        current_score = score_layout(current, room)
        T = 80.0

        for _ in range(iterations):
            neighbor = _perturb(current, room, groups, fixed_positions)
            if neighbor is None or not is_valid_placement(neighbor, room):
                T *= 0.995
                continue
            neighbor_score = score_layout(neighbor, room)
            delta = neighbor_score - current_score
            if delta > 0 or random.random() < math.exp(delta / max(T, 0.01)):
                current = neighbor
                current_score = neighbor_score
            T *= 0.995

        best_layouts.append((current_score, copy.deepcopy(current)))

    best_layouts.sort(key=lambda x: x[0], reverse=True)
    unique_layouts = _deduplicate(best_layouts, n_layouts)

    results = []
    openings = room.get('openings', [])
    for rank, (score, layout) in enumerate(unique_layouts[:n_layouts], 1):
        breakdown = score_breakdown(layout, room)
        metrics = {
            'min_clearance_cm': compute_min_clearance_cm(layout),
            'light_coverage_pct': compute_light_coverage(
                layout, openings, room['width'], room['depth']),
            'conflicts': count_conflicts(layout, openings, room['width'], room['depth']),
        }
        results.append({
            'rank': rank,
            'score': round(score, 1),
            'highlight': get_highlight(breakdown),
            'score_breakdown': breakdown,
            'warnings': generate_soft_warnings(layout, room),
            'furniture_positions': layout,
            'metrics': metrics,
        })
    return results


# ── Group building ────────────────────────────────────────────────────────────

def _build_groups(furniture_list: List[dict]) -> List[Tuple[int, List[int]]]:
    """
    Return [(anchor_idx, [sat_idx, ...]), ...].
    Each satellite is assigned to at most one anchor.
    """
    assigned: set = set()
    groups: List[Tuple[int, List[int]]] = []

    for i, item in enumerate(furniture_list):
        if item['type'] not in _ANCHOR_SATELLITES or i in assigned:
            continue
        sat_types = _ANCHOR_SATELLITES[item['type']]
        sats = []
        for j, other in enumerate(furniture_list):
            if j != i and j not in assigned and other['type'] in sat_types:
                sats.append(j)
                assigned.add(j)
        assigned.add(i)
        if sats:
            groups.append((i, sats))

    return groups


# ── Item factory ──────────────────────────────────────────────────────────────

def _make_item(furn: dict, x: float, y: float, rot: int) -> dict:
    return {
        'type':     furn['type'],
        'x':        round(x, 2),
        'y':        round(y, 2),
        'rotation': rot,
        'width':    furn['width'],
        'depth':    furn['depth'],
        'label':    furn.get('label'),
    }


def _rotated(furn: dict, rot: int) -> Tuple[float, float]:
    """Return (rotated_width, rotated_depth) for a given rotation."""
    if rot in (90, 270):
        return furn['depth'], furn['width']
    return furn['width'], furn['depth']


# ── Placement helpers ─────────────────────────────────────────────────────────

def _place_against_wall(furn: dict, placed: list, room: dict) -> Optional[dict]:
    """
    Try placing furn with its back against each wall.
    Randomises wall order so we get variety across attempts.
    """
    rw, rd = room['width'], room['depth']
    fw, fd = furn['width'], furn['depth']

    walls = ['S', 'N', 'W', 'E']
    random.shuffle(walls)

    for wall in walls:
        if wall == 'S':
            rot = 0; w, d = fw, fd
            if w > rw: continue
            for _ in range(40):
                x = random.uniform(0, rw - w)
                item = _make_item(furn, x, 0, rot)
                if is_valid_placement(placed + [item], room):
                    return item
        elif wall == 'N':
            rot = 0; w, d = fw, fd
            if w > rw: continue
            for _ in range(40):
                x = random.uniform(0, rw - w)
                item = _make_item(furn, x, rd - d, rot)
                if is_valid_placement(placed + [item], room):
                    return item
        elif wall == 'W':
            rot = 90; w, d = fd, fw  # rotated: w=depth, d=width
            if w > rw or d > rd: continue
            for _ in range(40):
                y = random.uniform(0, rd - d)
                item = _make_item(furn, 0, y, rot)
                if is_valid_placement(placed + [item], room):
                    return item
        elif wall == 'E':
            rot = 270; w, d = fd, fw
            if w > rw or d > rd: continue
            for _ in range(40):
                y = random.uniform(0, rd - d)
                item = _make_item(furn, rw - w, y, rot)
                if is_valid_placement(placed + [item], room):
                    return item
    return None


def _place_adjacent(furn: dict, anchor: dict, placed: list, room: dict) -> Optional[dict]:
    """
    Place furn immediately adjacent to anchor (front/back/left/right).
    Tries all 4 rotations × 4 sides, shuffled for variety.
    """
    rw, rd = room['width'], room['depth']
    aw, ad = get_rotated_dims(anchor)
    ax, ay = anchor['x'], anchor['y']
    GAP = 0.03

    candidates = []
    for rot in [0, 90, 180, 270]:
        fw, fd = _rotated(furn, rot)
        # South of anchor (in front when anchor faces north)
        cx = ax + aw / 2 - fw / 2
        candidates.append((cx, ay - fd - GAP, rot))
        # North of anchor
        candidates.append((cx, ay + ad + GAP, rot))
        # West of anchor
        cy = ay + ad / 2 - fd / 2
        candidates.append((ax - fw - GAP, cy, rot))
        # East of anchor
        candidates.append((ax + aw + GAP, cy, rot))

    random.shuffle(candidates)
    for (x, y, rot) in candidates:
        fw, fd = _rotated(furn, rot)
        x = max(0.0, min(rw - fw, x))
        y = max(0.0, min(rd - fd, y))
        item = _make_item(furn, x, y, rot)
        if is_valid_placement(placed + [item], room):
            return item
    return None


def _place_random(furn: dict, placed: list, room: dict) -> Optional[dict]:
    """Random placement fallback."""
    rw, rd = room['width'], room['depth']
    for _ in range(300):
        rot = random.choice([0, 90, 180, 270])
        w, d = _rotated(furn, rot)
        if w > rw or d > rd:
            continue
        x = random.uniform(0, rw - w)
        y = random.uniform(0, rd - d)
        item = _make_item(furn, x, y, rot)
        if is_valid_placement(placed + [item], room):
            return item
    return None


# ── Constructive layout ───────────────────────────────────────────────────────

def _constructive_layout(room: dict, furniture_list: List[dict],
                          fixed_positions: dict = None) -> Optional[List[dict]]:
    """
    Build a semantically valid initial layout:
      Phase 1 — fixed positions (reoptimize mode)
      Phase 2 — wall-huggers (shelves, wardrobes) placed against walls
      Phase 3 — anchors (desks, beds) placed against walls, then satellites adjacent
      Phase 4 — everything else placed randomly
    """
    placed: List[dict] = []
    placed_idx: set = set()

    def commit(i: int, item: Optional[dict]) -> bool:
        if item is None:
            return False
        placed.append(item)
        placed_idx.add(i)
        return True

    # Phase 1: fixed positions
    if fixed_positions:
        for i, furn in enumerate(furniture_list):
            if str(i) in fixed_positions:
                fp = fixed_positions[str(i)]
                placed.append(_make_item(furn, fp['x'], fp['y'], fp.get('rotation', 0)))
                placed_idx.add(i)

    # Phase 2: wall-huggers
    for i, furn in enumerate(furniture_list):
        if i in placed_idx or furn['type'] not in _WALL_TYPES:
            continue
        item = _place_against_wall(furn, placed, room)
        if item is None:
            item = _place_random(furn, placed, room)
        if not commit(i, item):
            return None

    # Phase 3: anchors + their satellites
    for i, furn in enumerate(furniture_list):
        if i in placed_idx or furn['type'] not in _ANCHOR_SATELLITES:
            continue

        # Place anchor against wall (preferred) or anywhere
        anchor_item = _place_against_wall(furn, placed, room)
        if anchor_item is None:
            anchor_item = _place_random(furn, placed, room)
        if not commit(i, anchor_item):
            return None

        # Place each matching satellite adjacent to this anchor
        sat_types = _ANCHOR_SATELLITES[furn['type']]
        for j, sat_furn in enumerate(furniture_list):
            if j in placed_idx or sat_furn['type'] not in sat_types:
                continue
            sat_item = _place_adjacent(sat_furn, anchor_item, placed, room)
            if sat_item is None:
                sat_item = _place_random(sat_furn, placed, room)
            if not commit(j, sat_furn if sat_item is None else None
                          if sat_item is None else sat_item):
                # Try harder: pure random last resort
                sat_item = _place_random(sat_furn, placed, room)
                if not commit(j, sat_item):
                    return None

    # Phase 4: everything else (ungrouped satellites, sofas, etc.)
    for i, furn in enumerate(furniture_list):
        if i in placed_idx:
            continue
        item = _place_random(furn, placed, room)
        if not commit(i, item):
            return None

    return placed if is_valid_placement(placed, room) else None


# ── Group-aware SA perturbation ───────────────────────────────────────────────

def _perturb(layout: List[dict], room: dict,
             groups: List[Tuple[int, List[int]]],
             fixed_positions: dict = None) -> Optional[List[dict]]:
    """
    60% → move anchor + all its satellites as a rigid group (translate / snap-to-wall / rotate)
    40% → fine-tune a single movable item
    """
    new_layout = copy.deepcopy(layout)
    rw, rd = room['width'], room['depth']
    fixed_set = set(fixed_positions.keys()) if fixed_positions else set()

    # ── Group move ───────────────────────────────────────────────────────────
    movable_groups = [(ai, si) for ai, si in groups
                      if str(ai) not in fixed_set and ai < len(new_layout)]
    if movable_groups and random.random() < 0.60:
        anchor_idx, sat_idxs = random.choice(movable_groups)
        action = random.choice(['translate_x', 'translate_y', 'snap_wall'])

        if action in ('translate_x', 'translate_y'):
            delta = random.uniform(-0.7, 0.7)
            for idx in [anchor_idx] + sat_idxs:
                if str(idx) in fixed_set or idx >= len(new_layout):
                    continue
                item = new_layout[idx]
                iw, id_ = get_rotated_dims(item)
                if action == 'translate_x':
                    item['x'] = round(max(0, min(rw - iw, item['x'] + delta)), 3)
                else:
                    item['y'] = round(max(0, min(rd - id_, item['y'] + delta)), 3)

        elif action == 'snap_wall':
            anchor = new_layout[anchor_idx]
            aw, ad = get_rotated_dims(anchor)
            old_ax, old_ay = anchor['x'], anchor['y']
            wall = random.choice(['S', 'N', 'W', 'E'])

            if wall == 'S':
                anchor['y'] = 0
            elif wall == 'N':
                anchor['y'] = round(rd - ad, 3)
            elif wall == 'W':
                anchor['x'] = 0
            elif wall == 'E':
                anchor['x'] = round(rw - aw, 3)

            dx = anchor['x'] - old_ax
            dy = anchor['y'] - old_ay
            for idx in sat_idxs:
                if str(idx) in fixed_set or idx >= len(new_layout):
                    continue
                item = new_layout[idx]
                iw, id_ = get_rotated_dims(item)
                item['x'] = round(max(0, min(rw - iw, item['x'] + dx)), 3)
                item['y'] = round(max(0, min(rd - id_, item['y'] + dy)), 3)

        return new_layout

    # ── Individual fine-tune ─────────────────────────────────────────────────
    movable = [i for i in range(len(new_layout)) if str(i) not in fixed_set]
    if not movable:
        return new_layout

    idx = random.choice(movable)
    item = new_layout[idx]
    action = random.choice(['move_x', 'move_y', 'rotate'])
    iw, id_ = get_rotated_dims(item)

    if action == 'move_x':
        item['x'] = round(max(0, min(rw - iw, item['x'] + random.uniform(-0.35, 0.35))), 3)
    elif action == 'move_y':
        item['y'] = round(max(0, min(rd - id_, item['y'] + random.uniform(-0.35, 0.35))), 3)
    else:
        item['rotation'] = random.choice([0, 90, 180, 270])
        iw2, id2 = get_rotated_dims(item)
        item['x'] = round(max(0, min(rw - iw2, item['x'])), 3)
        item['y'] = round(max(0, min(rd - id2, item['y'])), 3)

    return new_layout


# ── Deduplication ─────────────────────────────────────────────────────────────

def _deduplicate(layouts: List[Tuple], n: int) -> List[Tuple]:
    unique = []
    for score, layout in layouts:
        if not any(_layouts_similar(layout, kept) for _, kept in unique):
            unique.append((score, layout))
        if len(unique) >= n:
            break
    return unique


def _layouts_similar(a: List[dict], b: List[dict], threshold: float = 0.3) -> bool:
    if len(a) != len(b):
        return False
    total_diff = sum(abs(ai['x'] - bi['x']) + abs(ai['y'] - bi['y'])
                     for ai, bi in zip(a, b))
    return total_diff / max(len(a), 1) < threshold
