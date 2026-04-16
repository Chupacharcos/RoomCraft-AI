from pydantic import BaseModel
from typing import List, Optional, Dict


class Position(BaseModel):
    type: str
    x: float
    y: float
    rotation: int  # 0, 90, 180, 270
    width: float
    depth: float
    label: Optional[str] = None


class ScoreBreakdown(BaseModel):
    circulation: float    # max 40
    natural_light: float  # max 30
    ergonomics: float     # max 20
    aesthetics: float     # max 10


class Metrics(BaseModel):
    min_clearance_cm: int
    light_coverage_pct: float
    conflicts: int


class Layout(BaseModel):
    rank: int
    score: float
    highlight: str
    score_breakdown: ScoreBreakdown
    warnings: List[str]
    furniture_positions: List[Position]
    metrics: Metrics
