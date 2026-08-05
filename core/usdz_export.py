"""
Exportador de layouts a USDZ (Universal Scene Description, empaquetado Apple).

USDZ es el formato que abre Quick Look en iOS y macOS: al recibir el fichero, un
iPhone lo previsualiza y ofrece «Ver en tu espacio» en realidad aumentada, sin
instalar nada. Es lo que usan Ikea, Wayfair o Apple en sus fichas de producto, y
el complemento natural del glTF (que cubre web y escritorio).

La escena se construye con **OpenUSD**, la implementación de referencia de
Pixar, y se empaqueta con `UsdUtils.CreateNewUsdzPackage`, la ruta oficial: así
la alineación de 64 bytes y el orden interno del ZIP que exige la spec los
resuelve la propia librería, no un empaquetador casero.

`usd-core` es una **dependencia opcional** (~150 MB): sólo hace falta para este
exportador. Si no está instalada, el resto del proyecto funciona igual y el
endpoint devuelve 503 explicando cómo instalarla.

Alturas: como en el exportador glTF, el optimizador trabaja en planta y la
altura sale de la tabla `FURNITURE_HEIGHTS` de `gltf_export.py` — misma
convención documentada, para que ambos formatos coincidan.
"""
from __future__ import annotations

import math
import tempfile
from pathlib import Path

from core.gltf_export import (
    DEFAULT_COLOR,
    DEFAULT_HEIGHT,
    FLOOR_COLOR,
    FLOOR_THICKNESS,
    FURNITURE_COLORS,
    FURNITURE_HEIGHTS,
)


class UsdNotAvailable(RuntimeError):
    """usd-core no está instalado en el entorno."""


def _safe_name(text: str, fallback: str) -> str:
    """Nombre de prim válido en USD: sólo alfanuméricos y '_', sin empezar por dígito."""
    out = [c if (c.isalnum() or c == "_") else "_" for c in str(text)]
    name = "".join(out).strip("_") or fallback
    if name[0].isdigit():
        name = f"_{name}"
    return name


def layout_to_usdz_bytes(room: dict, layout: list[dict], name: str = "RoomCraft") -> bytes:
    """Devuelve el contenido binario de un .usdz con la habitación y sus muebles.

    Lanza UsdNotAvailable si falta usd-core.
    """
    try:
        from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdUtils
    except ImportError as e:  # pragma: no cover - depende del entorno
        raise UsdNotAvailable(
            "Falta 'usd-core' (pip install usd-core). Es una dependencia opcional "
            "usada sólo por el exportador USDZ."
        ) from e

    room_w = float(room.get("width", 0))
    room_d = float(room.get("depth", 0))

    with tempfile.TemporaryDirectory() as tmp:
        stage_path = str(Path(tmp) / "scene.usdc")
        stage = Usd.Stage.CreateNew(stage_path)

        # Y arriba y unidades en metros: es lo que espera Quick Look para que la
        # escala en AR sea la real.
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)

        root = UsdGeom.Xform.Define(stage, "/Root")
        stage.SetDefaultPrim(root.GetPrim())

        materials_scope = UsdGeom.Scope.Define(stage, "/Root/Materials")
        material_cache: dict[str, object] = {}

        def get_material(key: str, rgb: list[float]):
            """Material PBR reutilizable por tipo de mueble."""
            if key in material_cache:
                return material_cache[key]
            mat_path = f"{materials_scope.GetPath()}/{_safe_name(key, 'mat')}"
            material = UsdShade.Material.Define(stage, mat_path)
            shader = UsdShade.Shader.Define(stage, f"{mat_path}/Shader")
            shader.CreateIdAttr("UsdPreviewSurface")
            shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
                Gf.Vec3f(rgb[0], rgb[1], rgb[2])
            )
            shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.8)
            shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
            material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
            material_cache[key] = material
            return material

        def add_box(prim_path: str, center: tuple[float, float, float],
                    size: tuple[float, float, float], rot_y: float, mat) -> None:
            """Un cubo unitario escalado: misma geometría que el exportador glTF."""
            xform = UsdGeom.Xform.Define(stage, prim_path)
            xform.AddTranslateOp().Set(Gf.Vec3d(*center))
            if rot_y:
                xform.AddRotateYOp().Set(float(rot_y))
            xform.AddScaleOp().Set(Gf.Vec3f(*size))

            cube = UsdGeom.Cube.Define(stage, f"{prim_path}/Geom")
            # UsdGeom.Cube por defecto mide 2 unidades: con size=1 va de -0.5 a
            # 0.5, así la escala del Xform equivale a las medidas reales.
            cube.CreateSizeAttr(1.0)
            cube.CreateExtentAttr([Gf.Vec3f(-0.5, -0.5, -0.5), Gf.Vec3f(0.5, 0.5, 0.5)])
            UsdShade.MaterialBindingAPI.Apply(cube.GetPrim()).Bind(mat)

        # Suelo
        add_box("/Root/Suelo",
                (room_w / 2, -FLOOR_THICKNESS / 2, room_d / 2),
                (room_w, FLOOR_THICKNESS, room_d),
                0.0, get_material("floor", FLOOR_COLOR))

        usados: dict[str, int] = {}
        for item in layout:
            ftype = item.get("type", "unknown")
            h = FURNITURE_HEIGHTS.get(ftype, DEFAULT_HEIGHT)
            w = float(item.get("width", 0.5))
            d = float(item.get("depth", 0.5))
            rot = float(item.get("rotation", 0) or 0)
            cx = float(item.get("x", 0)) + w / 2
            cz = float(item.get("y", 0)) + d / 2

            base = _safe_name(item.get("label") or ftype, "Mueble")
            usados[base] = usados.get(base, 0) + 1
            prim_name = base if usados[base] == 1 else f"{base}_{usados[base]}"

            add_box(f"/Root/{prim_name}", (cx, h / 2, cz), (w, h, d), rot,
                    get_material(ftype, FURNITURE_COLORS.get(ftype, DEFAULT_COLOR)))

        stage.GetRootLayer().Save()

        usdz_path = str(Path(tmp) / "scene.usdz")
        # Ruta oficial de empaquetado: resuelve alineación y orden del ZIP.
        if not UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(stage_path), usdz_path):
            raise RuntimeError("CreateNewUsdzPackage falló al empaquetar la escena")
        return Path(usdz_path).read_bytes()
