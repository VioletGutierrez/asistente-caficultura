# ============================================================
# modulos/red_bayesiana.py
# Red Bayesiana del cafe usando pgmpy
# Referencia: IA.docx Pag. 27-29 (CPTs) y Pag. 38 (implementacion)
# Incluye los 6 nodos del documento + R_Ojo
# ============================================================

try:
    from pgmpy.models import DiscreteBayesianNetwork
except ImportError:
    from pgmpy.models import BayesianNetwork as DiscreteBayesianNetwork

from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination


class RedBayesianaCafe:
    """
    Nodos:
      T       = Temperatura (0=Baja<18, 1=Optima 18-28, 2=Alta>28)
      HR      = Humedad Relativa (0=Baja<75, 1=Moderada 75-88, 2=Alta>88)
      P       = Precipitacion (0=Escasa<50, 1=Moderada 50-120, 2=Abundante>120)
      S       = Horas de mojadura (0=Corta<6h, 1=Prolongada>=6h)
      R_Roya  = Riesgo de roya (0=Bajo, 1=Medio, 2=Alto)
      S_Antra = Severidad de antracnosis (0=Baja, 1=Moderada, 2=Severa)
      R_Ojo   = Prevalencia de ojo de gallo (0=Bajo, 1=Alto)
    """

    def __init__(self):
        self.modelo = DiscreteBayesianNetwork([
            ("T", "S"), ("HR", "S"),
            ("T", "R_Roya"), ("S", "R_Roya"), ("P", "R_Roya"),
            ("R_Roya", "S_Antra"), ("P", "S_Antra"),
            ("P", "R_Ojo"), ("HR", "R_Ojo"),
        ])

        self._construir_cpts()
        assert self.modelo.check_model(), "Red Bayesiana con inconsistencias"
        self.inferencia = VariableElimination(self.modelo)

    # --------------------------------------------------------
    def _construir_cpts(self):
        # Nodos raiz
        cpd_T = TabularCPD(
            variable="T", variable_card=3,
            values=[[0.20], [0.60], [0.20]],
        )
        cpd_HR = TabularCPD(
            variable="HR", variable_card=3,
            values=[[0.30], [0.40], [0.30]],
        )
        cpd_P = TabularCPD(
            variable="P", variable_card=3,
            values=[[0.40], [0.40], [0.20]],
        )

        # S | T, HR  (2 x 9)
        # Columnas en orden lexicografico: (T0,HR0), (T0,HR1), (T0,HR2),
        #                                  (T1,HR0), (T1,HR1), (T1,HR2),
        #                                  (T2,HR0), (T2,HR1), (T2,HR2)
        cpd_S = TabularCPD(
            variable="S", variable_card=2,
            values=[
                # P(S = Corta)
                [0.95, 0.85, 0.40,   0.85, 0.45, 0.10,   0.95, 0.70, 0.30],
                # P(S = Prolongada)
                [0.05, 0.15, 0.60,   0.15, 0.55, 0.90,   0.05, 0.30, 0.70],
            ],
            evidence=["T", "HR"], evidence_card=[3, 3],
        )

        # R_Roya | S, P, T  (3 x 18)
        cpd_R_Roya = TabularCPD(
            variable="R_Roya", variable_card=3,
            values=[
                # P(Bajo)
                [0.85, 0.85, 0.85,  0.40, 0.40, 0.40,  0.15, 0.15, 0.15,
                 0.05, 0.05, 0.05,  0.15, 0.15, 0.15,  0.05, 0.05, 0.05],
                # P(Medio)
                [0.10, 0.10, 0.10,  0.45, 0.45, 0.45,  0.50, 0.50, 0.50,
                 0.15, 0.15, 0.15,  0.50, 0.50, 0.50,  0.15, 0.15, 0.15],
                # P(Alto)
                [0.05, 0.05, 0.05,  0.15, 0.15, 0.15,  0.35, 0.35, 0.35,
                 0.80, 0.80, 0.80,  0.35, 0.35, 0.35,  0.80, 0.80, 0.80],
            ],
            evidence=["S", "P", "T"], evidence_card=[2, 3, 3],
        )

        # S_Antra | R_Roya, P  (3 x 9)
        cpd_S_Antra = TabularCPD(
            variable="S_Antra", variable_card=3,
            values=[
                [0.90, 0.90, 0.90,  0.30, 0.30, 0.30,  0.25, 0.25, 0.25],
                [0.08, 0.08, 0.08,  0.50, 0.50, 0.50,  0.50, 0.50, 0.50],
                [0.02, 0.02, 0.02,  0.20, 0.20, 0.20,  0.25, 0.25, 0.25],
            ],
            evidence=["R_Roya", "P"], evidence_card=[3, 3],
        )

        # R_Ojo | P, HR  (2 x 9)  -- NUEVO
        # Favorecido por precipitacion y humedad alta
        cpd_R_Ojo = TabularCPD(
            variable="R_Ojo", variable_card=2,
            values=[
                # P(R_Ojo = Bajo)
                [0.95, 0.90, 0.70,   0.85, 0.75, 0.45,   0.70, 0.50, 0.15],
                # P(R_Ojo = Alto)
                [0.05, 0.10, 0.30,   0.15, 0.25, 0.55,   0.30, 0.50, 0.85],
            ],
            evidence=["P", "HR"], evidence_card=[3, 3],
        )

        self.modelo.add_cpds(
            cpd_T, cpd_HR, cpd_P, cpd_S,
            cpd_R_Roya, cpd_S_Antra, cpd_R_Ojo,
        )

    # --------------------------------------------------------
    @staticmethod
    def _discretizar(ev):
        out = {}
        if "temperatura" in ev:
            t = ev["temperatura"]
            out["T"] = 0 if t < 18 else (1 if t <= 28 else 2)
        if "humedad_relativa" in ev:
            hr = ev["humedad_relativa"]
            out["HR"] = 0 if hr < 75 else (1 if hr <= 88 else 2)
        if "precipitacion_24h" in ev:
            p = ev["precipitacion_24h"]
            out["P"] = 0 if p < 50 else (1 if p <= 120 else 2)
        return out

    # --------------------------------------------------------
    def evaluar(self, lluvia, hr, temp, sintoma="", precipitacion_24h=None):
        if precipitacion_24h is None:
            precipitacion_24h = 120.0 if lluvia else 20.0

        evidencia = self._discretizar({
            "temperatura":       temp,
            "humedad_relativa":  hr,
            "precipitacion_24h": precipitacion_24h,
        })

        try:
            q_roya = self.inferencia.query(
                variables=["R_Roya"], evidence=evidencia, show_progress=False
            )
            probs_roya = q_roya.values

            q_antra = self.inferencia.query(
                variables=["S_Antra"], evidence=evidencia, show_progress=False
            )
            probs_antra = q_antra.values

            q_ojo = self.inferencia.query(
                variables=["R_Ojo"], evidence=evidencia, show_progress=False
            )
            probs_ojo = q_ojo.values
        except Exception:
            probs_roya  = [0.30, 0.40, 0.30]
            probs_antra = [0.40, 0.40, 0.20]
            probs_ojo   = [0.60, 0.40]

        p_roya_alta = float(probs_roya[2])
        p_antra_sev = float(probs_antra[2])
        p_ojo_alto  = float(probs_ojo[1])

        if sintoma:
            s = sintoma.lower()
            if "naranja" in s or "pustul" in s:
                p_roya_alta = min(1.0, p_roya_alta * 1.40)
            if "negra" in s or "hundida" in s:
                p_antra_sev = min(1.0, p_antra_sev * 1.35)
            if "circular" in s or "gris" in s:
                p_ojo_alto = min(1.0, p_ojo_alto * 1.40)

        return {
            "roya":         round(p_roya_alta, 3),
            "antracnosis":  round(p_antra_sev, 3),
            "ojo_gallo":    round(p_ojo_alto, 3),
            "riesgo_global": round(max(p_roya_alta, p_antra_sev, p_ojo_alto), 3),
            "detalle_roya": {
                "bajo":  round(float(probs_roya[0]), 3),
                "medio": round(float(probs_roya[1]), 3),
                "alto":  round(float(probs_roya[2]), 3),
            },
            "detalle_antracnosis": {
                "baja":     round(float(probs_antra[0]), 3),
                "moderada": round(float(probs_antra[1]), 3),
                "severa":   round(float(probs_antra[2]), 3),
            },
            "detalle_ojo": {
                "bajo": round(float(probs_ojo[0]), 3),
                "alto": round(float(probs_ojo[1]), 3),
            },
        }


# ------------------------------------------------------------
if __name__ == "__main__":
    red = RedBayesianaCafe()
    escenarios = [
        ("A - Canicula Seca",    False, 65.0, 29.5, 15.0),
        ("B - Lluvia Moderada",  True,  82.0, 23.0, 65.0),
        ("C - Temporal Extremo", True,  94.0, 22.0, 145.0),
    ]
    for nombre, lluvia, hr, temp, precip in escenarios:
        r = red.evaluar(lluvia=lluvia, hr=hr, temp=temp,
                        sintoma="manchas naranjas", precipitacion_24h=precip)
        print(f"=== {nombre} ===")
        print(f"  Roya alto:       {r['detalle_roya']['alto']:.2f}")
        print(f"  Roya bajo:       {r['detalle_roya']['bajo']:.2f}")
        print(f"  Antracnosis sev: {r['detalle_antracnosis']['severa']:.2f}")
        print(f"  Ojo de gallo:    {r['detalle_ojo']['alto']:.2f}")
        print()