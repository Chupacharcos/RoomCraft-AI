"""Scoring function: 0-100 total score."""
import math
from typing import List
from core.geometry import (get_rotated_dims, _opening_center, compute_light_coverage,
                            compute_min_clearance_cm)


def score_layout(layout: List[dict], room: dict) -> float:
    return (score_circulation(layout, room) +
            score_natural_light(layout, room) +
            score_ergonomics(layout, room) +
            score_aesthetics(layout, room))


def score_breakdown(layout: List[dict], room: dict) -> dict:
    return {
        'circulation': round(score_circulation(layout, room), 1),
        'natural_light': round(score_natural_light(layout, room), 1),
        'ergonomics': round(score_ergonomics(layout, room), 1),
        'aesthetics': round(score_aesthetics(layout, room), 1),
    }


def score_circulation(layout: List[dict], room: dict) -> float:
    """Max 40 points: penalize tight passages."""
    clearance = compute_min_clearance_cm(layout)
    if clearance >= 100:
        return 40.0
    elif clearance >= 60:
        return 20.0 + (clearance - 60) / 40 * 20
    else:
        return max(0.0, clearance / 60 * 20)


def score_natural_light(layout: List[dict], room: dict) -> float:
    """Max 30 points: furniture not blocking windows."""
    openings = room.get('openings', [])
    coverage = compute_light_coverage(layout, openings, room['width'], room['depth'])
    return coverage / 100 * 30


def _min_wall_dist(item: dict, room_w: float, room_d: float) -> float:
    """Distance from nearest edge of item to nearest wall (meters)."""
    iw, id_ = get_rotated_dims(item)
    return min(item['x'], item['y'],
               room_w - (item['x'] + iw),
               room_d - (item['y'] + id_))


def _edge_dist(a: dict, b: dict) -> float:
    """Edge-to-edge distance between two items (0 = touching)."""
    aw, ad = get_rotated_dims(a)
    bw, bd = get_rotated_dims(b)
    dx = max(0.0, max(a['x'], b['x']) - min(a['x'] + aw, b['x'] + bw))
    dy = max(0.0, max(a['y'], b['y']) - min(a['y'] + ad, b['y'] + bd))
    return math.sqrt(dx * dx + dy * dy)


def score_ergonomics(layout: List[dict], room: dict) -> float:
    """
    Max ~30 points: semantic placement rules.
    Strong rewards/penalties guide SA toward logical layouts.
    """
    score = 30.0
    room_w = room['width']
    room_d = room['depth']
    openings = room.get('openings', [])
    WALL_TOL = 0.15  # within 15 cm = "against wall"

    # Group by role
    desks        = [i for i in layout if i['type'] == 'desk']
    chairs       = [i for i in layout if i['type'] in ('chair', 'chair_arm')]
    seating_tbls = desks + [i for i in layout if i['type'] in ('dining_table', 'coffee_table')]
    wall_pieces  = [i for i in layout if i['type'] in
                    ('bookshelf', 'shelf', 'wardrobe', 'wardrobe_sliding', 'dresser')]
    beds         = [i for i in layout if i['type'] in ('bed_double', 'bed_single')]
    sofas        = [i for i in layout if i['type'] in ('sofa', 'sofa_3', 'armchair')]
    nightstands  = [i for i in layout if i['type'] == 'nightstand']

    # ── Rule 1: Shelves / wardrobes MUST hug a wall ─────────────────────────
    for item in wall_pieces:
        d = _min_wall_dist(item, room_w, room_d)
        if d <= WALL_TOL:
            score += 10.0   # strong reward
        else:
            score -= 15.0   # strong penalty: shelf floating in room makes no sense

    # ── Rule 2: Desk should be near or against a wall ───────────────────────
    for item in desks:
        d = _min_wall_dist(item, room_w, room_d)
        if d <= WALL_TOL:
            score += 6.0
        elif d <= 0.5:
            score += 2.0
        else:
            score -= 10.0   # desk in the middle of the room is wrong

    # ── Rule 3: Each chair must be adjacent to a desk or table ──────────────
    for chair in chairs:
        if not seating_tbls:
            break
        nearest_dist = min(_edge_dist(chair, t) for t in seating_tbls)
        if nearest_dist <= 0.1:         # touching / tucked in
            score += 14.0
        elif nearest_dist <= 0.55:      # pulled back slightly (sitting position)
            score += 10.0
        elif nearest_dist <= 0.75:      # nearby but not ideal
            score += 0.0
        else:
            score -= 22.0   # chair with no desk/table nearby — completely wrong

    # ── Rule 4: Nightstands should be beside a bed ──────────────────────────
    for ns in nightstands:
        if not beds:
            break
        nearest_dist = min(_edge_dist(ns, b) for b in beds)
        if nearest_dist <= 0.15:
            score += 6.0
        elif nearest_dist <= 0.6:
            score += 2.0
        else:
            score -= 8.0

    # ── Rule 5: Beds — side access + not blocking door ──────────────────────
    for item in beds:
        iw, id_ = get_rotated_dims(item)
        left_space = item['x']
        right_space = room_w - (item['x'] + iw)
        if left_space < 0.5 and right_space < 0.5:
            score -= 15
        for op in openings:
            if op['type'] == 'door':
                cx, cy = _opening_center(op, room_w, room_d)
                if abs(item['y'] - cy) < 1.0:
                    score -= 8

    # ── Rule 6: Sofas face the room / not backs to window ───────────────────
    for item in sofas:
        iw, id_ = get_rotated_dims(item)
        for op in openings:
            if op['type'] == 'window':
                cx, _ = _opening_center(op, room_w, room_d)
                if abs(item['x'] + iw / 2 - cx) < 0.5:
                    score -= 10

    # ── Rule 7: Wardrobes/dressers must not block windows ───────────────────
    for item in layout:
        if item['type'] in ('wardrobe', 'wardrobe_sliding', 'dresser'):
            iw, id_ = get_rotated_dims(item)
            for op in openings:
                if op['type'] == 'window':
                    cx, cy = _opening_center(op, room_w, room_d)
                    dist = min(abs(item['x'] - cx), abs(item['x'] + iw - cx))
                    if dist < 0.4:
                        score -= 10

    return max(0.0, score)


def score_aesthetics(layout: List[dict], room: dict) -> float:
    """Max 10 points: symmetry, alignment."""
    room_w = room['width']
    room_cx = room_w / 2
    score = 10.0

    for item in layout:
        iw, _ = get_rotated_dims(item)
        item_cx = item['x'] + iw / 2
        offset = abs(item_cx - room_cx)
        if offset < 0.1:
            score += 1

    return min(10.0, max(0.0, score))


def get_highlight(breakdown: dict) -> str:
    max_key = max(breakdown, key=breakdown.get)
    highlights = {
        'circulation': 'Mejor circulación',
        'natural_light': 'Más luz natural',
        'ergonomics': 'Mayor ergonomía',
        'aesthetics': 'Mayor simetría',
    }
    return highlights.get(max_key, 'Layout equilibrado')
