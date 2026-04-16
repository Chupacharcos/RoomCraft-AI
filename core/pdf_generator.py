"""
PDF technical floor plan generator using ReportLab.
Outputs A4 portrait with furniture floor plan, dimensions, metrics table.
"""
import io
from typing import List, Dict
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor


# Color palette
BG_DARK = HexColor('#1a1a2e')
ACCENT = HexColor('#e07b00')
WALL_COLOR = HexColor('#2d2d4e')
FURNITURE_COLOR = HexColor('#3a5f8a')
FURNITURE_STROKE = HexColor('#5b8fbf')
DOOR_COLOR = HexColor('#e07b00')
WINDOW_COLOR = HexColor('#64ffda')
TEXT_LIGHT = HexColor('#e0e0e0')
TEXT_DIM = HexColor('#8888aa')
GRID_COLOR = HexColor('#2a2a4a')


FURNITURE_LABELS = {
    'bed_single': 'Cama individual',
    'bed_double': 'Cama doble',
    'nightstand': 'Mesita',
    'wardrobe': 'Armario',
    'wardrobe_sliding': 'Armario corredero',
    'desk': 'Escritorio',
    'chair': 'Silla',
    'sofa': 'Sofá',
    'sofa_3': 'Sofá 3 plazas',
    'armchair': 'Sillón',
    'tv_stand': 'Mueble TV',
    'coffee_table': 'Mesa centro',
    'dining_table': 'Mesa comedor',
    'bookshelf': 'Librería',
    'dresser': 'Cómoda',
    'plant': 'Planta',
    'printer': 'Impresora',
    'meeting_table': 'Mesa reuniones',
}


def generate_pdf(room: dict, layout: dict) -> bytes:
    buf = io.BytesIO()
    w_page, h_page = A4

    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle("RoomCraft AI — Plano Técnico")

    # Dark background
    c.setFillColor(BG_DARK)
    c.rect(0, 0, w_page, h_page, fill=1, stroke=0)

    # --- Header ---
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(1.5*cm, h_page - 1.5*cm, "RoomCraft AI — Plano Técnico")

    c.setFillColor(TEXT_DIM)
    c.setFont("Helvetica", 9)
    c.drawString(1.5*cm, h_page - 2.1*cm,
                 f"Layout #{layout['rank']}  ·  Score {layout['score']}/100  ·  "
                 f"{layout['highlight']}  ·  adrianmoreno-dev.com")

    # --- Room dimensions label ---
    room_w = room['width']
    room_d = room['depth']
    c.setFillColor(TEXT_LIGHT)
    c.setFont("Helvetica", 9)
    c.drawString(1.5*cm, h_page - 2.7*cm,
                 f"Habitación: {room_w:.1f}m × {room_d:.1f}m  "
                 f"(techo {room.get('height', 2.5):.1f}m)")

    # --- Floor plan area ---
    plan_x = 1.5*cm
    plan_y = h_page - 3.5*cm - 10*cm  # top-left corner of floor plan
    plan_w = w_page - 3.0*cm
    plan_h = 10*cm

    scale = min(plan_w / room_w, plan_h / room_d)

    actual_w = room_w * scale
    actual_d = room_d * scale
    offset_x = plan_x + (plan_w - actual_w) / 2
    offset_y = plan_y + (plan_h - actual_d) / 2

    def to_canvas(x_m, y_m):
        return offset_x + x_m * scale, offset_y + y_m * scale

    # Grid
    c.setStrokeColor(GRID_COLOR)
    c.setLineWidth(0.3)
    for xi in range(int(room_w) + 2):
        px, py = to_canvas(xi, 0)
        c.line(px, py, px, py + actual_d)
    for yi in range(int(room_d) + 2):
        px, py = to_canvas(0, yi)
        c.line(px, py, px + actual_w, py)

    # Room walls
    c.setStrokeColor(WALL_COLOR)
    c.setLineWidth(3)
    c.setFillColor(HexColor('#0d1b2a'))
    rx, ry = to_canvas(0, 0)
    c.rect(rx, ry, actual_w, actual_d, fill=1, stroke=1)

    # Openings
    for op in room.get('openings', []):
        _draw_opening(c, op, room, scale, offset_x, offset_y, to_canvas)

    # Furniture
    for i, item in enumerate(layout.get('furniture_positions', [])):
        _draw_furniture(c, item, scale, offset_x, offset_y, to_canvas, i)

    # Dimension lines
    _draw_dimension_line(c, offset_x, offset_y, actual_w, actual_d, room_w, room_d)

    # Scale bar
    bar_len = 1.0 * scale  # 1 meter
    c.setStrokeColor(TEXT_DIM)
    c.setLineWidth(1)
    bar_x = offset_x
    bar_y = offset_y - 0.7*cm
    c.line(bar_x, bar_y, bar_x + bar_len, bar_y)
    c.line(bar_x, bar_y - 2, bar_x, bar_y + 2)
    c.line(bar_x + bar_len, bar_y - 2, bar_x + bar_len, bar_y + 2)
    c.setFillColor(TEXT_DIM)
    c.setFont("Helvetica", 7)
    c.drawCentredString(bar_x + bar_len / 2, bar_y - 10, "1m")

    # --- Metrics table ---
    _draw_metrics_table(c, layout, room, 1.5*cm, plan_y - 2.0*cm, w_page - 3.0*cm)

    # --- Furniture legend ---
    _draw_legend(c, layout.get('furniture_positions', []), 1.5*cm,
                 plan_y - 5.5*cm, w_page - 3.0*cm)

    # --- Warnings ---
    warnings = layout.get('warnings', [])
    if warnings:
        warn_y = 2.5*cm
        c.setFillColor(HexColor('#ff6b6b'))
        c.setFont("Helvetica-Bold", 8)
        c.drawString(1.5*cm, warn_y + 1.0*cm, "Advertencias detectadas:")
        c.setFillColor(HexColor('#ffaaaa'))
        c.setFont("Helvetica", 8)
        for w_text in warnings[:3]:
            c.drawString(1.5*cm, warn_y, f"• {w_text}")
            warn_y -= 0.4*cm

    # Watermark footer
    c.setFillColor(TEXT_DIM)
    c.setFont("Helvetica", 7)
    c.drawCentredString(w_page / 2, 0.7*cm,
                        "Generado por adrianmoreno-dev.com — RoomCraft AI")

    c.save()
    return buf.getvalue()


def _draw_opening(c, op, room, scale, offset_x, offset_y, to_canvas):
    from core.geometry import _opening_center, _pos_to_offset
    wall = op['wall']
    width = op['width']
    is_door = op['type'] == 'door'
    cx, cy = _opening_center(op, room['width'], room['depth'])
    half_w = width * scale / 2

    color = DOOR_COLOR if is_door else WINDOW_COLOR
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(2 if is_door else 1.5)

    if wall in ('S', 'N'):
        px = offset_x + (cx - width / 2) * scale
        py = to_canvas(0, cy)[1] if wall == 'S' else to_canvas(0, cy)[1]
        c.setFillColor(BG_DARK)
        c.rect(px, offset_y - 2 if wall == 'S' else offset_y + room['depth'] * scale - 2,
               width * scale, 4, fill=1, stroke=0)
        c.setStrokeColor(color)
        c.setLineWidth(2)
        c.line(px, offset_y if wall == 'S' else offset_y + room['depth'] * scale,
               px + width * scale,
               offset_y if wall == 'S' else offset_y + room['depth'] * scale)
    else:
        py = offset_y + (cy - width / 2) * scale
        wall_x = offset_x if wall == 'W' else offset_x + room['width'] * scale
        c.setFillColor(BG_DARK)
        c.rect(wall_x - 2, py, 4, width * scale, fill=1, stroke=0)
        c.setStrokeColor(color)
        c.setLineWidth(2)
        c.line(wall_x, py, wall_x, py + width * scale)


def _draw_furniture(c, item, scale, offset_x, offset_y, to_canvas, idx):
    from core.geometry import get_rotated_dims
    iw, id_ = get_rotated_dims(item)
    px, py = to_canvas(item['x'], item['y'])
    fw = iw * scale
    fh = id_ * scale

    # Fill
    alpha_colors = [
        HexColor('#2d5a8e'), HexColor('#2d7a6e'), HexColor('#6e4a8e'),
        HexColor('#8e6a2d'), HexColor('#2d8e4a'), HexColor('#8e2d4a'),
        HexColor('#4a6e8e'), HexColor('#8e8e2d'),
    ]
    c.setFillColor(alpha_colors[idx % len(alpha_colors)])
    c.setStrokeColor(FURNITURE_STROKE)
    c.setLineWidth(0.8)
    c.rect(px, py, fw, fh, fill=1, stroke=1)

    # Label
    label = FURNITURE_LABELS.get(item['type'], item['type'])
    font_size = max(5, min(8, fw / len(label) * 1.5))
    c.setFillColor(TEXT_LIGHT)
    c.setFont("Helvetica", font_size)
    c.drawCentredString(px + fw / 2, py + fh / 2 - font_size / 2, label[:12])

    # Dimensions in small text
    if fw > 25:
        c.setFillColor(TEXT_DIM)
        c.setFont("Helvetica", 5)
        c.drawCentredString(px + fw / 2, py + 3,
                            f"{iw*100:.0f}×{id_*100:.0f}cm")


def _draw_dimension_line(c, ox, oy, aw, ad, room_w, room_d):
    c.setStrokeColor(TEXT_DIM)
    c.setFillColor(TEXT_DIM)
    c.setLineWidth(0.5)
    offset = 12

    # Width arrow (bottom)
    c.line(ox, oy - offset, ox + aw, oy - offset)
    c.line(ox, oy - offset - 3, ox, oy - offset + 3)
    c.line(ox + aw, oy - offset - 3, ox + aw, oy - offset + 3)
    c.setFont("Helvetica", 7)
    c.drawCentredString(ox + aw / 2, oy - offset - 9, f"{room_w:.2f} m")

    # Depth arrow (left)
    c.line(ox - offset, oy, ox - offset, oy + ad)
    c.line(ox - offset - 3, oy, ox - offset + 3, oy)
    c.line(ox - offset - 3, oy + ad, ox - offset + 3, oy + ad)
    c.saveState()
    c.translate(ox - offset - 12, oy + ad / 2)
    c.rotate(90)
    c.drawCentredString(0, 0, f"{room_d:.2f} m")
    c.restoreState()


def _draw_metrics_table(c, layout, room, x, y, width):
    metrics = layout.get('metrics', {})
    breakdown = layout.get('score_breakdown', {})

    row_h = 0.55*cm
    cols = [
        ("Score total", f"{layout['score']}/100"),
        ("Circulación", f"{breakdown.get('circulation', 0):.0f}/40"),
        ("Luz natural", f"{breakdown.get('natural_light', 0):.0f}/30"),
        ("Ergonomía", f"{breakdown.get('ergonomics', 0):.0f}/20"),
        ("Estética", f"{breakdown.get('aesthetics', 0):.0f}/10"),
        ("Paso mínimo", f"{metrics.get('min_clearance_cm', 0)} cm"),
        ("Cobertura luz", f"{metrics.get('light_coverage_pct', 0):.0f}%"),
        ("Conflictos", str(metrics.get('conflicts', 0))),
    ]

    col_w = width / len(cols)
    c.setFillColor(HexColor('#0d1b2a'))
    c.rect(x, y, width, row_h * 2, fill=1, stroke=0)

    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(TEXT_DIM)
    for i, (label, value) in enumerate(cols):
        cx = x + col_w * i + col_w / 2
        c.drawCentredString(cx, y + row_h + 2, label)
        c.setFillColor(ACCENT if i == 0 else TEXT_LIGHT)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(cx, y + 4, value)
        c.setFillColor(TEXT_DIM)
        c.setFont("Helvetica-Bold", 7)

    c.setStrokeColor(WALL_COLOR)
    c.setLineWidth(0.3)
    for i in range(1, len(cols)):
        lx = x + col_w * i
        c.line(lx, y, lx, y + row_h * 2)


def _draw_legend(c, positions, x, y, width):
    if not positions:
        return
    c.setFillColor(TEXT_DIM)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(x, y, "MUEBLES:")

    col_w = width / 3
    for i, item in enumerate(positions):
        col = i % 3
        row = i // 3
        lx = x + col * col_w
        ly = y - 0.4*cm - row * 0.35*cm
        if ly < 1.5*cm:
            break
        label = FURNITURE_LABELS.get(item['type'], item['type'])
        from core.geometry import get_rotated_dims
        iw, id_ = get_rotated_dims(item)
        c.setFillColor(TEXT_LIGHT)
        c.setFont("Helvetica", 7)
        c.drawString(lx, ly, f"• {label}: {iw*100:.0f}×{id_*100:.0f}cm")
