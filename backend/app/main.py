from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from app import models, schemas, crud
from app.database import engine, get_db
from sqlalchemy import func
from app.auth import crear_token_acceso, obtener_identidad_actual  

# Crear tablas en la DB
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SMAT - Backend Profesional",
    description="""
    API robusta para la gestión y monitoreo de desastres naturales.
    Permite la telemetría de sensores en tiempo real y el cálculo de niveles de riesgo.
    **Entidades principales:**
    * **Estaciones:** Puntos de monitoreo físico.
    * **Lecturas:** Datos capturados por sensores.
    * **Riesgos:** Análisis de criticidad basado en umbrales.
    """,
    version="1.0.0",
    terms_of_service="http://unmsm.edu.pe/terms/",
    contact={
    "name": "Soporte Técnico SMAT - FISI",
    "url": "http://fisi.unmsm.edu.pe",
    "email": "desarrollo.smat@unmsm.edu.pe",
    },
    license_info={
    "name": "Apache 2.0",
    "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
    )
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# ENDPOINTS
# =========================

# Crear estación
@app.post("/estaciones/", status_code=201, tags=["Infraestructura"])
def crear_estacion(
    estacion: schemas.EstacionCreate,
    db: Session = Depends(get_db),
    usuario: str = Depends(obtener_identidad_actual) # PROTECCIÓN JWT
):
    return crud.crear_estacion(db=db, estacion=estacion)


# Registrar lectura
@app.post(
    "/lecturas/",
    status_code=201,
    tags=["Telemetría de Sensores"],
    summary="Recibir datos de telemetría",
    description="Recibe datos de sensores y valida integridad."
)
def registrar_lectura(
    lectura: schemas.LecturaCreate,
    db: Session = Depends(get_db),
    usuario: str = Depends(obtener_identidad_actual)  # 🔐 JWT
):
    estacion_db = db.query(models.EstacionDB).filter(
        models.EstacionDB.id == lectura.estacion_id
    ).first()

    if not estacion_db:
        raise HTTPException(
            status_code=404,
            detail="Error de Integridad: La estación no existe en la base de datos."
        )

    return crud.crear_lectura(db, lectura)


# Listar estaciones
@app.get(
    "/estaciones/",
    tags=["Gestión de Infraestructura"],
    summary="Listar estaciones registradas",
    description="Devuelve todas las estaciones almacenadas en la base de datos en formato JSON."
)
def listar_estaciones(db: Session = Depends(get_db)):
    return crud.obtener_estaciones(db)


# Historial de lecturas
@app.get(
    "/estaciones/{id}/historial",
    tags=["Reportes Históricos"],
    summary="Obtener historial de lecturas",
    description="Devuelve todas las lecturas de una estación, incluyendo el conteo total y el promedio de valores registrados.",
    responses={404: {"description": "Estación no encontrada"}}
)
def historial(id: int, db: Session = Depends(get_db)):
    estacion = crud.get_estacion(db, id)

    if not estacion:
        raise HTTPException(status_code=404, detail="Estación no encontrada")

    return crud.get_historial(db, id)


#obtener riesgo
@app.get(
    "/estaciones/{id}/riesgo",
    tags=["Análisis de Riesgo"],
    summary="Evaluar nivel de peligro actual",
    description="Analiza la última lectura recibida de una estación y determina si el estado es NORMAL, ALERTA o PELIGRO.",
    responses={404: {"description": "Estación no encontrada"}}
)
def obtener_riesgo(id: int, db: Session = Depends(get_db)):
    estacion = crud.get_estacion(db, id)

    if not estacion:
        raise HTTPException(status_code=404, detail="Estación no encontrada")

    return crud.calcular_riesgo(db, id)


#reporte critico
@app.get(
    "/reportes/criticos",
    tags=["Auditoría"],
    summary="Reporte de estaciones críticas",
    description="Devuelve estaciones cuya última lectura supera un umbral definido. El parámetro opcional 'umbral' permite ajustar el nivel mínimo de alerta (por defecto 20.0)."
)
def reporte_criticos(umbral: float = 20.0, db: Session = Depends(get_db)):
    return crud.get_estaciones_criticas(db, umbral)


#stats
@app.get(
    "/estaciones/stats",
    tags=["Reportes Históricos"],
    summary="Resumen general del sistema",
    description="Proporciona un resumen ejecutivo del sistema SMAT, incluyendo número total de estaciones, total de lecturas y el valor máximo registrado."
)
def stats(db: Session = Depends(get_db)):

    return crud.obtener_estadisticas(db)


# Endpoint para obtener el Token (Simulación de Login)
@app.post("/token", tags=["Seguridad"])
async def login_para_obtener_token():
# En la Unidad II esto validará contra la tabla de usuarios
    return {"access_token": crear_token_acceso({"sub": "admin_smat"}), "token_type": "bearer"}