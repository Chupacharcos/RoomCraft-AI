"""Parser endpoint: text → structured room JSON via Groq Llama."""
import json
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from groq import Groq

router = APIRouter()

SYSTEM_PROMPT = """Eres un asistente de arquitectura de interiores. Tu única tarea es
convertir la descripción de una habitación en JSON estructurado.
Responde SOLO con JSON válido, sin texto adicional, sin markdown.

Formato de salida requerido:
{
  "room": {"width": float_metros, "depth": float_metros, "height": float_metros},
  "openings": [{"wall": "N|S|E|W", "type": "door|window", "width": float_metros, "pos": "left|center|right|float"}],
  "furniture": [{"type": "bed_single|bed_double|nightstand|wardrobe|wardrobe_sliding|desk|chair|sofa|sofa_3|armchair|tv_stand|coffee_table|dining_table|bookshelf|dresser|plant|printer|meeting_table", "width": float_metros, "depth": float_metros, "qty": int}]
}

Reglas:
- Si no se menciona altura de techo, asume 2.5m.
- Si no se menciona orientación de puerta, asume pared sur.
- Convierte pies a metros si es necesario (1 pie = 0.305m).
- Si hay muebles que no caben (suma mayor que área útil), incluye "warning": "Los muebles X no caben".
- bed_single: 0.9x2.0m | bed_double: 1.6x2.0m | nightstand: 0.5x0.4m | wardrobe: 1.8x0.6m | wardrobe_sliding: 1.8x0.6m | desk: 1.2x0.6m | chair: 0.6x0.6m | sofa: 2.0x0.9m | sofa_3: 2.2x0.9m | armchair: 0.8x0.8m | tv_stand: 1.5x0.4m | coffee_table: 1.0x0.5m | dining_table: 1.6x0.9m | bookshelf: 0.8x0.3m | dresser: 1.0x0.5m | plant: 0.4x0.4m | printer: 0.5x0.4m | meeting_table: 1.4x0.7m
"""


class ParseRequest(BaseModel):
    text: str


@router.post("/parse")
async def parse_room(req: ParseRequest):
    if not req.text or len(req.text.strip()) < 5:
        raise HTTPException(status_code=400, detail="Descripción demasiado corta")

    client = Groq(api_key=os.getenv('GROQ_API_KEY'))
    try:
        response = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': req.text}
            ],
            temperature=0.1,
            max_tokens=800,
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace('```json', '').replace('```', '').strip()
        parsed = json.loads(raw)
        return parsed
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"No se pudo parsear la respuesta del modelo: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error del servicio IA: {str(e)}")
