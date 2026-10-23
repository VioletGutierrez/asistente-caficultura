# ============================================================
# modulos/vision_cnn.py
# ============================================================
import os
import numpy as np

try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False

from modulos.llm_fallback import OraculoAgronomoLLM

CLASES = ["Sana", "Roya", "Antracnosis", "Deficiencia_Nitrogeno", "Ojo_de_gallo", "Mancha_de_hierro"]
UMBRAL_CONF = 0.55

SINTOMA_A_CLASE = {
    "manchas_naranjas": "Roya", "polvo_amarillo": "Roya", "pustulas": "Roya",
    "manchas_negras": "Antracnosis", "lesiones_hundidas": "Antracnosis",
    "manchas_circulares": "Ojo_de_gallo", "borde_cafe": "Ojo_de_gallo",
    "mancha_cafe_rojiza": "Mancha_de_hierro", "halo_amarillo": "Mancha_de_hierro",
    "hojas_amarillas": "Deficiencia_Nitrogeno", "clorosis_uniforme": "Deficiencia_Nitrogeno",
}

class ClasificadorVisionCNN:
    def __init__(self, ruta_modelo=None):
        self.modo = "heuristico_hsv"
        self.llm = OraculoAgronomoLLM()

    def _preprocesar(self, ruta):
        img = cv2.imread(ruta)
        if img is None: raise FileNotFoundError(f"No se pudo leer: {ruta}")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return cv2.resize(img, (400, 400))

    def _analizar_hsv(self, img_rgb):
        hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
        total_area = img_rgb.shape[0] * img_rgb.shape[1]

        m_roya = cv2.inRange(hsv, (5, 100, 100), (25, 255, 255))
        m_antra = cv2.inRange(hsv, (0, 30, 0), (25, 255, 90))
        m_defn = cv2.inRange(hsv, (22, 40, 100), (40, 200, 255))
        m_ojo = cv2.inRange(hsv, (0, 0, 150), (180, 40, 255))
        m_hierro = cv2.inRange(hsv, (10, 100, 100), (20, 255, 200))

        def pct(mask): return np.count_nonzero(mask) / total_area

        r, a, d, o, h = pct(m_roya), pct(m_antra), pct(m_defn), pct(m_ojo), pct(m_hierro)
        
        # ARREGLO: Roya tiene prioridad sobre Mancha de Hierro
        if a > 0.02: return "Antracnosis", min(0.92, 0.60 + (a * 5))
        elif o > 0.015: return "Ojo_de_gallo", min(0.88, 0.60 + (o * 5))
        elif r > 0.008: return "Roya", min(0.95, 0.65 + (r * 8)) # Roya antes que Hierro
        elif h > 0.015: return "Mancha_de_hierro", min(0.90, 0.60 + (h * 5))
        elif d > 0.10: return "Deficiencia_Nitrogeno", min(0.90, 0.50 + (d * 2))
        else: return "Sana", 0.85

    def clasificar_imagen(self, ruta, sintoma_textual=None):
        # 1. Intentar con Inteligencia Artificial
        resultado_ia = self.llm.analizar_imagen_con_ia(ruta)
        
        if resultado_ia and "error" not in resultado_ia:
            clase = resultado_ia["clase"]
            conf = resultado_ia["confianza"]
            justificacion = resultado_ia.get("justificacion", "")
            modo = resultado_ia["modo"]
        else:
            # 2. Fallback local
            img_rgb = self._preprocesar(ruta)
            clase, conf = self._analizar_hsv(img_rgb)
            modo = "heuristico_hsv"
            # Si hubo un error con Gemini, lo mostramos para que sepas qué pasa
            if resultado_ia and "error" in resultado_ia:
                justificacion = f"Error IA (usando HSV): {resultado_ia['error']}"
            else:
                justificacion = "Análisis por color (Fallback local)."

        # --- CRUCE CON SINTOMA TEXTUAL ---
        nota_cruce = None
        if sintoma_textual:
            clase_esperada = SINTOMA_A_CLASE.get(sintoma_textual)
            if clase_esperada and clase != clase_esperada:
                nota_cruce = f"Ajustado a '{clase_esperada}' basado en síntomas descritos."
                clase = clase_esperada
                conf = max(conf, 0.85)

        return {
            "clase": clase,
            "confianza": round(conf, 3),
            "justificacion": justificacion,
            "requiere_retomar_foto": conf < UMBRAL_CONF,
            "modo": modo,
            "nota_cruce": nota_cruce,
        }