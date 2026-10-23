# ============================================================
# modulos/mitscherlich_baule.py
# Modelo fisiologico-bioeconomico de Mitscherlich-Baule
# Referencia: IA.docx Pag. 30-31
# Formula: Y(x) = A * PROD(1 - exp(-c_i * (x_i + d_i)))
# ============================================================
import numpy as np


class MitscherlichBaule:
    """
    Modela la respuesta del cafeto a la aplicacion de nutrientes y agua.

    Parametros
    ----------
    A  : rendimiento maximo asintotico (qq oro / manzana)
    c  : coeficientes de eficiencia fisiologica por factor
    d  : disponibilidad basal del factor en el suelo (constante)

    Orden de factores:
        indice 0 = agua de riego (m3/mz)
        indice 1 = nitrogeno (kg/mz)
        indice 2 = fosforo (kg/mz)
        indice 3 = potasio (kg/mz)
    """

    def __init__(
        self,
        A  = 35.0,
        c  = (0.015, 0.020, 0.035, 0.025),
        d  = (50.0,  30.0,  15.0,  25.0),
    ):
        self.A = float(A)
        self.c = tuple(c)
        self.d = tuple(d)

    # --------------------------------------------------------
    def rendimiento(self, agua, N, P, K):
        """
        Retorna el rendimiento esperado en quintales de cafe oro
        por manzana, dadas las dosis de cada factor.
        """
        x = (agua, N, P, K)
        y = self.A
        for i in range(4):
            y *= (1.0 - np.exp(-self.c[i] * (x[i] + self.d[i])))
        return float(y)

    # --------------------------------------------------------
    def fraccion_suficiencia(self, factor_idx, dosis):
        """
        Progresion de suficiencia w_n = 1 - (0.5)^n
        (equivalente a 1 - exp(-c*(x+d)) con la curva ajustada).
        Util para reportes.
        """
        c_i = self.c[factor_idx]
        d_i = self.d[factor_idx]
        return float(1.0 - np.exp(-c_i * (dosis + d_i)))


# ------------------------------------------------------------
# Prueba local
# ------------------------------------------------------------
if __name__ == "__main__":
    mb = MitscherlichBaule()
    print("Rendimiento maximo teorico A =", mb.A, "qq/mz")
    print("-" * 55)
    escenarios = [
        (50,   30,  15,  25),
        (120,  85,  40,  60),
        (200, 120,  60,  90),
        (350, 145,  75, 110),
    ]
    print(f"{'Agua':>6} {'N':>6} {'P':>6} {'K':>6} {'Rendimiento':>14}")
    for a, n, p, k in escenarios:
        print(f"{a:>6} {n:>6} {p:>6} {k:>6} {mb.rendimiento(a,n,p,k):>14.2f}")