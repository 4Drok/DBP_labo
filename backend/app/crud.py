from app import models
from sqlalchemy import func

def crear_estacion(db, estacion):
    nueva = models.EstacionDB(**estacion.model_dump())
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return {
        "id": nueva.id,
        "nombre": nueva.nombre,
        "ubicacion": nueva.ubicacion
    }

def obtener_estaciones(db):
    return db.query(models.EstacionDB).all()

def crear_lectura(db, lectura):
    nueva = models.LecturaDB(**lectura.model_dump())
    db.add(nueva)
    db.commit()
    return nueva

def get_historial(db, estacion_id):
    lecturas = db.query(models.LecturaDB)\
        .filter(models.LecturaDB.estacion_id == estacion_id)\
        .all()

    if not lecturas:
        return {
            "lecturas": [],
            "conteo": 0,
            "promedio": 0
        }

    valores = [l.valor for l in lecturas]
    promedio = sum(valores) / len(valores)

    return {
        "lecturas": [
            {
                "valor": l.valor,
                "estacion_id": l.estacion_id
            }
            for l in lecturas
        ],
        "conteo": len(lecturas),
        "promedio": promedio
    }

def get_estacion(db, estacion_id):
    return db.query(models.EstacionDB)\
        .filter(models.EstacionDB.id == estacion_id)\
        .first()

def calcular_riesgo(db, estacion_id):
    ultima = db.query(models.LecturaDB)\
        .filter(models.LecturaDB.estacion_id == estacion_id)\
        .order_by(models.LecturaDB.id.desc())\
        .first()

    if not ultima:
        return {"nivel": "SIN DATOS", "valor": 0}

    valor = ultima.valor

    if valor > 20:
        nivel = "PELIGRO"
    elif valor > 10:
        nivel = "ALERTA"
    else:
        nivel = "NORMAL"

    return {"nivel": nivel, "valor": valor}

def get_estaciones_criticas(db, umbral: float):
    estaciones = db.query(models.EstacionDB).all()
    resultado = []

    for e in estaciones:
        lecturas = db.query(models.LecturaDB)\
            .filter(models.LecturaDB.estacion_id == e.id)\
            .all()

        if lecturas:
            ultima = lecturas[-1].valor
            if ultima > umbral:
                resultado.append({
                    "estacion_id": e.id,
                    "nombre": e.nombre,
                    "valor": ultima
                })

    return {
        "umbral": umbral,
        "estaciones_criticas": resultado
    }

def obtener_estadisticas(db):
    total_estaciones = db.query(func.count(models.EstacionDB.id)).scalar()
    total_lecturas = db.query(func.count(models.LecturaDB.id)).scalar()

    max_lectura = db.query(models.LecturaDB)\
        .order_by(models.LecturaDB.valor.desc())\
        .first()

    return {
        "total_estaciones": total_estaciones,
        "total_lecturas": total_lecturas,
        "maximo": {
            "estacion_id": max_lectura.estacion_id if max_lectura else None,
            "valor": max_lectura.valor if max_lectura else 0
        }
    }