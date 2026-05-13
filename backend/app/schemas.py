from pydantic import BaseModel

class EstacionCreate(BaseModel):
    nombre: str
    ubicacion: str

class LecturaCreate(BaseModel):
    estacion_id: int
    valor: float