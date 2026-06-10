# SMAT - Sistema de Monitoreo de Alerta Temprana

Proyecto incremental del curso **Desarrollo Basado en Plataformas (2010305)**  
Universidad Nacional Mayor de San Marcos — FISI  

## Estructura del proyecto

SMAT-ECOSYSTEM-2026/
├── backend/        # API REST con FastAPI + SQLite
│   └── app/
│       ├── main.py
│       ├── models.py
│       ├── schemas.py
│       ├── crud.py
│       ├── auth.py
│       └── database.py
├── mobile/         # App móvil con Flutter (Web/Android)
│   └── lib/
│       ├── main.dart
│       ├── models/
│       ├── screens/
│       └── services/
└── iot_device/     # Emulador de sensores IoT
└── sensor_emitter.py

## Requisitos previos

- Python 3.10+
- Flutter SDK 3.4+
- Git

## Cómo levantar el Backend

```bash
# 1. Entrar a la carpeta
cd backend

# 2. Crear y activar el entorno virtual
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Correr el servidor
cd app
uvicorn main:app --reload
```

El servidor estará disponible en: http://127.0.0.1:8000  
Documentación Swagger: http://127.0.0.1:8000/docs

## Cómo correr el Mobile

```bash
# 1. Entrar a la carpeta
cd mobile

# 2. Instalar dependencias
flutter pub get

# 3. Correr en Chrome (puerto fijo)
flutter run -d chrome --web-port 8080
```

> Asegúrate de tener el backend corriendo antes de iniciar el mobile.

## Cómo correr el IoT

```bash
# 1. Entrar a la carpeta
cd iot_device

# 2. Instalar dependencias
pip install requests

# 3. Para ejecutar el emisor aplicamos
python sensor_emitter.py
```

> El script obtiene el token automáticamente y envía lecturas cada 10s en modo normal y cada 2s en modo emergencia (valor > 70 cm).

## Flujo de uso

1. Levantar el backend
2. Abrir la app mobile en Chrome
3. Iniciar sesión (cualquier usuario/contraseña)
4. Crear una estación desde la app
5. Correr el emisor IoT — las lecturas aparecerán en la base de datos
6. Refrescar la lista en la app para ver los cambios

## Tecnologías usadas

| Capa | Tecnología |
|------|-----------|
| Backend | Python, FastAPI, SQLAlchemy, SQLite, JWT |
| Mobile | Flutter, Dart, HTTP, SharedPreferences |
| IoT | Python, Requests |
| Control de versiones | Git, GitHub |