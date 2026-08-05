from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from services import generate_realistic_image

router = APIRouter()

class RenderRealisticRequest(BaseModel):
    png_base64: str
    style: str = "scandinavian"

@router.post("/api/render-realistic")
async def render_realistic(request: RenderRealisticRequest):
    try:
        image_base64 = generate_realistic_image(request.png_base64, request.style)
        return JSONResponse(content=jsonable_encoder({"image": image_base64}), media_type="application/json")
    except Exception as e:
        return JSONResponse(content=jsonable_encoder({"error": str(e)}), status_code=500, media_type="application/json")