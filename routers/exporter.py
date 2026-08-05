"""Export endpoints: PDF (plano técnico) y glTF 2.0 (escena 3D)."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Dict, Any, List
from core.gltf_export import layout_to_gltf_bytes
from core.pdf_generator import generate_pdf

router = APIRouter()


class ExportRequest(BaseModel):
    room: Dict[str, Any]
    layout: Dict[str, Any]


@router.post("/export-pdf")
async def export_pdf(req: ExportRequest):
    try:
        pdf_bytes = generate_pdf(req.room, req.layout)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=roomcraft-layout-{req.layout.get('rank', 1)}.pdf",
                "Cache-Control": "no-cache",
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando PDF: {str(e)}")


@router.post("/export-gltf")
async def export_gltf(req: ExportRequest):
    """Exporta el layout como escena glTF 2.0.

    Formato estándar de Khronos: se abre sin plugins en Blender, three.js,
    Babylon.js, Unity, Unreal, el Visor 3D de Windows y la vista previa de
    macOS/iOS. Permite llevar el resultado a la escena del propio integrador
    en lugar de quedarse en el PNG del render.
    """
    try:
        rank = req.layout.get("rank", 1)
        gltf_bytes = layout_to_gltf_bytes(
            req.room,
            req.layout.get("furniture_positions", []),
            name=f"RoomCraft Layout {rank}",
        )
        return Response(
            content=gltf_bytes,
            media_type="model/gltf+json",
            headers={
                "Content-Disposition": f"attachment; filename=roomcraft-layout-{rank}.gltf",
                "Cache-Control": "no-cache",
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando glTF: {str(e)}")
