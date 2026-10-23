# ============================================================
# modulos/vision_cnn.py
# Clasificador de hojas con MobileNetV3 + fallback HSV mejorado
# Referencia: IA.docx §4.4
# ============================================================
import os
import numpy as np

try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False

try:
    import tensorflow as tf
    TF_OK = True
except ImportError:
    TF_OK = False


RUTA_H5     = os.path.join("modelos", "cnn_cafe.h5")
RUTA_TFLITE = os.path.join("modelos", "cnn_cafe.tflite")
CLASES      = ["Sana", "Roya", "Antracnosis", "Deficiencia_Nitrogeno"]
UMBRAL_CONF = 0.55   # umbral mas bajo porque ahora es clinico

# Umbral clinico: si una patologia supera este %, se declara
# (una hoja con 5% de roya NO esta sana, aunque el 95% sea verde)
UMBRAL_CLINICO = {
    "Roya":                 0.030,  # 3% de area con naranja/rojo
    "Antracnosis":          0.030,  # 3% de area con marron/negro
    "Deficiencia_Nitrogeno":0.050,  # 5% de area amarillenta
}

# Mapa sintoma -> clase esperada (para cruce)
SINTOMA_A_CLASE = {
    "manchas_naranjas":    "Roya",
    "polvo_amarillo":      "Roya",
    "pustulas":            "Roya",
    "manchas_negras":      "Antracnosis",
    "lesiones_hundidas":   "Antracnosis",
    "muerte_ramas":        "Antracnosis",
    "hojas_amarillas":     "Deficiencia_Nitrogeno",
    "clorosis_uniforme":   "Deficiencia_Nitrogeno",
    "borde_hojas_amarillo":"Deficiencia_Nitrogeno",
    "necrosis_marginal":   "Deficiencia_Nitrogeno",
}


class ClasificadorVisionCNN:
    """Clasificador foliar con modelo real o fallback HSV."""

    def __init__(self, ruta_modelo=None):
        self.modelo        = None
        self.interprete    = None
        self.ruta_modelo   = ruta_modelo
        self.modo          = "heuristico_hsv"
        self._intentar_cargar_modelo(ruta_modelo)

    def _intentar_cargar_modelo(self, ruta_modelo=None):
        if ruta_modelo and os.path.exists(ruta_modelo):
            self._cargar_h5(ruta_modelo); return
        if os.path.exists(RUTA_H5):
            self._cargar_h5(RUTA_H5); return
        if os.path.exists(RUTA_TFLITE):
            self._cargar_tflite(RUTA_TFLITE); return

    def _cargar_h5(self, ruta):
        if not TF_OK: return
        try:
            self.modelo = tf.keras.models.load_model(ruta)
            self.modo = "tensorflow_h5"
        except Exception as e:
            print(f"[vision] Error al cargar {ruta}: {e}")

    def _cargar_tflite(self, ruta):
        if not TF_OK: return
        try:
            self.interprete = tf.lite.Interpreter(model_path=ruta)
            self.interprete.allocate_tensors()
            self.modo = "tflite"
        except Exception as e:
            print(f"[vision] Error al cargar TFLite: {e}")

    def _preprocesar(self, ruta):
        img = cv2.imread(ruta)
        if img is None:
            raise FileNotFoundError(f"No se pudo leer: {ruta}")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (224, 224))
        x   = img.astype(np.float32) / 255.0
        return img, x

    def _predecir_tf(self, x):
        return self.modelo.predict(np.expand_dims(x, 0), verbose=0)[0]

    def _predecir_tflite(self, x):
        det = self.interprete.get_input_details()[0]
        sal = self.interprete.get_output_details()[0]
        self.interprete.set_tensor(det["index"], np.expand_dims(x, 0))
        self.interprete.invoke()
        return self.interprete.get_tensor(sal["index"])[0]

    # --------------------------------------------------------
    def _analizar_hsv(self, img_rgb):
        """
        Analisis HSV mejorado:
        - Rangos mas amplios (H 0-40 cubre rojo-naranja-amarillo)
        - Prioriza patologias con umbral clinico
        """
        hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)

        # Roya: rojo-naranja-amarillo (H 0-40 cubre toda la gama)
        m_roya = cv2.inRange(hsv, (0, 60, 50), (40, 255, 255))
        # Antracnosis: marron oscuro / negro / cafe
        m_antra = cv2.inRange(hsv, (0, 20, 0), (180, 255, 90))
        # Deficiencia N: amarillo palido (H 20-45, S bajo-medio)
        m_defn = cv2.inRange(hsv, (20, 30, 90), (45, 180, 255))
        # Verde (sano)
        m_verde = cv2.inRange(hsv, (35, 60, 40), (85, 255, 255))

        total = img_rgb.shape[0] * img_rgb.shape[1]
        def pct(mask):
            return float(np.count_nonzero(mask)) / total

        r, a, d, v = pct(m_roya), pct(m_antra), pct(m_defn), pct(m_verde)
        # Restar doble conteo: roya esta dentro de antra en algunos pixeles
        # Si el pixel es naranja claro, priorizarlo como roya
        # (un pixel no puede ser roya Y antracnosis al mismo tiempo)
        a = max(0.0, a - 0.3 * r)

        raw = np.array([v, r, a, d], dtype=np.float32) + 1e-3
        probs = raw / raw.sum()
        return probs, {"roya": r, "antra": a, "defn": d, "verde": v}

    # --------------------------------------------------------
    def _decidir_clase(self, probs, areas):
        """
        Logica clinica: si cualquier patologia supera su umbral,
        se declara, aunque el verde domine.
        """
        # Verificar patologias primero
        for clase in ["Roya", "Antracnosis", "Deficiencia_Nitrogeno"]:
            idx = CLASES.index(clase)
            area_pct = probs[idx]
            umbral   = UMBRAL_CLINICO.get(clase, 0.05)
            if area_pct >= umbral:
                return clase, float(area_pct)

        # Si nada supera, "Sana" pero con confianza = verde
        idx_sana = CLASES.index("Sana")
        return "Sana", float(probs[idx_sana])

    # --------------------------------------------------------
    def clasificar_imagen(self, ruta, sintoma_textual=None):
        """
        clasificar_imagen(ruta, sintoma_textual="manchas_naranjas")
        Cruza la clasificacion visual con el sintoma declarado por el
        usuario para corregir falsos negativos.
        """
        img_rgb, x = self._preprocesar(ruta)

        if self.modo == "tensorflow_h5":
            probs = np.asarray(self._predecir_tf(x), dtype=np.float32)
            areas = {}
        elif self.modo == "tflite":
            probs = np.asarray(self._predecir_tflite(x), dtype=np.float32)
            areas = {}
        else:
            probs, areas = self._analizar_hsv(img_rgb)

        # Logica clinica
        clase, conf = self._decidir_clase(probs, areas)

        # --- Cruce con sintoma textual ---
        nota_cruce = None
        if sintoma_textual:
            clase_esperada = SINTOMA_A_CLASE.get(sintoma_textual)
            if clase_esperada and clase != clase_esperada:
                if clase == "Sana":
                    # El usuario dice sintoma, la imagen dice sana -> corregir
                    nota_cruce = (
                        f"Corregida de 'Sana' a '{clase_esperada}' "
                        f"por sintomas declarados por el usuario."
                    )
                    clase = clase_esperada
                    conf  = 0.55  # confianza moderada al corregir

        return {
            "clase":                 clase,
            "confianza":             round(conf, 3),
            "vector_probabilidades": [round(float(p), 3) for p in probs],
            "areas_hsv":             {k: round(float(v), 3) for k, v in areas.items()},
            "requiere_retomar_foto": conf < UMBRAL_CONF,
            "modo":                  self.modo,
            "nota_cruce":            nota_cruce,
        }