"""PDF export endpoint."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Dict, Any, List
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
