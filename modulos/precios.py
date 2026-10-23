# ============================================================
# modulos/precios.py
# Automatizacion de precios de cafe y tipo de cambio
# Referencia: IA.docx Pag. 40
# ============================================================
import json
import requests
import yfinance as yf
from datetime import datetime
from config import (
    RUTA_PRECIOS, TIPO_CAMBIO_USD_NIO, PRECIO_CAFE_QQ_USD,
    COSTO_MANO_OBRA_DIA_NIO,
)


VALORES_DEFECTO = {
    "tipo_cambio_usd_nio":       TIPO_CAMBIO_USD_NIO,
    "precio_cafe_oro_qq_usd":    PRECIO_CAFE_QQ_USD,
    "costo_mano_obra_dia_nio":   COSTO_MANO_OBRA_DIA_NIO,
    "precio_urea_qq_nio":        1650.0,
    "precio_kcl_qq_nio":         1400.0,
    "precio_fungicida_litro_nio": 950.0,
    "costo_aplicacion_nio":      500.0,
    "ultima_actualizacion":      "2026-09-08",
}


# ------------------------------------------------------------
def obtener_tipo_cambio():
    """Consulta el tipo de cambio USD/NIO desde open.er-api.com (gratis)."""
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        r.raise_for_status()
        return float(r.json()["rates"]["NIO"])
    except Exception as e:
        print(f"[precios] Error tipo de cambio: {e}")
        return TIPO_CAMBIO_USD_NIO


# ------------------------------------------------------------
def obtener_precio_cafe():
    """
    Consulta el precio del cafe arabica (KC=F) en Yahoo Finance.
    Correccion: yfinance devuelve el precio en centavos USD/libra.
    1 quintal = 100 libras, por lo que el valor crudo ya es USD/qq.
    """
    try:
        cafe = yf.Ticker("KC=F")
        hist = cafe.history(period="1d")
        if hist.empty:
            return PRECIO_CAFE_QQ_USD

        raw = float(hist["Close"].iloc[-1])

        # Si el valor es menor a 10, viene en USD/libra (raro)
        # Si es mayor a 10, viene en centavos por libra (= USD/qq)
        precio_qq = raw if raw > 10 else raw * 100.0

        # Sanidad: precio razonable entre 100 y 500 USD/qq
        if not (100.0 <= precio_qq <= 500.0):
            return PRECIO_CAFE_QQ_USD

        return round(precio_qq, 2)
    except Exception as e:
        print(f"[precios] Error precio cafe: {e}")
        return PRECIO_CAFE_QQ_USD


# ------------------------------------------------------------
def actualizar_precios():
    """Actualiza el JSON con los precios mas recientes."""
    datos = VALORES_DEFECTO.copy()
    datos["precio_cafe_oro_qq_usd"] = obtener_precio_cafe()
    datos["tipo_cambio_usd_nio"]    = obtener_tipo_cambio()
    datos["ultima_actualizacion"]   = datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        with open(RUTA_PRECIOS, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[precios] Error guardando: {e}")

    return datos


# ------------------------------------------------------------
def leer_precios_actuales():
    """Lee el JSON o genera uno nuevo si no existe."""
    try:
        with open(RUTA_PRECIOS, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return actualizar_precios()


# ------------------------------------------------------------
if __name__ == "__main__":
    print("Actualizando precios de mercado...")
    p = actualizar_precios()
    for k, v in p.items():
        print(f"{k:32s}: {v}")