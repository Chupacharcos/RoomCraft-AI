"""
Geometry utilities: collision detection, clearance, light coverage.
All coordinates in meters. Origin = SW corner of room.
"""
import math
from typing import List, Tuple


def get_rotated_dims(item: dict) -> Tuple[float, float]:
    w, d = item['width'], item['depth']
    if item['rotation'] in (90, 270):
        return d, w
    return w, d


def rect_overlap(ax, ay, aw, ad, bx, by, bw, bd, margin=0.0) -> bool:
    return not (
        ax + aw + margin <= bx or bx + bw + margin <= ax or
        ay + ad + margin <= by or by + bd + margin <= ay
    )


def check_within_room(item: dict, room_w: float, room_d: float) -> bool:
    w, d = get_rotated_dims(item)
    return (item['x'] >= 0 and item['y'] >= 0 and
            item['x'] + w <= room_w and item['y'] + d <= room_d)


def check_no_overlap(items: List[dict]) -> bool:
    for i in range(len(items)):
        wi, di = get_rotated_dims(items[i])
        for j in range(i + 1, len(items)):
            wj, dj = get_rotated_dims(items[j])
            if rect_overlap(items[i]['x'], items[i]['y'], wi, di,
                            items[j]['x'], items[j]['y'], wj, dj, margin=0.02):
                return False
    return True


def _opening_center(opening: dict, room_w: float, room_d: float) -> Tuple[float, float]:
    wall = opening['wall']
    width = opening['width']
    pos = opening.get('pos', 'center')
    offset = opening.get('offset')

    if wall == 'S':
        x = _pos_to_offset(pos, offset, room_w, width)
        return x + width / 2, 0.0
    elif wall == 'N':
        x = _pos_to_offset(pos, offset, room_w, width)
        return x + width / 2, room_d
    elif wall == 'W':
        y = _pos_to_offset(pos, offset, room_d, width)
        return 0.0, y + width / 2
    else:  # E
        y = _pos_to_offset(pos, offset, room_d, width)
        return room_w, y + width / 2


def _pos_to_offset(pos: str, offset, wall_len: float, opening_w: float) -> float:
    if offset is not None:
        return float(offset)
    if pos == 'left':
        return 0.3
    elif pos == 'right':
        return wall_len - opening_w - 0.3
    return (wall_len - opening_w) / 2


def compute_min_clearance_cm(items: List[dict]) -> int:
    min_dist = float('inf')
    for i in range(len(items)):
        wi, di = get_rotated_dims(items[i])
        for j in range(i + 1, len(items)):
            wj, dj = get_rotated_dims(items[j])
            dx = max(0.0, max(items[i]['x'], items[j]['x']) -
                     min(items[i]['x'] + wi, items[j]['x'] + wj))
            dy = max(0.0, max(items[i]['y'], items[j]['y']) -
                     min(items[i]['y'] + di, items[j]['y'] + dj))
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < min_dist:
                min_dist = dist
    return int(min_dist * 100) if min_dist != float('inf') else 200


def compute_light_coverage(items: List[dict], openings: List[dict],
                            room_w: float, room_d: float) -> float:
    windows = [op for op in openings if op['type'] == 'window']
    if not windows:
        return 75.0
    room_area = room_w * room_d
    blocked = 0.0
    for item in items:
        iw, id_ = get_rotated_dims(item)
        for op in windows:
            cx, cy = _opening_center(op, room_w, room_d)
            dist_to_window = min(
                abs(item['x'] - cx), abs(item['x'] + iw - cx),
                abs(item['y'] - cy), abs(item['y'] + id_ - cy)
            )
            if dist_to_window < 0.4:
                blocked += iw * id_ * 0.5
                break
    return round(max(0.0, (room_area - blocked) / room_area * 100), 1)


def count_conflicts(items: List[dict], openings: List[dict],
                    room_w: float, room_d: float) -> int:
    conflicts = 0
    for op in openings:
        cx, cy = _opening_center(op, room_w, room_d)
        arc_r = 0.9 if op['type'] == 'door' else 0.4
        for item in items:
            iw, id_ = get_rotated_dims(item)
            if rect_overlap(item['x'], item['y'], iw, id_,
                            cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2):
                conflicts += 1
                break
    return conflicts
