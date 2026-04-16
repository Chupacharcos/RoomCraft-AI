"""Furniture catalog and predefined examples."""
import json
import os
from fastapi import APIRouter

router = APIRouter()

FURNITURE_CATALOG = [
    {"type": "bed_single",      "label": "Cama individual",     "width": 0.9,  "depth": 2.0, "category": "dormitorio"},
    {"type": "bed_double",      "label": "Cama doble",          "width": 1.6,  "depth": 2.0, "category": "dormitorio"},
    {"type": "nightstand",      "label": "Mesita de noche",     "width": 0.5,  "depth": 0.4, "category": "dormitorio"},
    {"type": "wardrobe",        "label": "Armario",             "width": 1.8,  "depth": 0.6, "category": "dormitorio"},
    {"type": "wardrobe_sliding","label": "Armario corredero",   "width": 1.8,  "depth": 0.6, "category": "dormitorio"},
    {"type": "dresser",         "label": "Cómoda",              "width": 1.0,  "depth": 0.5, "category": "dormitorio"},
    {"type": "desk",            "label": "Escritorio",          "width": 1.2,  "depth": 0.6, "category": "trabajo"},
    {"type": "chair",           "label": "Silla",               "width": 0.6,  "depth": 0.6, "category": "trabajo"},
    {"type": "sofa",            "label": "Sofá 2 plazas",       "width": 2.0,  "depth": 0.9, "category": "salon"},
    {"type": "sofa_3",          "label": "Sofá 3 plazas",       "width": 2.2,  "depth": 0.9, "category": "salon"},
    {"type": "armchair",        "label": "Sillón",              "width": 0.8,  "depth": 0.8, "category": "salon"},
    {"type": "tv_stand",        "label": "Mueble TV",           "width": 1.5,  "depth": 0.4, "category": "salon"},
    {"type": "coffee_table",    "label": "Mesa centro",         "width": 1.0,  "depth": 0.5, "category": "salon"},
    {"type": "dining_table",    "label": "Mesa comedor",        "width": 1.6,  "depth": 0.9, "category": "salon"},
    {"type": "bookshelf",       "label": "Librería",            "width": 0.8,  "depth": 0.3, "category": "salon"},
    {"type": "plant",           "label": "Planta",              "width": 0.4,  "depth": 0.4, "category": "decoracion"},
    {"type": "printer",         "label": "Impresora",           "width": 0.5,  "depth": 0.4, "category": "trabajo"},
    {"type": "meeting_table",   "label": "Mesa reuniones",      "width": 1.4,  "depth": 0.7, "category": "trabajo"},
]

EXAMPLES = [
    {
        "name": "Dormitorio 10m²",
        "description": "Habitación estudiante o piso compartido — espacio reducido al máximo",
        "room": {"width": 3.5, "depth": 2.8, "height": 2.5},
        "openings": [
            {"wall": "S", "type": "door", "width": 0.8, "pos": "left"},
            {"wall": "E", "type": "window", "width": 1.0, "pos": "center"}
        ],
        "furniture": [
            {"type": "bed_single",      "width": 0.9, "depth": 2.0, "qty": 1},
            {"type": "nightstand",      "width": 0.5, "depth": 0.4, "qty": 1},
            {"type": "desk",            "width": 1.2, "depth": 0.6, "qty": 1},
            {"type": "chair",           "width": 0.6, "depth": 0.6, "qty": 1},
            {"type": "wardrobe",        "width": 1.8, "depth": 0.6, "qty": 1},
        ]
    },
    {
        "name": "Salón 20m²",
        "description": "Reforma de salón familiar — gestión de punto focal y zonas de conversación",
        "room": {"width": 5.0, "depth": 4.0, "height": 2.7},
        "openings": [
            {"wall": "S", "type": "door", "width": 0.8, "pos": "left"},
            {"wall": "N", "type": "window", "width": 1.5, "pos": "center"},
            {"wall": "W", "type": "window", "width": 1.2, "pos": "center"}
        ],
        "furniture": [
            {"type": "sofa_3",       "width": 2.2, "depth": 0.9, "qty": 1},
            {"type": "armchair",     "width": 0.8, "depth": 0.8, "qty": 1},
            {"type": "coffee_table", "width": 1.0, "depth": 0.5, "qty": 1},
            {"type": "tv_stand",     "width": 1.5, "depth": 0.4, "qty": 1},
            {"type": "bookshelf",    "width": 0.8, "depth": 0.3, "qty": 1},
            {"type": "plant",        "width": 0.4, "depth": 0.4, "qty": 1},
        ]
    },
    {
        "name": "Despacho profesional 15m²",
        "description": "Caso de arquitecto o interiorista — métricas profesionales al máximo",
        "room": {"width": 4.0, "depth": 3.75, "height": 2.8},
        "openings": [
            {"wall": "S", "type": "door", "width": 0.9, "pos": "right"},
            {"wall": "N", "type": "window", "width": 1.8, "pos": "center"}
        ],
        "furniture": [
            {"type": "desk",          "width": 1.6, "depth": 0.8, "qty": 1},
            {"type": "chair",         "width": 0.6, "depth": 0.6, "qty": 1},
            {"type": "chair",         "width": 0.6, "depth": 0.6, "qty": 2, "label": "Silla cliente"},
            {"type": "wardrobe",      "width": 1.2, "depth": 0.5, "qty": 1, "label": "Archivador"},
            {"type": "meeting_table", "width": 1.4, "depth": 0.7, "qty": 1},
            {"type": "printer",       "width": 0.5, "depth": 0.4, "qty": 1},
        ]
    }
]


@router.get("/furniture-catalog")
async def get_furniture_catalog():
    return {"catalog": FURNITURE_CATALOG}


@router.get("/examples")
async def get_examples():
    return {"examples": EXAMPLES}


@router.get("/health")
async def health():
    import os
    groq_ok = bool(os.getenv('GROQ_API_KEY'))
    return {"status": "ok", "groq": "ok" if groq_ok else "missing_key", "optimizer": "ok"}
