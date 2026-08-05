"""
Exportador de layouts a glTF 2.0 (.gltf, JSON con buffer embebido).

glTF es el estándar Khronos que abren sin plugins Blender, three.js, Babylon,
Unity, Unreal, el Visor 3D de Windows y la vista previa de macOS/iOS. Exportarlo
convierte el resultado de RoomCraft en algo que un estudio de interiorismo o un
portal inmobiliario puede meter en su propia escena, en vez de quedarse en un
PNG.

Sobre la altura: el optimizador trabaja en planta (x, y, ancho, fondo,
rotación), que es lo que importa para circulación y colisiones. Para levantar el
plano a 3D hace falta una altura por mueble, y aquí se usa una tabla de alturas
típicas de mobiliario (`FURNITURE_HEIGHTS`). Es una convención documentada — la
misma que aplica cualquier conversor de plano a 3D — no un dato medido: por eso
va declarada en el propio fichero y en el README, y se puede ajustar.

Geometría: todos los muebles comparten UNA malla de cubo unitario, instanciada
por nodo con su propia traslación/rotación/escala. Así el fichero pesa unos
pocos KB independientemente del número de muebles.
"""
from __future__ import annotations

import base64
import json
import math
import struct

# Alturas típicas en metros. Fuente: dimensiones habituales de mobiliario
# residencial y de oficina; ajustables por el integrador.
FURNITURE_HEIGHTS = {
    "bed_single": 0.55, "bed_double": 0.55, "nightstand": 0.55,
    "wardrobe": 2.00, "wardrobe_sliding": 2.00, "desk": 0.75,
    "chair": 0.90, "sofa": 0.85, "sofa_3": 0.85, "armchair": 0.90,
    "tv_stand": 0.50, "coffee_table": 0.42, "dining_table": 0.75,
    "bookshelf": 1.80, "dresser": 0.85, "plant": 1.20,
    "printer": 0.40, "meeting_table": 0.75,
}
DEFAULT_HEIGHT = 0.75
WALL_HEIGHT = 2.50
FLOOR_THICKNESS = 0.02

# Colores RGBA por familia de mueble, para que la escena no salga monocroma.
FURNITURE_COLORS = {
    "bed_single": [0.30, 0.45, 0.70, 1.0], "bed_double": [0.30, 0.45, 0.70, 1.0],
    "wardrobe": [0.55, 0.40, 0.28, 1.0], "wardrobe_sliding": [0.55, 0.40, 0.28, 1.0],
    "desk": [0.62, 0.47, 0.33, 1.0], "dining_table": [0.62, 0.47, 0.33, 1.0],
    "meeting_table": [0.62, 0.47, 0.33, 1.0], "coffee_table": [0.62, 0.47, 0.33, 1.0],
    "sofa": [0.42, 0.45, 0.50, 1.0], "sofa_3": [0.42, 0.45, 0.50, 1.0],
    "armchair": [0.42, 0.45, 0.50, 1.0], "chair": [0.50, 0.52, 0.55, 1.0],
    "plant": [0.25, 0.55, 0.30, 1.0], "bookshelf": [0.50, 0.36, 0.25, 1.0],
}
DEFAULT_COLOR = [0.60, 0.60, 0.62, 1.0]
FLOOR_COLOR = [0.85, 0.83, 0.80, 1.0]


def _unit_cube() -> tuple[bytes, int, int]:
    """Cubo de 1×1×1 centrado en el origen, con normales por cara (24 vértices,
    36 índices). Devuelve (buffer, n_vertices, n_indices)."""
    # (normal, 4 esquinas) por cara
    faces = [
        ([0, 0, 1],  [(-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5)]),
        ([0, 0, -1], [(.5, -.5, -.5), (-.5, -.5, -.5), (-.5, .5, -.5), (.5, .5, -.5)]),
        ([0, 1, 0],  [(-.5, .5, .5), (.5, .5, .5), (.5, .5, -.5), (-.5, .5, -.5)]),
        ([0, -1, 0], [(-.5, -.5, -.5), (.5, -.5, -.5), (.5, -.5, .5), (-.5, -.5, .5)]),
        ([1, 0, 0],  [(.5, -.5, .5), (.5, -.5, -.5), (.5, .5, -.5), (.5, .5, .5)]),
        ([-1, 0, 0], [(-.5, -.5, -.5), (-.5, -.5, .5), (-.5, .5, .5), (-.5, .5, -.5)]),
    ]
    positions, normals, indices = [], [], []
    for i, (n, corners) in enumerate(faces):
        base = i * 4
        for c in corners:
            positions.append(c)
            normals.append(n)
        indices += [base, base + 1, base + 2, base, base + 2, base + 3]

    pos_bytes = b"".join(struct.pack("<3f", *p) for p in positions)
    nrm_bytes = b"".join(struct.pack("<3f", *map(float, n)) for n in normals)
    idx_bytes = b"".join(struct.pack("<H", i) for i in indices)
    # Los offsets de los accessors deben estar alineados a 4 bytes.
    while len(idx_bytes) % 4:
        idx_bytes += b"\x00"
    return pos_bytes + nrm_bytes + idx_bytes, len(positions), len(indices)


def _quat_y(degrees: float) -> list[float]:
    """Cuaternión [x, y, z, w] de una rotación sobre el eje Y (vertical)."""
    half = math.radians(degrees) / 2.0
    return [0.0, math.sin(half), 0.0, math.cos(half)]


def layout_to_gltf(room: dict, layout: list[dict], name: str = "RoomCraft") -> dict:
    """Convierte una habitación y su layout en un documento glTF 2.0.

    Ejes glTF: Y es la vertical. El plano de la habitación (x, y) se mapea a
    (X, Z), de modo que la planta se ve desde arriba tal cual la calculó el
    optimizador.
    """
    buf, n_vert, n_idx = _unit_cube()
    pos_len = n_vert * 12
    nrm_len = n_vert * 12
    idx_off = pos_len + nrm_len

    room_w = float(room.get("width", 0))
    room_d = float(room.get("depth", 0))

    materials = [{"name": "floor",
                  "pbrMetallicRoughness": {"baseColorFactor": FLOOR_COLOR,
                                           "metallicFactor": 0.0, "roughnessFactor": 0.95}}]
    mat_index: dict[str, int] = {}
    nodes, children = [], []

    # Suelo: el mismo cubo, aplastado.
    nodes.append({
        "name": "Suelo",
        "mesh": 0,
        "translation": [room_w / 2, -FLOOR_THICKNESS / 2, room_d / 2],
        "scale": [room_w, FLOOR_THICKNESS, room_d],
    })
    children.append(0)

    for item in layout:
        ftype = item.get("type", "unknown")
        if ftype not in mat_index:
            mat_index[ftype] = len(materials)
            materials.append({
                "name": ftype,
                "pbrMetallicRoughness": {
                    "baseColorFactor": FURNITURE_COLORS.get(ftype, DEFAULT_COLOR),
                    "metallicFactor": 0.0, "roughnessFactor": 0.8,
                },
            })

        h = FURNITURE_HEIGHTS.get(ftype, DEFAULT_HEIGHT)
        w = float(item.get("width", 0.5))
        d = float(item.get("depth", 0.5))
        rot = float(item.get("rotation", 0) or 0)
        # x, y son la esquina del mueble; glTF escala desde el centro del nodo.
        cx = float(item.get("x", 0)) + w / 2
        cz = float(item.get("y", 0)) + d / 2

        nodes.append({
            "name": item.get("label") or ftype,
            "mesh": mat_index[ftype],  # una malla por material (misma geometría)
            "translation": [cx, h / 2, cz],
            "rotation": _quat_y(rot),
            "scale": [w, h, d],
        })
        children.append(len(nodes) - 1)

    # Una "mesh" por material, todas apuntando a los mismos accessors.
    meshes = [{
        "name": mat["name"],
        "primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1}, "indices": 2, "material": i}],
    } for i, mat in enumerate(materials)]

    nodes.append({"name": name, "children": children})
    root = len(nodes) - 1

    return {
        "asset": {"version": "2.0", "generator": "RoomCraft AI glTF exporter"},
        "scene": 0,
        "scenes": [{"name": name, "nodes": [root]}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "buffers": [{
            "byteLength": len(buf),
            "uri": "data:application/octet-stream;base64," + base64.b64encode(buf).decode(),
        }],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": pos_len, "target": 34962},
            {"buffer": 0, "byteOffset": pos_len, "byteLength": nrm_len, "target": 34962},
            {"buffer": 0, "byteOffset": idx_off, "byteLength": n_idx * 2, "target": 34963},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": n_vert, "type": "VEC3",
             "min": [-0.5, -0.5, -0.5], "max": [0.5, 0.5, 0.5]},
            {"bufferView": 1, "componentType": 5126, "count": n_vert, "type": "VEC3"},
            {"bufferView": 2, "componentType": 5123, "count": n_idx, "type": "SCALAR"},
        ],
        "extras": {
            "room": {"width": room_w, "depth": room_d, "wall_height": WALL_HEIGHT},
            "nota_alturas": "Las alturas de los muebles son valores típicos por tipo "
                            "(core/gltf_export.py::FURNITURE_HEIGHTS), no medidas del optimizador, "
                            "que trabaja en planta.",
        },
    }


def layout_to_gltf_bytes(room: dict, layout: list[dict], name: str = "RoomCraft") -> bytes:
    return json.dumps(layout_to_gltf(room, layout, name), ensure_ascii=False).encode("utf-8")
