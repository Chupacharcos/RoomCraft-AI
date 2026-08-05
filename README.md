# RoomCraft AI — Optimizador de distribución de habitaciones

Describes una habitación en lenguaje natural («dormitorio de 4×3,5 m con ventana
al sur, cama doble, armario y escritorio») y devuelve **varias distribuciones
optimizadas**, puntuadas por circulación, luz natural y agrupación funcional.

La colocación no la hace un LLM: la resuelve un **recocido simulado** (simulated
annealing) sobre restricciones geométricas reales — que las puertas abran, que
quede paso, que nada se solape. El LLM sólo interpreta el texto de entrada y lo
convierte en medidas y lista de muebles.

**Licencia:** MIT (ver [LICENSE](LICENSE)) — uso libre, incluido comercial,
manteniendo el aviso de copyright. Sin garantía ni soporte incluidos.

## Demo en vivo

[adrianmoreno-dev.com/demo/roomcraft-ai](https://adrianmoreno-dev.com/demo/roomcraft-ai)

## Cómo funciona

```
Texto libre ──► parser (Groq)  ──► {habitación, muebles, aberturas}
                                      │
                            optimizer (recocido simulado)
                                      │
                   ┌──────────────────┼──────────────────┐
                   ▼                  ▼                  ▼
              Plano PDF          Escena glTF      Render fotorrealista
                                                    (Gemini, opcional)
```

El optimizador trabaja **en planta**: cada mueble tiene posición, ancho, fondo y
rotación. Sobre eso se puntúa:

| Criterio | Qué mide |
|---|---|
| Circulación | Que quede paso libre entre muebles y hacia las puertas |
| Luz natural | Que los muebles de uso (escritorio, sofá) aprovechen las ventanas |
| Agrupación | Que lo que se usa junto quede junto (mesita ↔ cama) |
| Conflictos | Solapes y bloqueo de puertas o ventanas |

## Endpoints

Todos bajo el prefijo `/api/roomcraft`:

```
POST /parse               Texto libre → habitación + muebles estructurados
POST /optimize            Genera N distribuciones puntuadas
POST /reoptimize          Recalcula fijando muebles que el usuario ha movido
POST /export-pdf          Plano técnico en PDF
POST /export-gltf         Escena 3D en glTF 2.0
POST /api/render-realistic  Render fotorrealista del plano (Gemini)
GET  /furniture-catalog   Catálogo de muebles con dimensiones estándar
GET  /examples            Ejemplos de entrada
GET  /health
```

Documentación interactiva (OpenAPI/Swagger) en `/docs`.

## Integración, datos y licencia

### Integración

API REST propia (FastAPI) con 10 endpoints. Al ser HTTP+JSON se consume desde
cualquier lenguaje, y el esquema OpenAPI de `/docs` permite generar el cliente
automáticamente.

**Exportación en formatos estándar** — para que el resultado no se quede
encerrado en esta aplicación:

| Formato | Endpoint | Para qué |
|---|---|---|
| **glTF 2.0** (Khronos) | `POST /export-gltf` | Abre sin plugins en Blender, three.js, Babylon.js, Unity, Unreal, el Visor 3D de Windows y la vista previa de macOS/iOS |
| **PDF** | `POST /export-pdf` | Plano técnico acotado, para imprimir o adjuntar |

```bash
curl -X POST http://localhost:8006/api/roomcraft/export-gltf \
     -H 'Content-Type: application/json' \
     -d '{"room":{"width":4.0,"depth":3.5},
          "layout":{"rank":1,"furniture_positions":[
            {"type":"bed_double","x":0.2,"y":0.2,"width":1.6,"depth":2.0,"rotation":0}
          ]}}' -o habitacion.gltf
```

> **Sobre las alturas en el glTF:** el optimizador trabaja en planta, que es lo
> que importa para circulación y colisiones. Para levantar el plano a 3D se
> aplica una tabla de **alturas típicas por tipo de mueble**
> (`core/gltf_export.py::FURNITURE_HEIGHTS`) — es una convención documentada y
> editable, no una medida calculada. El propio fichero glTF lo declara en
> `extras.nota_alturas`.

### Tratamiento de datos

| Qué | Dónde | Cuánto tiempo |
|---|---|---|
| Descripción de la habitación | Se procesa en memoria para la respuesta | No se persiste |
| Layouts generados | Se devuelven al cliente | No se persiste |
| Ficheros PDF/glTF | Se generan al vuelo en la respuesta | No se guardan en disco |

**Qué sale del servidor:** el texto de la descripción se envía a la **API de
Groq** para extraer medidas y muebles. Si se usa `/api/render-realistic`, el
esquema del plano se envía a **Google Gemini** para el render. El optimizador,
el PDF y el glTF son **100 % locales**: no salen de tu servidor.

### Despliegue propio y otros motores

El repositorio es la aplicación completa: FastAPI + systemd, sin dependencias
SaaS más allá de los proveedores LLM citados.

El parser está aislado en `routers/parser.py` (cliente de Groq) y el render en
`services/roomcraft_ai_patch.py` (Gemini). Cambiarlos por OpenAI, Azure OpenAI o
un modelo local es sustituir esa llamada; **el optimizador no usa IA en
absoluto**, así que la parte que produce las distribuciones funciona sin ningún
proveedor externo.

### Costes

El código es gratuito (MIT). Los costes de un despliegue son ajenos al proyecto:
el **motor de IA** para parsear y renderizar (Groq tiene plan gratuito con
límites; Gemini se factura por uso), la **infraestructura** donde se aloje y la
**implantación y mantenimiento**, a cargo de quien lo despliega — el autor no
ofrece soporte ni consultoría.

## Instalación

```bash
python -m venv venv && ./venv/bin/pip install -r requirements.txt

cp .env.example .env      # añadir GROQ_API_KEY y, si se usa el render, GEMINI_API_KEY

./venv/bin/uvicorn app:app --host 127.0.0.1 --port 8006
```

## Stack

| Capa | Tecnología |
|---|---|
| API | FastAPI + Uvicorn |
| Optimización | Recocido simulado propio (`core/annealing.py`) |
| Parsing de texto | Groq |
| Render fotorrealista | Google Gemini (opcional) |
| Exportación | ReportLab (PDF) · glTF 2.0 propio (`core/gltf_export.py`) |
