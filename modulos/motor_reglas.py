# ============================================================
# modulos/motor_reglas.py
# Motor de reglas determinista con soporte AND/OR
# Referencia: IA.docx §3.2
# ============================================================
import json
import os
import re


class MotorReglas:
    """Motor de reglas con forward chaining y prioridad."""

    def __init__(self, ruta=None):
        if ruta is None:
            ruta = os.path.join("datos", "reglas_produccion.json")
        self.ruta = ruta
        with open(ruta, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.reglas = self.data["reglas"]

    # --------------------------------------------------------
    def _cumple(self, valor_real, condicion):
        """Evalua una condicion (operador, rango, lista, booleano)."""
        if isinstance(condicion, list):
            return valor_real in condicion

        if isinstance(condicion, bool):
            if isinstance(valor_real, str):
                return valor_real.lower() in (
                    "true", "si", "sí", "1") == condicion
            return bool(valor_real) == condicion

        if isinstance(condicion, str):
            s = condicion.strip()
            # Rango "18-24"
            m = re.match(
                r"^(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)$", s)
            if m:
                lo, hi = float(m.group(1)), float(m.group(2))
                try:
                    return lo <= float(valor_real) <= hi
                except (ValueError, TypeError):
                    return False
            # Comparadores ">75", "<2.2"
            m = re.match(r"^(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)$", s)
            if m:
                op, ref = m.group(1), float(m.group(2))
                try:
                    v = float(valor_real)
                except (ValueError, TypeError):
                    return False
                if op == ">":  return v > ref
                if op == "<":  return v < ref
                if op == ">=": return v >= ref
                if op == "<=": return v <= ref
            # Igualdad de strings / numerica
            if isinstance(valor_real, str):
                return valor_real == condicion
            try:
                return float(valor_real) == float(condicion)
            except (ValueError, TypeError):
                return False

        return valor_real == condicion

    # --------------------------------------------------------
    def _eval_dict(self, condiciones, hechos):
        for k, v in condiciones.items():
            if k in ("operador_logico", "condiciones"):
                continue
            if k not in hechos:
                return False
            if not self._cumple(hechos[k], v):
                return False
        return True

    # --------------------------------------------------------
    def _aplica(self, regla, hechos):
        si = regla.get("si", {})

        # Formato con operador logico explicito
        if isinstance(si.get("condiciones"), list):
            op = str(si.get("operador_logico", "AND")).upper()
            resultados = []
            for c in si["condiciones"]:
                var = c.get("variable")
                val = c.get("valor")
                if var not in hechos:
                    resultados.append(False)
                else:
                    resultados.append(self._cumple(hechos[var], val))
            if not resultados:
                return True
            return any(resultados) if op == "OR" else all(resultados)

        # Formato clasico (AND implicito)
        return self._eval_dict(si, hechos)

    # --------------------------------------------------------
    def inferir(self, hechos):
        aplicables = []
        for regla in self.reglas:
            if self._aplica(regla, hechos):
                aplicables.append({
                    "regla_id":      regla["id"],
                    "prioridad":     regla.get("prioridad", 0),
                    "diagnostico":   regla["entonces"].get("diagnostico", ""),
                    "recomendacion": regla["entonces"].get("recomendacion", ""),
                    "descripcion":   regla.get("descripcion", ""),
                })
        aplicables.sort(key=lambda r: -r["prioridad"])
        if not aplicables:
            return [{
                "regla_id": None,
                "prioridad": 0,
                "diagnostico": "Sin diagnostico concluyente",
                "recomendacion": "Proporcione mas datos o consulte al Oraculo LLM.",
                "descripcion": "Ninguna regla coincide con los hechos.",
            }]
        return aplicables