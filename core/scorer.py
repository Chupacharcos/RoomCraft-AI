"""Scoring function: 0-100 total score."""
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
    # 100cm+ = full 40; 60cm = 20; <60cm = 0
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


def score_ergonomics(layout: List[dict], room: dict) -> float:
    """Max 20 points: soft ergonomic rules."""
    score = 20.0
    openings = room.get('openings', [])
    room_w = room['width']
    room_d = room['depth']

    for item in layout:
        iw, id_ = get_rotated_dims(item)

        if item['type'] in ('bed_double', 'bed_single'):
            left_space = item['x']
            right_space = room_w - (item['x'] + iw)
            if left_space < 0.5 and right_space < 0.5:
                score -= 15  # Cama sin acceso ambos lados
            for op in openings:
                if op['type'] == 'door':
                    cx, cy = _opening_center(op, room_w, room_d)
                    if abs(item['y'] - cy) < 1.0:
                        score -= 8  # Pies hacia puerta

        if item['type'] == 'sofa' or item['type'] == 'sofa_3':
            # Sofa de espaldas al focal
            for op in openings:
                if op['type'] == 'window':
                    cx, _ = _opening_center(op, room_w, room_d)
                    if abs(item['x'] + iw / 2 - cx) < 0.5:
                        score -= 12  # Sofá espaldas a ventana

        if item['type'] in ('wardrobe', 'wardrobe_sliding', 'dresser'):
            for op in openings:
                if op['type'] == 'window':
                    cx, cy = _opening_center(op, room_w, room_d)
                    dist = min(abs(item['x'] - cx), abs(item['x'] + iw - cx))
                    if dist < 0.4:
                        score -= 10  # Mueble alto tapando ventana

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
            score += 1  # Bonus for centered items

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
