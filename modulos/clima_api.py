# ============================================================
# modulos/clima_api.py
# Open-Meteo + fallback + coordenadas por departamento
# Referencia: IA.docx §4.1
# ============================================================
import requests


# Coordenadas de las capitales departamentales de Nicaragua
DEPTO_COORDS = {
    "Boaco":          (12.4722, -85.6586),
    "Carazo":         (11.8497, -86.1994),
    "Chinandega":     (12.6294, -87.1311),
    "Chontales":      (12.1064, -85.3647),
    "Esteli":         (13.0919, -86.3547),
    "Granada":        (11.9299, -85.9560),
    "Jinotega":       (13.0917, -86.0022),
    "Leon":           (12.4344, -86.8786),
    "Madriz":         (13.4833, -86.5833),
    "Managua":        (12.1364, -86.2514),
    "Masaya":         (11.9744, -86.0942),
    "Matagalpa":      (12.9256, -85.9172),
    "Nueva Segovia":  (13.6333, -86.4833),
    "Rio San Juan":   (11.1239, -84.7772),
    "Rivas":          (11.4394, -85.8286),
    "RACCN":          (14.0353, -83.3864),  # Bilwi
    "RACCS":          (12.0133, -83.7639),  # Bluefields
}


class ModuloClima:
    """Consulta Open-Meteo por departamento; fallback calibrado."""

    def __init__(self, departamento="Matagalpa", timeout=5.0):
        self.set_departamento(departamento)
        self.timeout = timeout
        self.url = "https://api.open-meteo.com/v1/forecast"

    # --------------------------------------------------------
    def set_departamento(self, depto):
        """Cambia las coordenadas segun el departamento de la finca."""
        if depto in DEPTO_COORDS:
            self.departamento = depto
            self.lat, self.lon = DEPTO_COORDS[depto]
        else:
            self.departamento = "Matagalpa"
            self.lat, self.lon = DEPTO_COORDS["Matagalpa"]

    # --------------------------------------------------------
    def obtener_datos_actuales(self):
        params = {
            "latitude":  self.lat,
            "longitude": self.lon,
            "hourly":    "temperature_2m,relativehumidity_2m,precipitation",
            "timezone":  "America/Managua",
        }
        try:
            r = requests.get(self.url, params=params, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()["hourly"]
            temp = float(data["temperature_2m"][-1])
            hr   = float(data["relativehumidity_2m"][-1])
            prec = float(sum(data["precipitation"][-24:]))
            horas = 10.0 if hr > 88.0 else 4.0
            return {
                "temperatura":       round(temp, 1),
                "humedad_relativa":  round(hr, 1),
                "precipitacion_24h": round(prec, 1),
                "horas_mojadura":    horas,
                "fuente":            f"Open-Meteo ({self.departamento})",
            }
        except Exception as e:
            print(f"[clima] Fallo en API ({e}). Activando fallback.")
            return self._fallback()

    # --------------------------------------------------------
    def _fallback(self):
        return {
            "temperatura":       22.5,
            "humedad_relativa":  85.0,
            "precipitacion_24h": 120.0,
            "horas_mojadura":    8.0,
            "fuente":            f"Fallback Local ({self.departamento})",
        }