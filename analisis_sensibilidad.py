# ============================================================
# analisis_sensibilidad.py
# Analisis de sensibilidad con 3 escenarios climaticos
# Referencia: IA.docx §5.2
# Uso: python analisis_sensibilidad.py
# ============================================================
import json
from datetime import datetime
from modulos.red_bayesiana import RedBayesianaCafe


ESCENARIOS = [
    {
        "id": "A",
        "nombre": "Canicula Seca",
        "lluvia": False, "hr": 65.0, "temp": 29.5, "precipitacion_24h": 15.0,
    },
    {
        "id": "B",
        "nombre": "Lluvia Moderada",
        "lluvia": True,  "hr": 82.0, "temp": 23.0, "precipitacion_24h": 65.0,
    },
    {
        "id": "C",
        "nombre": "Temporal Extremo",
        "lluvia": True,  "hr": 94.0, "temp": 22.0, "precipitacion_24h": 145.0,
    },
]


def ejecutar_analisis():
    red = RedBayesianaCafe()
    salida = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "escenarios": [],
    }
    for e in ESCENARIOS:
        r = red.evaluar(
            lluvia=e["lluvia"], hr=e["hr"], temp=e["temp"],
            sintoma="manchas naranjas",
            precipitacion_24h=e["precipitacion_24h"],
        )
        salida["escenarios"].append({
            "id":         e["id"],
            "nombre":     e["nombre"],
            "entrada":    {
                "lluvia": e["lluvia"], "hr": e["hr"],
                "temp": e["temp"], "precipitacion_24h": e["precipitacion_24h"],
            },
            "resultado": {
                "roya":          r["roya"],
                "antracnosis":   r["antracnosis"],
                "ojo_gallo":     r["ojo_gallo"],
                "riesgo_global": r["riesgo_global"],
                "detalle_roya":  r["detalle_roya"],
                "detalle_ojo":   r["detalle_ojo"],
            },
        })
    return salida


if __name__ == "__main__":
    res = ejecutar_analisis()
    print(json.dumps(res, indent=2, ensure_ascii=False))