from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class WallSide(str, Enum):
    N = "N"
    S = "S"
    E = "E"
    W = "W"


class OpeningType(str, Enum):
    door = "door"
    window = "window"


class OpeningPos(str, Enum):
    left = "left"
    center = "center"
    right = "right"
    float = "float"


class Opening(BaseModel):
    wall: WallSide
    type: OpeningType
    width: float = Field(..., gt=0, le=5)
    pos: OpeningPos = OpeningPos.center
    offset: Optional[float] = None  # metros desde extremo izquierdo de la pared


class FurnitureType(str, Enum):
    bed_single = "bed_single"
    bed_double = "bed_double"
    nightstand = "nightstand"
    wardrobe = "wardrobe"
    wardrobe_sliding = "wardrobe_sliding"
    desk = "desk"
    chair = "chair"
    sofa = "sofa"
    sofa_3 = "sofa_3"
    armchair = "armchair"
    tv_stand = "tv_stand"
    coffee_table = "coffee_table"
    dining_table = "dining_table"
    bookshelf = "bookshelf"
    dresser = "dresser"
    plant = "plant"
    printer = "printer"
    meeting_table = "meeting_table"


class Furniture(BaseModel):
    type: FurnitureType
    width: float = Field(..., gt=0)
    depth: float = Field(..., gt=0)
    qty: int = Field(default=1, ge=1, le=6)
    label: Optional[str] = None


class Room(BaseModel):
    width: float = Field(..., gt=1, le=20, description="metros")
    depth: float = Field(..., gt=1, le=20, description="metros")
    height: float = Field(default=2.5, gt=1.5, le=5)
    openings: List[Opening] = []
    furniture: List[Furniture] = []
    warning: Optional[str] = None
