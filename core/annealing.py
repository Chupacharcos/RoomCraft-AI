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


def _random_initial_layout(room: dict, furniture_list: List[dict],
                            fixed_positions: dict = None) -> Optional[List[dict]]:
    """Place furniture randomly (respecting fixed positions), return valid layout or None."""
    room_w = room['width']
    room_d = room['depth']
    rotations = [0, 90, 180, 270]
    placed = []

    for idx, furn in enumerate(furniture_list):
        # Check if this piece has a fixed position
        if fixed_positions and str(idx) in fixed_positions:
            fp = fixed_positions[str(idx)]
            item = {
                'type': furn['type'],
                'x': fp['x'], 'y': fp['y'],
                'rotation': fp.get('rotation', 0),
                'width': furn['width'], 'depth': furn['depth'],
                'label': furn.get('label')
            }
            placed.append(item)
            continue

        placed_item = False
        for _ in range(200):
            rot = random.choice(rotations)
            w = furn['width'] if rot in (0, 180) else furn['depth']
            d = furn['depth'] if rot in (0, 180) else furn['width']
            if w > room_w or d > room_d:
                continue
            x = random.uniform(0, room_w - w)
            y = random.uniform(0, room_d - d)
            item = {
                'type': furn['type'],
                'x': round(x, 2), 'y': round(y, 2),
                'rotation': rot,
                'width': furn['width'], 'depth': furn['depth'],
                'label': furn.get('label')
            }
            test = placed + [item]
            if is_valid_placement(test, room):
                placed.append(item)
                placed_item = True
                break

        if not placed_item:
            return None

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
