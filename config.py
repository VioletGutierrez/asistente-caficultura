# ============================================================
# config.py
# Configuracion central del Asistente Inteligente Caficultura
# ============================================================
from pathlib import Path

# Rutas base del proyecto
BASE_DIR = Path(__file__).resolve().parent
DATOS_DIR = BASE_DIR / "datos"
MODELOS_DIR = BASE_DIR / "modelos"
SALIDAS_DIR = BASE_DIR / "salidas"

RUTA_REGLAS   = DATOS_DIR / "reglas_produccion.json"
RUTA_PRECIOS  = DATOS_DIR / "precios_mercado.json"
RUTA_CONTEXTO = DATOS_DIR / "contexto_agronomico.txt"
RUTA_CNN      = MODELOS_DIR / "cnn_hojas_cafe.h5"
RUTA_BD       = DATOS_DIR / "asistente.db"

# Parametros agronomicos y economicos
SUPERFICIE_DEFECTO_MZ   = 1.0
TIPO_CAMBIO_USD_NIO     = 36.62
PRECIO_CAFE_QQ_USD      = 220.0
COSTO_MANO_OBRA_DIA_NIO = 280.0

# Umbrales de decision
UMBRAL_CONFIANZA_CNN    = 0.70
UMBRAL_RIESGO_ALTO      = 0.65
UMBRAL_RIESGO_MEDIO     = 0.40

# API meteorologica
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Coordenadas por defecto (Matagalpa, Nicaragua)
LAT_DEFECTO = 12.9256
LON_DEFECTO = -85.9172

# Ollama (LLM local)
OLLAMA_URL    = "http://localhost:11434/api/generate"
OLLAMA_MODELO = "llama3.2:3b"

# Asegurar directorios
for d in (DATOS_DIR, MODELOS_DIR, SALIDAS_DIR):
    d.mkdir(parents=True, exist_ok=True)