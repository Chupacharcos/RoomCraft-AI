"""
Simulated Annealing optimizer for room layout.
Explores 10k iterations per attempt, 20 attempts → Top 5 unique layouts.
"""
import random
import math
import copy
from typing import List, Optional, Tuple
from core.scorer import score_layout, score_breakdown, get_highlight
from core.constraints import is_valid_placement, generate_soft_warnings
from core.geometry import get_rotated_dims, compute_min_clearance_cm, compute_light_coverage, count_conflicts


def optimize(room: dict, furniture_list: List[dict], n_layouts: int = 5,
             iterations: int = 10000, fixed_positions: dict = None) -> List[dict]:
    """
    Main optimization entry point.
    fixed_positions: {furniture_index: {x, y, rotation}} for reoptimize endpoint.
    Returns list of ranked layout dicts.
    """
    # Scale down iterations/attempts based on total item count to keep latency <10s on CPU
    n_items = sum(f.get('qty', 1) for f in furniture_list)
    if n_items >= 7:
        iterations = min(iterations, 3000)
        n_attempts = 10
    elif n_items >= 4:
        iterations = min(iterations, 5000)
        n_attempts = 12
    else:
        n_attempts = 20

    best_layouts = []

    for attempt in range(n_attempts):
        layout = _random_initial_layout(room, furniture_list, fixed_positions)
        if layout is None:
            continue

        current = layout
        current_score = score_layout(current, room)
        T = 100.0

        for i in range(iterations):
            neighbor = _perturb(current, room, fixed_positions)
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

    # Sort and deduplicate (keep top n_layouts unique)
    best_layouts.sort(key=lambda x: x[0], reverse=True)
    unique_layouts = _deduplicate(best_layouts, n_layouts)

    results = []
    for rank, (score, layout) in enumerate(unique_layouts[:n_layouts], 1):
        breakdown = score_breakdown(layout, room)
        openings = room.get('openings', [])
        metrics = {
            'min_clearance_cm': compute_min_clearance_cm(layout),
            'light_coverage_pct': compute_light_coverage(layout, openings, room['width'], room['depth']),
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


_CHAIR_TYPES   = {'chair', 'chair_arm'}
_TABLE_TYPES   = {'desk', 'dining_table', 'coffee_table'}
_WALL_TYPES    = {'bookshelf', 'shelf', 'wardrobe', 'wardrobe_sliding', 'dresser'}
_BESIDE_TYPES  = {'nightstand'}


def _try_place(furn: dict, x: float, y: float, rot: int,
               placed: list, room: dict) -> Optional[dict]:
    """Return item dict if placement is valid, else None."""
    item = {
        'type': furn['type'],
        'x': round(x, 2), 'y': round(y, 2),
        'rotation': rot,
        'width': furn['width'], 'depth': furn['depth'],
        'label': furn.get('label'),
    }
    if is_valid_placement(placed + [item], room):
        return item
    return None


def _wall_candidates(furn: dict, room: dict, n: int = 6) -> list:
    """Return random candidate positions along the 4 walls."""
    room_w, room_d = room['width'], room['depth']
    fw, fd = furn['width'], furn['depth']
    candidates = []
    for _ in range(n * 4):
        wall = random.choice(['S', 'N', 'W', 'E'])
        if wall == 'S':   # y = 0
            rot = 0
            w, d = (fw, fd) if rot in (0, 180) else (fd, fw)
            x = random.uniform(0, max(0, room_w - w))
            candidates.append((x, 0, rot))
        elif wall == 'N':  # y = room_d - d
            rot = 180
            w, d = (fw, fd) if rot in (0, 180) else (fd, fw)
            x = random.uniform(0, max(0, room_w - w))
            candidates.append((x, room_d - d, rot))
        elif wall == 'W':  # x = 0
            rot = 90
            w, d = (fw, fd) if rot in (0, 180) else (fd, fw)
            y = random.uniform(0, max(0, room_d - d))
            candidates.append((0, y, rot))
        else:              # E: x = room_w - w
            rot = 270
            w, d = (fw, fd) if rot in (0, 180) else (fd, fw)
            y = random.uniform(0, max(0, room_d - d))
            candidates.append((room_w - w, y, rot))
    return candidates


def _adjacent_candidates(furn: dict, anchor: dict, room: dict) -> list:
    """Return candidate positions adjacent to anchor (front/back/left/right)."""
    aw = anchor['width'] if anchor['rotation'] in (0, 180) else anchor['depth']
    ad = anchor['depth'] if anchor['rotation'] in (0, 180) else anchor['width']
    fw, fd = furn['width'], furn['depth']
    ax, ay = anchor['x'], anchor['y']
    room_w, room_d = room['width'], room['depth']
    gap = 0.03

    candidates = []
    # In front (south of anchor)
    for rot in [0, 180]:
        w = fw if rot in (0, 180) else fd
        d = fd if rot in (0, 180) else fw
        cx = ax + aw / 2 - w / 2
        candidates.append((cx, ay - d - gap, rot))
    # Behind (north of anchor)
    for rot in [0, 180]:
        w = fw if rot in (0, 180) else fd
        d = fd if rot in (0, 180) else fw
        cx = ax + aw / 2 - w / 2
        candidates.append((cx, ay + ad + gap, rot))
    # Left (west)
    for rot in [90, 270]:
        w = fw if rot in (0, 180) else fd
        d = fd if rot in (0, 180) else fw
        cy = ay + ad / 2 - d / 2
        candidates.append((ax - w - gap, cy, rot))
    # Right (east)
    for rot in [90, 270]:
        w = fw if rot in (0, 180) else fd
        d = fd if rot in (0, 180) else fw
        cy = ay + ad / 2 - d / 2
        candidates.append((ax + aw + gap, cy, rot))

    # Clamp to room
    result = []
    for (x, y, rot) in candidates:
        w = fw if rot in (0, 180) else fd
        d = fd if rot in (0, 180) else fw
        x = max(0, min(room_w - w, x))
        y = max(0, min(room_d - d, y))
        result.append((x, y, rot))
    return result


def _random_initial_layout(room: dict, furniture_list: List[dict],
                            fixed_positions: dict = None) -> Optional[List[dict]]:
    """
    Place furniture with semantic hints:
    - chairs near desks/tables
    - shelves/wardrobes against walls
    Falls back to random placement when hints fail.
    """
    room_w = room['width']
    room_d = room['depth']
    rotations = [0, 90, 180, 270]
    placed = []

    for idx, furn in enumerate(furniture_list):
        # Fixed position override
        if fixed_positions and str(idx) in fixed_positions:
            fp = fixed_positions[str(idx)]
            placed.append({
                'type': furn['type'],
                'x': fp['x'], 'y': fp['y'],
                'rotation': fp.get('rotation', 0),
                'width': furn['width'], 'depth': furn['depth'],
                'label': furn.get('label'),
            })
            continue

        ftype = furn['type']
        item = None

        # ── Semantic placement ───────────────────────────────────────────────
        if ftype in _CHAIR_TYPES:
            # Try to place adjacent to already-placed desk/table
            anchors = [p for p in placed if p['type'] in _TABLE_TYPES]
            if anchors:
                anchor = anchors[0]  # primary desk
                for (x, y, rot) in _adjacent_candidates(furn, anchor, room):
                    item = _try_place(furn, x, y, rot, placed, room)
                    if item:
                        break

        elif ftype in _WALL_TYPES:
            # Try to place against a wall
            for (x, y, rot) in _wall_candidates(furn, room):
                item = _try_place(furn, x, y, rot, placed, room)
                if item:
                    break

        elif ftype in _BESIDE_TYPES:
            # Try to place beside a bed
            beds = [p for p in placed if p['type'] in ('bed_double', 'bed_single')]
            if beds:
                for (x, y, rot) in _adjacent_candidates(furn, beds[0], room):
                    item = _try_place(furn, x, y, rot, placed, room)
                    if item:
                        break

        # ── Random fallback ──────────────────────────────────────────────────
        if item is None:
            for _ in range(200):
                rot = random.choice(rotations)
                w = furn['width'] if rot in (0, 180) else furn['depth']
                d = furn['depth'] if rot in (0, 180) else furn['width']
                if w > room_w or d > room_d:
                    continue
                x = random.uniform(0, room_w - w)
                y = random.uniform(0, room_d - d)
                item = _try_place(furn, x, y, rot, placed, room)
                if item:
                    break

        if item is None:
            return None
        placed.append(item)

    return placed if is_valid_placement(placed, room) else None


def _perturb(layout: List[dict], room: dict, fixed_positions: dict = None) -> Optional[List[dict]]:
    new_layout = copy.deepcopy(layout)
    # Pick a random non-fixed item
    movable = [i for i in range(len(new_layout))
               if not (fixed_positions and str(i) in fixed_positions)]
    if not movable:
        return new_layout

    idx = random.choice(movable)
    item = new_layout[idx]
    action = random.choice(['move_x', 'move_y', 'rotate'])
    room_w = room['width']
    room_d = room['depth']

    if action == 'move_x':
        item['x'] = max(0, min(room_w - item['width'], item['x'] + random.uniform(-0.3, 0.3)))
    elif action == 'move_y':
        item['y'] = max(0, min(room_d - item['depth'], item['y'] + random.uniform(-0.3, 0.3)))
    else:
        item['rotation'] = random.choice([0, 90, 180, 270])

    item['x'] = round(item['x'], 3)
    item['y'] = round(item['y'], 3)
    return new_layout


def _deduplicate(layouts: List[Tuple], n: int) -> List[Tuple]:
    """Keep layouts that are sufficiently different from each other."""
    unique = []
    for score, layout in layouts:
        is_dup = False
        for _, kept in unique:
            if _layouts_similar(layout, kept):
                is_dup = True
                break
        if not is_dup:
            unique.append((score, layout))
        if len(unique) >= n:
            break
    return unique


def _layouts_similar(a: List[dict], b: List[dict], threshold: float = 0.3) -> bool:
    """Two layouts are similar if all items are within threshold meters."""
    if len(a) != len(b):
        return False
    total_diff = sum(abs(ai['x'] - bi['x']) + abs(ai['y'] - bi['y'])
                     for ai, bi in zip(a, b))
    return total_diff / max(len(a), 1) < threshold
