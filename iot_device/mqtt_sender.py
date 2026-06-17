import paho.mqtt.client as mqtt
import json
import time
import random
import sys

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────
BROKER     = "broker.hivemq.com"
PORT       = 1883
ESTACION_ID = 1           # Cambia por el ID de tu estación (debe existir en la BD)
TOPIC      = f"fisi/smat/estaciones/{ESTACION_ID}"

INTERVALO_NORMAL    = 10   # segundos en modo normal
INTERVALO_EMERGENCIA = 2   # segundos cuando valor > 70 cm
UMBRAL_ALERTA       = 70.0
# ─────────────────────────────────────────────


def leer_sensor_emulado() -> float:
    """Simula una lectura de nivel de río entre 10.5 y 85.0 cm."""
    return round(random.uniform(10.5, 85.0), 2)


def on_connect(client, userdata, flags, rc):
    codigos = {
        0: "Conexión exitosa",
        1: "Versión de protocolo incorrecta",
        2: "Identificador de cliente rechazado",
        3: "Servidor no disponible",
        4: "Usuario/contraseña incorrectos",
        5: "No autorizado",
    }
    mensaje = codigos.get(rc, f"Código desconocido: {rc}")
    if rc == 0:
        print(f"[MQTT] Conectado al broker '{BROKER}'. {mensaje}")
    else:
        print(f"[MQTT ERROR] No se pudo conectar: {mensaje}")
        sys.exit(1)


def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"[MQTT] Desconexión inesperada (rc={rc}). Intentando reconectar...")


def on_publish(client, userdata, mid):
    # Callback silencioso; el log de OK ya se imprime en el bucle principal
    pass


def iniciar_sender():
    client = mqtt.Client(client_id=f"smat-sender-estacion{ESTACION_ID}")
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_publish    = on_publish

    print(f"[MQTT] Conectando a '{BROKER}:{PORT}'...")
    try:
        client.connect(BROKER, PORT, keepalive=60)
    except Exception as e:
        print(f"[MQTT CRÍTICO] No se pudo conectar al broker: {e}")
        sys.exit(1)

    # Bucle de red en hilo de fondo (non-blocking)
    client.loop_start()
    print(f"[MQTT] Publicando en tópico: '{TOPIC}'")
    print("       Presiona Ctrl+C para detener.\n")

    try:
        while True:
            valor = leer_sensor_emulado()
            payload = {
                "valor": valor,
                "estacion_id": ESTACION_ID,
                "timestamp": time.time()
            }

            result = client.publish(TOPIC, json.dumps(payload), qos=1)

            if valor > UMBRAL_ALERTA:
                print(f"  ⚠  [ALERTA] {valor} cm — Modo EMERGENCIA. QoS mid={result.mid}")
                intervalo = INTERVALO_EMERGENCIA
            else:
                print(f"[OK] {valor} cm publicados. QoS mid={result.mid}")
                intervalo = INTERVALO_NORMAL

            time.sleep(intervalo)

    except KeyboardInterrupt:
        print("\n[MQTT] Detenido por el usuario.")
    finally:
        client.loop_stop()
        client.disconnect()
        print("[MQTT] Desconectado del broker.")


if __name__ == "__main__":
    iniciar_sender()
