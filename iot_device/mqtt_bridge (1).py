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
# ─────────────────────────────────────────────


# ── Estado global (thread-safe con Lock) ────────────────────────────────────
_lock            = threading.Lock()
last_seen: dict  = {}          # {estacion_id: timestamp}
TOKEN: str       = ""
token_timestamp  = 0.0
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


# ── Callbacks MQTT ───────────────────────────────────────────────────────────

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[BRIDGE] Conectado al broker '{BROKER}'.")
        client.subscribe(TOPIC)
        print(f"[BRIDGE] Suscrito a '{TOPIC}'. Esperando mensajes...\n")
    else:
        print(f"[BRIDGE ERROR] No se pudo conectar al broker (rc={rc}).")
        sys.exit(1)


def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"[BRIDGE] Desconexión inesperada (rc={rc}). Reconectando...")


def on_message(client, userdata, msg):
    """Recibe un mensaje MQTT y lo reenvía al backend via HTTP POST."""
    global TOKEN, token_timestamp

    refrescar_token_si_necesario()

    try:
        # 1. Decodificar el mensaje
        payload = json.loads(msg.payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"[ERROR] No se pudo decodificar el mensaje de '{msg.topic}': {e}")
        return

    print(f"[MQTT] Recibido en '{msg.topic}': {payload}")

    # 2. Extraer el ID de la estación desde el tópico  (fisi/smat/estaciones/<id>)
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

    # 5. Construir el body que espera el backend (schemas.LecturaCreate)
    data_to_send = {
        "valor": payload["valor"],
        "estacion_id": estacion_id
    }

    # 6. Enviar al backend
    with _lock:
        token_actual = TOKEN

    headers = {"Authorization": f"Bearer {token_actual}"}
    try:
        response = requests.post(API_URL, json=data_to_send, headers=headers, timeout=5)

        if response.status_code in (200, 201):
            print(f"[OK] Estación {estacion_id} → {payload['valor']} cm guardados en DB.")

        elif response.status_code == 401:
            print("[AUTH] Token expirado o inválido. Renovando de inmediato...")
            nuevo = obtener_token()
            if nuevo:
                with _lock:
                    TOKEN = nuevo
                    token_timestamp = time.time()
                # Reintentar una vez con el nuevo token
                headers["Authorization"] = f"Bearer {nuevo}"
                r2 = requests.post(API_URL, json=data_to_send, headers=headers, timeout=5)
                if r2.status_code in (200, 201):
                    print(f"[OK] Reintento exitoso — Estación {estacion_id}.")
                else:
                    print(f"[ERROR] Reintento falló: HTTP {r2.status_code}")
            else:
                print("[CRÍTICO] No se pudo renovar el token.")

        elif response.status_code == 404:
            print(f"[ERROR 404] La estación {estacion_id} no existe en la BD. "
                  "Créala desde la app móvil.")

        else:
            print(f"[ERROR] API respondió HTTP {response.status_code}: {response.text}")

    except requests.exceptions.ConnectionError:
        print(f"[CRÍTICO] Sin conexión con el backend al procesar estación {estacion_id}.")
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
                print(f"[OFFLINE] ⚠  Estación {estacion_id} sin datos hace {sin_datos}s — "
                      "posiblemente OFFLINE.")


# ── Entry point ───────────────────────────────────────────────────────────────

def iniciar_bridge():
    global TOKEN, token_timestamp

    print("=== SMAT MQTT Bridge ===")
    print(f"    Broker  : {BROKER}:{PORT}")
    print(f"    Tópico  : {TOPIC}")
    print(f"    Backend : {API_URL}\n")

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

    # Configurar cliente MQTT
    client = mqtt.Client(client_id="smat-mqtt-bridge")
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
        client.loop_forever()   # Bloqueante; maneja reconexión automática
    except KeyboardInterrupt:
        print("\n[BRIDGE] Detenido por el usuario.")
    finally:
        client.disconnect()
        print("[BRIDGE] Desconectado del broker.")


if __name__ == "__main__":
    iniciar_bridge()
