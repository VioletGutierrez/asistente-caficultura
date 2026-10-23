# ============================================================
# modulos/algoritmo_genetico.py
# Algoritmo Genetico bioeconomico con penalizaciones del documento
# Referencia: IA.docx Pag. 30 (Mitscherlich) y Pag. 43 (AG exacto)
# Graduacion fitosanitaria: IA.docx Pag. 58
# ============================================================
import random
import numpy as np
from modulos.mitscherlich_baule import MitscherlichBaule
from modulos.precios import leer_precios_actuales


class OptimizacionGenetica:
    """
    Cromosoma = [riego_m3, N_kg, P_kg, K_kg, fungicida_L] por manzana.
    Objetivo  = maximizar beneficio neto en Cordobas ajustado por
                penalizaciones de anoxia, sobre-fertilizacion y riesgo.
    """

    # Limites agronomicos por gen
    LIMITES_INF = np.array([0.0,   0.0,   0.0,   0.0,   0.0])
    LIMITES_SUP = np.array([400.0, 150.0, 80.0,  120.0, 3.0])

    def __init__(self, generaciones=50, tam_poblacion=100,
                 tasa_cruce=0.85, tasa_mutacion=0.05,
                 alpha_blx=0.5, elite=2):
        self.generaciones = generaciones
        self.tam_poblacion = tam_poblacion
        self.tasa_cruce    = tasa_cruce
        self.tasa_mutacion = tasa_mutacion
        self.alpha_blx     = alpha_blx
        self.elite         = elite
        self.mb = MitscherlichBaule()

        # Precios unitarios en Cordobas (se leen del JSON)
        self._cargar_precios()

    # --------------------------------------------------------
    def _cargar_precios(self):
        p = leer_precios_actuales()
        self.precios = np.array([
            12.0,                                    # agua m3
            p.get("precio_urea_qq_nio", 1650.0) / 100.0,   # N por kg (urea 46%)
            p.get("precio_kcl_qq_nio", 1400.0) / 80.0,     # P por kg (aprox)
            p.get("precio_kcl_qq_nio", 1400.0) / 60.0,     # K por kg
            p.get("precio_fungicida_litro_nio", 950.0),    # fungicida por litro
        ])
        self.costo_aplicacion = p.get("costo_aplicacion_nio", 500.0)
        self.precio_cafe_cs   = (p.get("precio_cafe_oro_qq_usd", 220.0) *
                                 p.get("tipo_cambio_usd_nio", 36.62))

    # --------------------------------------------------------
    @staticmethod
    def _penalizacion_fitosanitaria(deficit):
        """
        Penalizacion graduada segun IA.docx Pag. 58.
        Continua en los puntos de union (0.15 y 0.35).

        deficit = max(0, riesgo_prob - cobertura_fungicida)
          - deficit <= 0.15 : lineal suave       (1200 * d)
          - 0.15 < d <= 0.35: cuadratica moderada (180 + 4000 * (d-0.15)^2)
          - d > 0.35        : cuadratica severa  (340 + 12000 * (d-0.35)^2)
        """
        if deficit <= 0.0:
            return 0.0
        if deficit <= 0.15:
            return 1200.0 * deficit
        if deficit <= 0.35:
            return 180.0 + 4000.0 * (deficit - 0.15) ** 2
        return 340.0 + 12000.0 * (deficit - 0.35) ** 2

    # --------------------------------------------------------
    def _fitness(self, x, riesgo_roya_pct=65.0):
        """
        Calcula (beneficio, rendimiento, costo) para un cromosoma.
        Penalizaciones exactas segun IA.docx Pag. 43
        con graduacion fitosanitaria segun Pag. 58.
        """
        riego, N, P, K, fung = x

        # Rendimiento biologico (qq/mz)
        rendimiento = self.mb.rendimiento(riego, N, P, K)

        # Costo de insumos + mano de obra
        costo = float(np.sum(x * self.precios)) + self.costo_aplicacion

        # --- Penalizaciones del documento ---
        # 1. Anoxia radical (saturacion de agua > 350 m3)
        pen_anoxia = 50.0 * max(0.0, riego - 350.0) ** 2

        # 2. Sobre-fertilizacion (N > 160 kg)
        pen_sobrefert = 80.0 * max(0.0, N - 160.0) ** 2

        # 3. Control fitosanitario insuficiente — GRADUADO
        proteccion = 1.0 - np.exp(-1.2 * fung)  # cobertura 0-1
        deficit = max(0.0, (riesgo_roya_pct / 100.0) - proteccion)
        pen_roya = self._penalizacion_fitosanitaria(deficit)

        # Beneficio neto (C$ por manzana)
        ingreso  = rendimiento * self.precio_cafe_cs
        beneficio = ingreso - costo - pen_anoxia - pen_sobrefert - pen_roya

        return beneficio, rendimiento, costo

    # --------------------------------------------------------
    def _seleccion_torneo(self, poblacion, aptitudes, k=3):
        """Seleccion por torneo estocastico."""
        indices = random.sample(range(len(poblacion)), k)
        mejor = max(indices, key=lambda i: aptitudes[i])
        return poblacion[mejor].copy()

    # --------------------------------------------------------
    def _cruzar_blx(self, p1, p2):
        """Cruzamiento aritmetico BLX-alpha."""
        if random.random() > self.tasa_cruce:
            return p1.copy(), p2.copy()

        hijo1 = np.zeros(5)
        hijo2 = np.zeros(5)
        for i in range(5):
            cmin = min(p1[i], p2[i])
            cmax = max(p1[i], p2[i])
            rango = cmax - cmin
            lo = cmin - rango * self.alpha_blx
            hi = cmax + rango * self.alpha_blx
            hijo1[i] = random.uniform(lo, hi)
            hijo2[i] = random.uniform(lo, hi)

        # Recortar a los limites
        hijo1 = np.clip(hijo1, self.LIMITES_INF, self.LIMITES_SUP)
        hijo2 = np.clip(hijo2, self.LIMITES_INF, self.LIMITES_SUP)
        return hijo1, hijo2

    # --------------------------------------------------------
    def _mutar(self, cromosoma):
        """Mutacion gaussiana con sigma proporcional al rango."""
        for i in range(5):
            if random.random() < self.tasa_mutacion:
                sigma = 0.1 * (self.LIMITES_SUP[i] - self.LIMITES_INF[i])
                cromosoma[i] += random.gauss(0.0, sigma)
        return np.clip(cromosoma, self.LIMITES_INF, self.LIMITES_SUP)

    # --------------------------------------------------------
    def optimizar(self, superficie_mz=1.0, riesgo_roya_pct=65.0, verbose=False):
        """
        Ejecuta el bucle evolutivo y devuelve la mejor solucion.
        """
        self._cargar_precios()  # refrescar precios al iniciar

        # Poblacion inicial uniforme
        poblacion = np.random.uniform(
            self.LIMITES_INF, self.LIMITES_SUP,
            size=(self.tam_poblacion, 5),
        )

        mejor_global = None
        mejor_aptitud = -np.inf

        for gen in range(self.generaciones):
            aptitudes = [self._fitness(ind, riesgo_roya_pct)[0]
                         for ind in poblacion]

            # Ordenar
            orden = np.argsort(aptitudes)[::-1]
            poblacion = poblacion[orden]
            aptitudes = [aptitudes[i] for i in orden]

            if aptitudes[0] > mejor_aptitud:
                mejor_aptitud = aptitudes[0]
                mejor_global  = poblacion[0].copy()

            if verbose and (gen % 10 == 0 or gen == self.generaciones - 1):
                print(f"Gen {gen:02d} | Mejor aptitud: {aptitudes[0]:,.2f} C$")

            # Nueva generacion
            nueva_pob = [poblacion[i].copy() for i in range(self.elite)]

            while len(nueva_pob) < self.tam_poblacion:
                p1 = self._seleccion_torneo(poblacion, aptitudes)
                p2 = self._seleccion_torneo(poblacion, aptitudes)
                h1, h2 = self._cruzar_blx(p1, p2)
                nueva_pob.append(self._mutar(h1))
                if len(nueva_pob) < self.tam_poblacion:
                    nueva_pob.append(self._mutar(h2))

            poblacion = np.array(nueva_pob)

        # Evaluacion final
        beneficio, rendimiento, costo = self._fitness(
            mejor_global, riesgo_roya_pct
        )

        return {
            "superficie_mz": superficie_mz,
            "dosis_por_mz": {
                "riego_m3":    round(float(mejor_global[0]), 1),
                "N_kg":        round(float(mejor_global[1]), 1),
                "P_kg":        round(float(mejor_global[2]), 1),
                "K_kg":        round(float(mejor_global[3]), 1),
                "fungicida_L": round(float(mejor_global[4]), 2),
            },
            "rendimiento_qq_mz":  round(rendimiento, 2),
            "costo_total_nio":    round(costo * superficie_mz, 2),
            "beneficio_neto_nio": round(beneficio * superficie_mz, 2),
            "precio_cafe_nio_qq": round(self.precio_cafe_cs, 2),
            "riesgo_roya_pct":    riesgo_roya_pct,
        }


# ------------------------------------------------------------
# Prueba local
# ------------------------------------------------------------
if __name__ == "__main__":
    # Verificar continuidad de la penalizacion graduada
    print("=== Curva de penalizacion fitosanitaria ===")
    for d in (0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.65):
        p = OptimizacionGenetica._penalizacion_fitosanitaria(d)
        print(f"  deficit={d:.2f} -> penalizacion C$ {p:>8.2f}")

    print("\n=== Optimizacion con graduacion aplicada ===")
    ag = OptimizacionGenetica(generaciones=40, tam_poblacion=60)
    resultado = ag.optimizar(
        superficie_mz=1.0,
        riesgo_roya_pct=65.0,
        verbose=True,
    )
    print("\n=== Resultado final ===")
    for k, v in resultado.items():
        print(f"{k:22s}: {v}")