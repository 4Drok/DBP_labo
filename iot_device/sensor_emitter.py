import requests
import time
import random

# ─────────────────────────────────────────────
# CONFIGURACIÓN — ajusta estos valores según tu entorno
# ─────────────────────────────────────────────
API_URL   = "http://127.0.0.1:8000/lecturas/"
TOKEN_URL = "http://127.0.0.1:8000/token"
ESTACION_ID = 1          # Debe existir en la BD antes de correr este script

# El token SMAT expira en 30 minutos; lo renovamos con margen de seguridad
TOKEN_REFRESH_SECONDS = 25 * 60   # 25 min → renovar antes del vencimiento
# ─────────────────────────────────────────────


def obtener_token() -> str | None:
    """Solicita un JWT al backend SMAT (/token no requiere credenciales)."""
    try:
        response = requests.post(TOKEN_URL, timeout=5)
        response.raise_for_status()
        token = response.json()["access_token"]
        print("[AUTH] Token obtenido correctamente.")
        return token
    except requests.exceptions.ConnectionError:
        print("[AUTH CRÍTICO] No hay conexión con el servidor. ¿Está el backend corriendo?")
    except requests.exceptions.HTTPError as e:
        print(f"[AUTH ERROR] HTTP {e.response.status_code}")
    except Exception as e:
        print(f"[AUTH CRÍTICO] Error inesperado: {e}")
    return None


def leer_sensor_emulado() -> float:
    """Simula una lectura de nivel de río entre 10.5 y 85.0 cm."""
    return round(random.uniform(10.5, 85.0), 2)


def enviar_telemetria():
    print(f"--- Iniciando Emisor IoT — Estación {ESTACION_ID} ---")
    print(f"    Backend  : {API_URL}")
    print(f"    Token URL: {TOKEN_URL}\n")

    token = obtener_token()
    if not token:
        print("[CRÍTICO] No se puede iniciar sin token. Abortando.")
        return

    token_obtenido_en = time.time()   # Marca de tiempo para renovación proactiva

    while True:
        # ── Renovación proactiva del token ──────────────────────────────────
        if time.time() - token_obtenido_en >= TOKEN_REFRESH_SECONDS:
            print("[AUTH] Renovando token de forma proactiva...")
            nuevo = obtener_token()
            if nuevo:
                token = nuevo
                token_obtenido_en = time.time()
            else:
                print("[AUTH] Renovación fallida; se usará el token anterior.")

        # ── Lectura y envío ─────────────────────────────────────────────────
        valor = leer_sensor_emulado()
        payload = {"valor": valor, "estacion_id": ESTACION_ID}
        headers = {"Authorization": f"Bearer {token}"}

        # Lógica de alarma y frecuencia dinámica
        if valor > 70.0:
            print(f"  ⚠  [ALERTA] Umbral de inundación superado ({valor} cm).")
            intervalo_envio = 2   # Modo emergencia
        else:
            intervalo_envio = 10  # Modo normal

        try:
            response = requests.post(API_URL, json=payload, headers=headers, timeout=5)

            if response.status_code in (200, 201):
                print(f"[OK] {valor} cm enviados — próximo envío en {intervalo_envio}s")

            elif response.status_code == 401:
                # Token rechazado: renovar de inmediato
                print("[AUTH] Token inválido o expirado. Renovando...")
                token = obtener_token()
                if not token:
                    print("[CRÍTICO] No se pudo renovar el token. Abortando.")
                    break
                token_obtenido_en = time.time()

            elif response.status_code == 404:
                print(f"[ERROR 404] La estación {ESTACION_ID} no existe en la BD.")
                print("           Créala desde la app móvil antes de correr el emisor.")
                break   # No tiene sentido seguir enviando a una estación inexistente

            else:
                print(f"[ERROR] Código: {response.status_code} — {response.text}")

        except requests.exceptions.ConnectionError:
            print("[CRÍTICO] Sin conexión con el servidor. Reintentando en 10s...")
            time.sleep(10)
            continue
        except Exception as e:
            print(f"[CRÍTICO] Error inesperado: {e}")

        time.sleep(intervalo_envio)


if __name__ == "__main__":
    enviar_telemetria()
