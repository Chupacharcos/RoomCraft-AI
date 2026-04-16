"""Hard and soft constraints for layout validation."""
from typing import List
from core.geometry import (get_rotated_dims, check_within_room,
                            check_no_overlap, _opening_center, rect_overlap)


def is_valid_placement(layout: List[dict], room: dict) -> bool:
    """Returns True if layout satisfies ALL hard constraints."""
    room_w = room['width']
    room_d = room['depth']
    openings = room.get('openings', [])

    for item in layout:
        if not check_within_room(item, room_w, room_d):
            return False

    if not check_no_overlap(layout):
        return False

    if not _check_door_clearance(layout, openings, room_w, room_d):
        return False

    if not _check_access_clearance(layout, room_w, room_d):
        return False

    return True


def _check_door_clearance(items: List[dict], openings: List[dict],
                           room_w: float, room_d: float) -> bool:
    for op in openings:
        if op['type'] != 'door':
            continue
        cx, cy = _opening_center(op, room_w, room_d)
        arc_r = 0.9
        for item in items:
            iw, id_ = get_rotated_dims(item)
            if rect_overlap(item['x'], item['y'], iw, id_,
                            cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2):
                return False
    return True


def _check_access_clearance(items: List[dict], room_w: float, room_d: float) -> bool:
    """Wardrobes/drawers need 80cm front access; simplified check."""
    access_types = {'wardrobe', 'wardrobe_sliding', 'dresser'}
    for i, item in enumerate(items):
        if item['type'] not in access_types:
            continue
        iw, id_ = get_rotated_dims(item)
        front_x = item['x']
        front_y = item['y'] + id_
        # Check 80cm clear space in front
        clear_zone = {'x': front_x, 'y': front_y, 'width': iw, 'depth': 0.8}
        for j, other in enumerate(items):
            if i == j:
                continue
            ow, od = get_rotated_dims(other)
            if rect_overlap(clear_zone['x'], clear_zone['y'],
                            clear_zone['width'], clear_zone['depth'],
                            other['x'], other['y'], ow, od, margin=-0.05):
                return False
    return True


def generate_soft_warnings(layout: List[dict], room: dict) -> List[str]:
    warnings = []
    openings = room.get('openings', [])
    room_w = room['width']
    room_d = room['depth']

    for item in layout:
        iw, id_ = get_rotated_dims(item)
        if item['type'] in ('bed_double', 'bed_single'):
            # Bed accessible from both sides
            left_space = item['x']
            right_space = room_w - (item['x'] + iw)
            if left_space < 0.5 and right_space < 0.5:
                warnings.append("Cama sin acceso por ambos lados — considera moverla del centro.")
            # Feet towards door
            for op in openings:
                if op['type'] == 'door':
                    cx, cy = _opening_center(op, room_w, room_d)
                    if abs(item['y'] - cy) < 1.0:
                        warnings.append("Cama con pies orientados a la puerta — menos privacidad.")

        if item['type'] == 'desk':
            for op in openings:
                if op['type'] == 'window':
                    cx, cy = _opening_center(op, room_w, room_d)
                    dist = abs(item['x'] - cx) + abs(item['y'] - cy)
                    if dist < 0.35:
                        warnings.append(f"Escritorio a {int(dist*100)}cm de la ventana — puede generar sombra en tarde.")

    return warnings
