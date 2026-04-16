"""Optimizer and re-optimizer endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from core.annealing import optimize

router = APIRouter()


class OptimizeRequest(BaseModel):
    room: Dict[str, Any]
    furniture: List[Dict[str, Any]]


class ReoptimizeRequest(BaseModel):
    room: Dict[str, Any]
    furniture: List[Dict[str, Any]]
    fixed_positions: Dict[str, Dict[str, Any]]  # {str(idx): {x, y, rotation}}


def _validate_room(room: dict):
    if not room.get('width') or not room.get('depth'):
        raise HTTPException(status_code=400, detail="Habitación sin dimensiones válidas")
    if room['width'] < 1.5 or room['depth'] < 1.5:
        raise HTTPException(status_code=400, detail="Habitación demasiado pequeña (mínimo 1.5m × 1.5m)")
    if room['width'] > 20 or room['depth'] > 20:
        raise HTTPException(status_code=400, detail="Habitación demasiado grande (máximo 20m × 20m)")


def _validate_furniture_fits(room: dict, furniture: list):
    room_area = room['width'] * room['depth'] * 0.6  # 60% usable
    furniture_area = sum(f.get('width', 1) * f.get('depth', 1) * f.get('qty', 1)
                         for f in furniture)
    if furniture_area > room_area:
        raise HTTPException(
            status_code=422,
            detail=f"Los muebles ({furniture_area:.1f}m²) no caben en la habitación "
                   f"(área útil ~{room_area:.1f}m²). Reduce el número de muebles."
        )


def _expand_furniture(furniture_list: list) -> list:
    """Expand qty > 1 into individual items."""
    expanded = []
    for f in furniture_list:
        qty = f.get('qty', 1)
        for i in range(qty):
            item = {k: v for k, v in f.items() if k != 'qty'}
            if qty > 1:
                item['label'] = f"{item.get('label', item['type'])} {i+1}"
            expanded.append(item)
    return expanded


@router.post("/optimize")
async def optimize_layout(req: OptimizeRequest):
    _validate_room(req.room)
    expanded = _expand_furniture(req.furniture)
    if not expanded:
        raise HTTPException(status_code=400, detail="Sin muebles para colocar")
    _validate_furniture_fits(req.room, expanded)

    layouts = optimize(req.room, expanded)
    if not layouts:
        raise HTTPException(
            status_code=422,
            detail="No se pudo generar ningún layout válido. La habitación puede ser demasiado pequeña para todos los muebles."
        )
    return {'layouts': layouts}


@router.post("/reoptimize")
async def reoptimize_layout(req: ReoptimizeRequest):
    _validate_room(req.room)
    expanded = _expand_furniture(req.furniture)
    if not expanded:
        raise HTTPException(status_code=400, detail="Sin muebles para colocar")

    layouts = optimize(req.room, expanded, fixed_positions=req.fixed_positions)
    if not layouts:
        raise HTTPException(status_code=422, detail="No se pudo re-optimizar el layout")
    return {'layouts': layouts}
