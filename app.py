"""RoomCraft AI — FastAPI entry point. Port 8006."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import parser, optimizer, exporter, catalog

app = FastAPI(
    title="RoomCraft AI",
    description="Layout Optimizer & 3D Room Planner API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api/roomcraft"

app.include_router(parser.router,    prefix=PREFIX, tags=["parser"])
app.include_router(optimizer.router, prefix=PREFIX, tags=["optimizer"])
app.include_router(exporter.router,  prefix=PREFIX, tags=["exporter"])
app.include_router(catalog.router,   prefix=PREFIX, tags=["catalog"])


@app.get("/")
async def root():
    return {"service": "RoomCraft AI", "version": "1.0.0", "status": "running"}
