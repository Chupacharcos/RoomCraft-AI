import time
from fastapi import APIRouter

router = APIRouter()

@router.get('/analyze_space')
def analyze_space():
    # Simulación de análisis de espacio usando un modelo de ML
    time.sleep(2)  # Simula tiempo de procesamiento
    return {'diagnostico': 'El espacio está bien optimizado', 'metricas': {'utilizacion': 0.85, 'eficiencia': 0.90}}