import os
import base64
from io import BytesIO
from typing import Optional

from google import genai
from google.genai import types
from PIL import Image

_client: Optional[genai.Client] = None

def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY no configurada en entorno")
        _client = genai.Client(api_key=api_key)
    return _client

PROMPT_TEMPLATE = (
    "Convert this 3D schematic room layout into a photorealistic "
    "interior design render. CRITICAL: keep the exact same furniture "
    "positions, orientations and proportions as in the input image. "
    "Do not add or remove any furniture. Apply the following style: "
    "{style}. Natural lighting from windows, realistic materials, "
    "architectural visualization quality, 4K detail, professional "
    "interior photography, wide-angle lens."
)

STYLES = {
    "scandinavian": "Scandinavian style, light wood, minimalistic",
    # Añade más estilos aquí...
}

def generate_realistic_image(png_base64: str, style: str = "scandinavian") -> str:
    client = _get_client()
    model = client.models.get("gemini-2.5-flash")
    prompt = PROMPT_TEMPLATE.format(style=STYLES[style])
    image_data = BytesIO(base64.b64decode(png_base64))
    image = Image.open(image_data)
    response = model.generate_content(
        prompt,
        image=image,
        stream=True,
    )
    image_data = BytesIO()
    for chunk in response:
        image_data.write(chunk)
    image_data.seek(0)
    return base64.b64encode(image_data.read()).decode()