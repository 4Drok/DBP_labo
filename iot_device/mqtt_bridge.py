import paho.mqtt.client as mqtt
import requests
import json
import time
import threading
import sys

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────
BROKER    = "broker.hivemq.com"
PORT      = 1883
TOPIC     = "fisi/smat/estaciones/#"   # Escucha TODAS las estaciones

API_URL   = "http://127.0.0.1:8000/lecturas/"
TOKEN_URL = "http://127.0.0.1:8000/token"

OFFLINE_TIMEOUT        = 30    # segundos sin datos → considerar estación OFFLINE
OFFLINE_CHECK_INTERVAL = 10    # cada cuántos segundos revisar el estado
TOKEN_REFRESH_SECONDS  = 25 * 60   # renovar token cada 25 min (expira en 30)

# ── Parámetros del Deadband Filter (Reto Semana 11) ─────────────────────────
DEADBAND_PORCENTAJE = 0.05   # 5%  → solo ingestar si el cambio supera este umbral
DEADBAND_TIMEOUT    = 60     # segundos → forzar inserción mínima cada 60s (heartbeat)
# ────────────────────────────────────────────────────────────────────────────


# ── Estado global (thread-safe con Lock) ────────────────────────────────────
_lock            = threading.Lock()
last_seen: dict  = {}          # {estacion_id: timestamp}
TOKEN: str       = ""
token_timestamp  = 0.0

# Caché del Deadband Filter
# Estructura: { estacion_id: {"valor": float, "timestamp": float} }
deadband_cache: dict = {}
# ────────────────────────────────────────────────────────────────────────────


def obtener_token() -> str | None:
    """Solicita un JWT al backend SMAT. No requiere credenciales."""
    try:
        response = requests.post(TOKEN_URL, timeout=5)
        response.raise_for_status()
        token = response.json()["access_token"]
        print("[AUTH] Token obtenido correctamente.")
        return token
    except requests.exceptions.ConnectionError:
        print("[AUTH CRÍTICO] Sin conexión con el backend. ¿Está corriendo?")
    except requests.exceptions.HTTPError as e:
        print(f"[AUTH ERROR] HTTP {e.response.status_code}")
    except Exception as e:
        print(f"[AUTH CRÍTICO] Error inesperado: {e}")
    return None


def refrescar_token_si_necesario():
    """Renueva el token de forma proactiva antes de que expire."""
    global TOKEN, token_timestamp
    with _lock:
        if time.time() - token_timestamp >= TOKEN_REFRESH_SECONDS:
            nuevo = obtener_token()
            if nuevo:
                TOKEN = nuevo
                token_timestamp = time.time()


def debe_ingestar(estacion_id: int, nuevo_valor: float) -> tuple[bool, str]:
    """
    Lógica del Deadband Filter (Reto Semana 11).

    Retorna (True, motivo) si el dato debe enviarse a la API,
    o (False, motivo) si debe bloquearse para evitar escrituras redundantes.

    Criterios para INGESTAR:
      1. Primera lectura de esta estación (no hay entrada en caché).
      2. El nuevo valor varía más de ±5% respecto al último valor guardado.
      3. Han pasado más de 60 segundos desde la última inserción (heartbeat mínimo).
    """
    with _lock:
        entrada = deadband_cache.get(estacion_id)

    if entrada is None:
        return True, "Primera lectura — sin caché previa"

    ultimo_valor     = entrada["valor"]
    ultimo_timestamp = entrada["timestamp"]
    ahora            = time.time()

    # Criterio 3: heartbeat mínimo de 60 segundos
    segundos_desde_ultima = ahora - ultimo_timestamp
    if segundos_desde_ultima >= DEADBAND_TIMEOUT:
        return True, f"Heartbeat: {int(segundos_desde_ultima)}s sin inserción"

    # Criterio 2: cambio de ±5%
    if ultimo_valor != 0:
        variacion = abs(nuevo_valor - ultimo_valor) / abs(ultimo_valor)
    else:
        variacion = abs(nuevo_valor)

    if variacion > DEADBAND_PORCENTAJE:
        return True, f"Cambio significativo: {variacion*100:.2f}% > {DEADBAND_PORCENTAJE*100:.0f}%"

    return False, f"Filtrado: cambio {variacion*100:.2f}% <= {DEADBAND_PORCENTAJE*100:.0f}% y solo {int(segundos_desde_ultima)}s desde última inserción"


def actualizar_cache(estacion_id: int, valor: float):
    """Actualiza la caché del deadband tras una inserción exitosa en la DB."""
    with _lock:
        deadband_cache[estacion_id] = {
            "valor":     valor,
            "timestamp": time.time()
        }


# ── Callbacks MQTT (VERSION2) ────────────────────────────────────────────────

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"[BRIDGE] Conectado al broker '{BROKER}'.")
        client.subscribe(TOPIC)
        print(f"[BRIDGE] Suscrito a '{TOPIC}'. Esperando mensajes...\n")
    else:
        print(f"[BRIDGE ERROR] No se pudo conectar al broker (rc={reason_code}).")
        sys.exit(1)


def on_disconnect(client, userdata, flags, reason_code, properties):
    if reason_code != 0:
        print(f"[BRIDGE] Desconexión inesperada (rc={reason_code}). Reconectando...")


def on_message(client, userdata, msg):
    """Recibe un mensaje MQTT, aplica el Deadband Filter y reenvía a FastAPI si procede."""
    global TOKEN, token_timestamp

    refrescar_token_si_necesario()

    # 1. Decodificar el mensaje
    try:
        payload = json.loads(msg.payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"[ERROR] No se pudo decodificar el mensaje de '{msg.topic}': {e}")
        return

    print(f"[MQTT] Recibido en '{msg.topic}': {payload}")

    # 2. Extraer el ID de la estación desde el tópico (fisi/smat/estaciones/<id>)
    try:
        estacion_id = int(msg.topic.split("/")[-1])
    except ValueError:
        print(f"[ERROR] No se pudo extraer estacion_id del tópico '{msg.topic}'.")
        return

    # 3. Registrar cuándo se vio por última vez esta estación
    with _lock:
        last_seen[estacion_id] = time.time()

    # 4. Validar que el campo requerido esté presente
    if "valor" not in payload:
        print(f"[ERROR] El mensaje de estación {estacion_id} no contiene 'valor'. Ignorado.")
        return

    try:
        nuevo_valor = float(payload["valor"])
    except (TypeError, ValueError):
        print(f"[ERROR] El campo 'valor' no es numérico: {payload['valor']}. Ignorado.")
        return

    # 5. ── DEADBAND FILTER (Reto Semana 11) ──────────────────────────────────
    ingestar, motivo = debe_ingestar(estacion_id, nuevo_valor)

    if not ingestar:
        print(f"[FILTRO BLOQUEADO] Estacion {estacion_id} | {nuevo_valor} cm -> {motivo}")
        return   # No se hace ningún HTTP POST

    print(f"[FILTRO PERMITIDO] Estacion {estacion_id} | {nuevo_valor} cm -> {motivo}")
    # ─────────────────────────────────────────────────────────────────────────

    # 6. Construir el body que espera el backend (schemas.LecturaCreate)
    data_to_send = {
        "valor":       nuevo_valor,
        "estacion_id": estacion_id
    }

    # 7. Enviar al backend vía HTTP POST con JWT
    with _lock:
        token_actual = TOKEN

    headers = {"Authorization": f"Bearer {token_actual}"}
    try:
        response = requests.post(API_URL, json=data_to_send, headers=headers, timeout=5)

        if response.status_code in (200, 201):
            print(f"[DB OK] Estacion {estacion_id} -> {nuevo_valor} cm guardados en DB.")
            actualizar_cache(estacion_id, nuevo_valor)

        elif response.status_code == 401:
            print("[AUTH] Token expirado o inválido. Renovando de inmediato...")
            nuevo = obtener_token()
            if nuevo:
                with _lock:
                    TOKEN = nuevo
                    token_timestamp = time.time()
                headers["Authorization"] = f"Bearer {nuevo}"
                r2 = requests.post(API_URL, json=data_to_send, headers=headers, timeout=5)
                if r2.status_code in (200, 201):
                    print(f"[OK] Reintento exitoso — Estacion {estacion_id}.")
                    actualizar_cache(estacion_id, nuevo_valor)
                else:
                    print(f"[ERROR] Reintento falló: HTTP {r2.status_code}")
            else:
                print("[CRÍTICO] No se pudo renovar el token.")

        elif response.status_code == 404:
            print(f"[ERROR 404] La estacion {estacion_id} no existe en la BD. "
                  "Créala desde la app móvil.")

        else:
            print(f"[ERROR] API respondió HTTP {response.status_code}: {response.text}")

    except requests.exceptions.ConnectionError:
        print(f"[CRÍTICO] Sin conexión con el backend al procesar estacion {estacion_id}.")
    except Exception as e:
        print(f"[CRÍTICO] Error inesperado al reenviar a la API: {e}")


# ── Hilo: detectar estaciones OFFLINE ────────────────────────────────────────

def monitor_offline():
    """Hilo daemon que alerta cuando una estación deja de enviar datos."""
    while True:
        time.sleep(OFFLINE_CHECK_INTERVAL)
        ahora = time.time()
        with _lock:
            snapshot = dict(last_seen)

        for estacion_id, ultimo in snapshot.items():
            sin_datos = int(ahora - ultimo)
            if sin_datos > OFFLINE_TIMEOUT:
                print(f"[OFFLINE] Estacion {estacion_id} sin datos hace {sin_datos}s — "
                      "posiblemente OFFLINE.")


# ── Entry point ───────────────────────────────────────────────────────────────

def iniciar_bridge():
    global TOKEN, token_timestamp

    print("=== SMAT MQTT Bridge — con Deadband Filter ===")
    print(f"    Broker        : {BROKER}:{PORT}")
    print(f"    Tópico        : {TOPIC}")
    print(f"    Backend       : {API_URL}")
    print(f"    Filtro umbral : +/-{DEADBAND_PORCENTAJE*100:.0f}%  |  Heartbeat: {DEADBAND_TIMEOUT}s\n")

    # Obtener token inicial
    token = obtener_token()
    if not token:
        print("[CRÍTICO] No se puede iniciar sin token. ¿Está el backend corriendo?")
        sys.exit(1)

    with _lock:
        TOKEN = token
        token_timestamp = time.time()

    # Lanzar monitor offline como hilo daemon
    threading.Thread(target=monitor_offline, daemon=True, name="monitor-offline").start()

    # Configurar cliente MQTT con VERSION2
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="smat-mqtt-bridge")
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_message    = on_message

    print("[BRIDGE] Conectando al broker MQTT...")
    try:
        client.connect(BROKER, PORT, keepalive=60)
    except Exception as e:
        print(f"[BRIDGE CRÍTICO] No se pudo conectar al broker: {e}")
        sys.exit(1)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[BRIDGE] Detenido por el usuario.")
    finally:
        client.disconnect()
        print("[BRIDGE] Desconectado del broker.")


if __name__ == "__main__":
    iniciar_bridge()