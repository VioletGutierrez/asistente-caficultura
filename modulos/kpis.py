# ============================================================
# modulos/kpis.py
# KPIs conversacionales + CSAT
# Referencia: IA_Entregable1.pdf §10.2
# ============================================================
import json
import os
from pathlib import Path

RUTA_LOG = Path("salidas") / "kpis.jsonl"


def _asegurar_directorio():
    os.makedirs(RUTA_LOG.parent, exist_ok=True)


def registrar_turno(sesion_uuid, intent, entidades, respuesta,
                    tiempo_seg, fallback=False, error=False):
    _asegurar_directorio()
    registro = {
        "sesion_uuid": sesion_uuid,
        "intent":      intent,
        "entidades":   entidades,
        "respuesta":   (respuesta[:500] if isinstance(respuesta, str)
                        else str(respuesta)),
        "tiempo_seg":  round(float(tiempo_seg), 3),
        "fallback":    bool(fallback),
        "error":       bool(error),
    }
    with open(RUTA_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def _leer_registros():
    if not RUTA_LOG.exists():
        return []
    with open(RUTA_LOG, "r", encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def calcular_kpis():
    registros = _leer_registros()
    total = len(registros)
    if total == 0:
        return {
            "total_turnos":           0,
            "fallback_rate":          0.0,
            "tasa_error":             0.0,
            "latencia_promedio_seg":  0.0,
            "csat_promedio":          None,
        }
    fallback = sum(1 for r in registros if r.get("fallback"))
    errores  = sum(1 for r in registros if r.get("error"))
    latencia = sum(r.get("tiempo_seg", 0.0) for r in registros) / total
    csats = [r["entidades"]["csat"]
             for r in registros
             if r.get("intent") == "CSAT_Feedback"
             and "csat" in r.get("entidades", {})]
    return {
        "total_turnos":           total,
        "fallback_rate":          round(fallback / total, 3),
        "tasa_error":             round(errores / total, 3),
        "latencia_promedio_seg":  round(latencia, 3),
        "csat_promedio":          (round(sum(csats) / len(csats), 2)
                                    if csats else None),
    }


def calcular_csat():
    """CSAT promedio (1-5). None si no hay registros."""
    registros = _leer_registros()
    csats = [r["entidades"]["csat"]
             for r in registros
             if r.get("intent") == "CSAT_Feedback"
             and "csat" in r.get("entidades", {})]
    if not csats:
        return None
    return round(sum(csats) / len(csats), 2)