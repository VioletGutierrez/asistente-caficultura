# ============================================================
# modulos/chatbot.py
# Chatbot con intents, entidades y flujos del documento
# Referencia: IA_Entregable1.pdf Seccion 9
# Incluye: 17 deptos, 16 enfermedades, auto-clima, unidades de
# superficie, cruce imagen/sintoma, imagenes en reporte
# ============================================================
import re
import time
import uuid
from modulos.motor_reglas       import MotorReglas
from modulos.red_bayesiana      import RedBayesianaCafe
from modulos.algoritmo_genetico import OptimizacionGenetica
from modulos.vision_cnn         import ClasificadorVisionCNN, SINTOMA_A_CLASE
from modulos.clima_api          import ModuloClima, DEPTO_COORDS
from modulos.precios            import leer_precios_actuales, actualizar_precios
from modulos.reporte_pdf        import generar_reporte, exportar_a_descargas
from modulos.llm_fallback       import OraculoAgronomoLLM
from modulos.kpis               import registrar_turno
from modulos.db                 import (
    crear_sesion, guardar_mensaje,
    guardar_diagnostico, guardar_optimizacion,
)


DEPARTAMENTOS = list(DEPTO_COORDS.keys())

_DEPTO_ALIASES = {
    "boaco": "Boaco", "carazo": "Carazo", "chinandega": "Chinandega",
    "chontales": "Chontales",
    "esteli": "Esteli", "estelí": "Esteli",
    "granada": "Granada", "jinotega": "Jinotega",
    "leon": "Leon", "león": "Leon",
    "madriz": "Madriz", "managua": "Managua", "masaya": "Masaya",
    "matagalpa": "Matagalpa",
    "nueva segovia": "Nueva Segovia",
    "rio san juan": "Rio San Juan", "río san juan": "Rio San Juan",
    "rivas": "Rivas",
    "racen": "RACCN", "raccn": "RACCN",
    "costa caribe norte": "RACCN", "bilwi": "RACCN",
    "racas": "RACCS", "raccs": "RACCS",
    "costa caribe sur": "RACCS", "bluefields": "RACCS",
}


NO_SE = (
    "no se", "no sé", "no lo se", "no lo sé",
    "no estoy seguro", "no estoy segura", "no tengo",
    "no tengo idea", "no recuerdo", "desconozco",
    "?", "??", "???", "nose", "ns",
)


# Factores de conversion a manzanas
SUPERFICIE_FACTORES = {
    "manzana": 1.0, "mz": 1.0,
    "hectarea": 1.4184, "hectárea": 1.4184, "ha": 1.4184,
    "m2": 0.00014184, "m²": 0.00014184, "metro": 0.00014184,
    "acre": 0.5735,
}


INTENTS = {
    "Consultar_Diagnostico_Sintoma": [
        r"mancha", r"s[ií]ntoma", r"enfermed", r"pustul", r"roya",
        r"antracnosis", r"ojo de gallo", r"hoja.{0,10}amarilla",
        r"broca", r"minador", r"nematodo", r"telara", r"telaraña",
        r"ra[ií]z", r"clorosis", r"deficien", r"nutri",
    ],
    "Sincronizar_Clima_Entorno": [
        r"clima", r"tiempo", r"lluvia", r"temperatura", r"humedad",
    ],
    "Analizar_Imagen_Hoja": [
        r"foto", r"imagen", r"adjunt", r"analiz.{0,10}hoja",
    ],
    "Optimizar_Plan_Fertilizacion_Riego": [
        r"fertiliz", r"riego", r"dosis", r"plan.{0,10}nutric",
        r"manzana",
    ],
    "Generar_Reporte_PDF": [
        r"reporte", r"pdf", r"documento",
    ],
    "Consultar_Precios_Mercado": [
        r"precio", r"mercado", r"c[oó]rdoba", r"cambio",
    ],
    "Solicitar_Ayuda": [
        r"ayuda", r"qu[eé] puedes", r"funciones", r"c[oó]mo funciona",
    ],
    "Confirmar_Accion": [
        r"^s[ií]$", r"^confirmo", r"^de acuerdo", r"^adelante",
        r"^ok$", r"^proceda",
    ],
    "Cancelar_Operacion": [
        r"^cancel", r"^olv[ií]dalo", r"^detente", r"^para$",
    ],
}


_SINTOMAS_MAP = {
    "manchas naranjas":  "manchas_naranjas",
    "mancha naranja":    "manchas_naranjas",
    "polvo amarillo":    "polvo_amarillo",
    "pustulas":          "pustulas",
    "pústulas":          "pustulas",
    "manchas negras":    "manchas_negras",
    "lesiones hundidas": "lesiones_hundidas",
    "muerte de ramas":   "muerte_ramas",
    "manchas circulares":"manchas_circulares",
    "borde cafe":        "borde_cafe",
    "borde café":        "borde_cafe",
    "centro gris":       "centro_gris",
    "hojas amarillas":   "hojas_amarillas",
    "clorosis uniforme": "clorosis_uniforme",
    "borde hoja amarillo":"borde_hojas_amarillo",
    "necrosis marginal": "necrosis_marginal",
    "telarana blanca":   "telarana_blanca",
    "telaraña blanca":   "telarana_blanca",
    "hilos blancos":     "hilos_blancos",
    "muerte descendente":"muerte_descendente",
    "mancha cafe rojiza":"mancha_cafe_rojiza",
    "halo amarillo":     "halo_amarillo",
    "centro blanco":     "centro_blanco",
    "mancha grasosa":    "mancha_grasosa",
    "mancha cafe oscura":"mancha_cafe_oscura",
    "hoja pegada":       "hoja_pegada",
    "raiz negra":        "raiz_negra",
    "raíz negra":        "raiz_negra",
    "necrosis radicular":"necrosis_radicular",
    "muerte subita":     "muerte_subita",
    "muerte súbita":     "muerte_subita",
    "perforaciones fruto":"perforaciones_fruto",
    "granos perforados":"granos_perforados",
    "broca visible":    "broca_visible",
    "galerias hoja":    "galerias_hoja",
    "galerías hoja":    "galerias_hoja",
    "minas hoja":       "minas_hoja",
    "hoja blanquecina": "hoja_blanquecina",
    "raices nudosas":   "raices_nudosas",
    "raíces nudosas":   "raices_nudosas",
    "amarillamiento general":"amarillamiento_general",
    "enanismo":         "enanismo",
    "hojas purpuras":   "hojas_purpuras",
    "hojas púrpuras":   "hojas_purpuras",
    "tallos purpura":   "tallos_purpura",
    "tallos púrpura":   "tallos_purpura",
    "margen hoja quemado":"margen_hoja_quemado",
    "hojas viejas amarillas":"hojas_viejas_amarillas",
    "clorosis intervenal":  "clorosis_intervenal_amarilla",
    "hojas viejas verde centro":"hojas_viejas_verde_centro",
    "hojas pequenas":   "hojas_pequenas",
    "hojas pequeñas":   "hojas_pequenas",
    "brotes arrugados": "brotes_arrugados",
    "hojas deformadas nuevas":"hojas_deformadas_nuevas",
    "entrenudos cortos":"entrenudos_cortos",
}


class ChatbotCaficultura:
    """Asistente conversacional con flujos guiados."""

    def __init__(self, perfil="pequeno_productor"):
        self.motor = MotorReglas()
        self.bayes = RedBayesianaCafe()
        self.ag    = OptimizacionGenetica(generaciones=40, tam_poblacion=60)
        self.cnn   = ClasificadorVisionCNN()
        self.clima = ModuloClima(departamento="Matagalpa")
        self.llm   = OraculoAgronomoLLM()

        self.ctx = {
            "perfil":               perfil,
            "flujo_pendiente":      None,
            "departamento_zona":    "Matagalpa",
            "imagenes_analizadas":  [],
            "superficie_manzanas":  1.0,
            "superficie_original":  {"valor": 1.0, "unidad": "manzana"},
        }
        self.sesion_uuid  = str(uuid.uuid4())[:8]
        self.sesion_db_id = crear_sesion(self.sesion_uuid, perfil=perfil)

    # --------------------------------------------------------
    def set_perfil(self, perfil):
        self.ctx["perfil"] = perfil

    def set_departamento(self, depto):
        if depto in DEPARTAMENTOS:
            self.ctx["departamento_zona"] = depto
            self.clima.set_departamento(depto)

    def set_superficie(self, valor, unidad="manzana"):
        """Setea superficie con conversion automatica a manzanas."""
        factor = SUPERFICIE_FACTORES.get(unidad.lower(), 1.0)
        self.ctx["superficie_manzanas"] = round(valor * factor, 4)
        self.ctx["superficie_original"] = {"valor": valor, "unidad": unidad}

    # --------------------------------------------------------
    def registrar_imagen(self, ruta, clase, confianza, nota_cruce=None):
        """Registra una imagen analizada para incluirla en el reporte."""
        self.ctx.setdefault("imagenes_analizadas", []).append({
            "ruta":       ruta,
            "clase":      clase,
            "confianza":  float(confianza),
            "fecha":      time.strftime("%Y-%m-%d %H:%M"),
            "nota_cruce": nota_cruce,
        })

    # --------------------------------------------------------
    def detectar_intent(self, texto):
        t = texto.lower()
        for intent, patrones in INTENTS.items():
            for p in patrones:
                if re.search(p, t):
                    return intent
        return "Consultar_Oraculo_LLM_Fallback"

    # --------------------------------------------------------
    def extraer_entidades(self, texto):
        t = texto.lower()
        ents = {}
        flujo = self.ctx.get("flujo_pendiente")
        stripped = t.strip()

        # --- "no se" durante un flujo pendiente ---
        if flujo in ("temp", "hr", "lluvia") and stripped in NO_SE:
            ents["_auto_clima"] = True
            return ents

        # @superficie_manzanas con unidades
        m = re.search(
            r"(\d+(?:[.,]\d+)?)\s*(manzana|mz|hectarea|hectárea|ha|"
            r"m2|m²|metro|acre)",
            t,
        )
        if m:
            valor = float(m.group(1).replace(",", "."))
            unidad = m.group(2).lower()
            factor = SUPERFICIE_FACTORES.get(unidad, 1.0)
            ents["superficie_manzanas"] = round(valor * factor, 4)
            ents["superficie_original"] = {"valor": valor, "unidad": unidad}
        else:
            m = re.search(r"(\d+(?:\.\d+)?)\s*manzana", t)
            if m:
                ents["superficie_manzanas"] = float(m.group(1))
                ents["superficie_original"] = {
                    "valor": float(m.group(1)), "unidad": "manzana",
                }

        # @temperatura
        m = re.search(r"(\d+(?:\.\d+)?)\s*[°]?\s*(?:c\b|grados)", t)
        if m:
            ents["temperatura"] = float(m.group(1))
        elif flujo == "temp":
            m = re.search(r"(\d+(?:\.\d+)?)", t)
            if m:
                ents["temperatura"] = float(m.group(1))

        # @humedad_relativa
        m = re.search(r"(\d+)\s*%\s*(?:de\s*)?humedad", t)
        if m:
            ents["humedad_relativa"] = float(m.group(1))
        elif flujo == "hr":
            m = re.search(r"(\d+)", t)
            if m:
                ents["humedad_relativa"] = float(m.group(1))

        # @lluvia_previa
        if any(w in t for w in ("llovio", "llovió", "si llovio",
                                "si, llovio", "sí, llovió")):
            ents["lluvia_previa"] = True
        elif flujo == "lluvia":
            if stripped in ("si", "sí", "s", "yes", "afirmativo"):
                ents["lluvia_previa"] = True
            elif stripped in ("no", "n", "negativo"):
                ents["lluvia_previa"] = False

        # @sintoma_observado
        for kw, val in _SINTOMAS_MAP.items():
            if kw in t:
                ents["sintoma_observado"] = val
                break

        # @fase_fenologica
        for kw, val in {
            "floracion": "floracion", "floración": "floracion",
            "llenado de grano": "llenado_grano", "llenado_grano": "llenado_grano",
            "maduración": "madurez", "madurez": "madurez",
            "crecimiento": "crecimiento", "vegetativo": "vegetativo",
        }.items():
            if kw in t:
                ents["fase_fenologica"] = val
                break

        # @departamento_zona
        for alias, canon in _DEPTO_ALIASES.items():
            if alias in t:
                ents["departamento_zona"] = canon
                break

        # @tipo_insumo
        if any(w in t for w in ("fertiliz", "urea", "npk", "18-46-0",
                                "ferticafe", "ferticafé")):
            ents["tipo_insumo"] = "fertilizante"
        elif any(w in t for w in ("fungicid", "clorotalonil",
                                  "cobre", "triadimefon", "triadimefón",
                                  "mancozeb", "benomil")):
            ents["tipo_insumo"] = "fungicida"
        elif any(w in t for w in ("insecticid", "beauveria",
                                  "trichoderma", "paecilomyces")):
            ents["tipo_insumo"] = "biologico"
        elif any(w in t for w in ("riego", "agua", "m3")):
            ents["tipo_insumo"] = "agua"

        # @confirmacion
        if stripped in ("si", "sí", "confirmo", "de acuerdo",
                        "adelante", "ok", "proceda"):
            ents["confirmacion"] = True
        elif stripped in ("no", "cancela", "negativo", "olvidalo"):
            ents["confirmacion"] = False

        # @imagen_hoja
        m = re.search(r"([\w\-/\\]+\.(?:jpg|jpeg|png))", t)
        if m:
            ents["imagen_hoja"] = m.group(1)

        return ents

    # --------------------------------------------------------
    def _autocompletar_clima(self):
        """Consulta Open-Meteo y llena temperatura, HR y lluvia en ctx."""
        depto = self.ctx.get("departamento_zona", "Matagalpa")
        self.clima.set_departamento(depto)
        datos = self.clima.obtener_datos_actuales()
        self.ctx["temperatura"]      = datos["temperatura"]
        self.ctx["humedad_relativa"] = datos["humedad_relativa"]
        self.ctx["lluvia_previa"]    = datos["precipitacion_24h"] > 0
        self.ctx["clima_auto"]       = datos
        return datos

    # --------------------------------------------------------
    def responder(self, texto_usuario):
        t0 = time.time()

        flujo = self.ctx.get("flujo_pendiente")
        if flujo in ("lluvia", "temp", "hr"):
            intent = "Consultar_Diagnostico_Sintoma"
        elif flujo == "superficie":
            intent = "Optimizar_Plan_Fertilizacion_Riego"
        else:
            intent = self.detectar_intent(texto_usuario)

        ents = self.extraer_entidades(texto_usuario)

        # --- Auto-clima si el usuario dijo "no se" ---
        if ents.pop("_auto_clima", False):
            try:
                datos = self._autocompletar_clima()
                ents["_auto_clima_ok"] = datos["fuente"]
            except Exception:
                ents["_auto_clima_ok"] = "fallo"

        self.ctx.update(ents)

        # Si describio sintoma pero el regex no lo clasifico -> diagnostico
        if intent == "Consultar_Oraculo_LLM_Fallback":
            if "sintoma_observado" in ents or "fase_fenologica" in ents:
                intent = "Consultar_Diagnostico_Sintoma"

        guardar_mensaje(self.sesion_db_id, "usuario", texto_usuario, intent)

        respuesta, intent_final, error = self._despachar(intent, texto_usuario)

        guardar_mensaje(self.sesion_db_id, "asistente",
                        respuesta, intent_final)

        tiempo = time.time() - t0
        registrar_turno(
            sesion_uuid=self.sesion_uuid,
            intent=intent_final,
            entidades=ents,
            respuesta=respuesta,
            tiempo_seg=tiempo,
            fallback=(intent_final == "Consultar_Oraculo_LLM_Fallback"),
            error=error,
        )

        return respuesta, intent_final

    # --------------------------------------------------------
    def _despachar(self, intent, texto_usuario):
        try:
            if intent == "Cancelar_Operacion":
                self.ctx["flujo_pendiente"] = None
                return ("Operacion cancelada. Puede iniciar una nueva consulta.",
                        intent, False)

            if intent == "Confirmar_Accion":
                return ("Accion confirmada. Proceda con la siguiente instruccion "
                        "o escriba 'ayuda' para ver opciones.",
                        intent, False)

            if intent == "Solicitar_Ayuda":
                return (self._texto_ayuda(), intent, False)

            if intent == "Consultar_Diagnostico_Sintoma":
                return self._flujo_diagnostico()

            if intent == "Sincronizar_Clima_Entorno":
                depto = self.ctx.get("departamento_zona", "Matagalpa")
                self.clima.set_departamento(depto)
                datos = self.clima.obtener_datos_actuales()
                self.ctx["clima"] = {
                    "temperatura":      datos["temperatura"],
                    "humedad_relativa": datos["humedad_relativa"],
                    "lluvia_previa":    datos["precipitacion_24h"] > 0,
                    "fuente":           datos["fuente"],
                }
                self.ctx["temperatura"]      = datos["temperatura"]
                self.ctx["humedad_relativa"] = datos["humedad_relativa"]
                self.ctx["lluvia_previa"]    = datos["precipitacion_24h"] > 0
                return (
                    f"Clima en {depto}: {datos['temperatura']} C, "
                    f"HR {datos['humedad_relativa']} %, "
                    f"lluvia 24h: {datos['precipitacion_24h']} mm. "
                    f"Fuente: {datos['fuente']}.",
                    intent, False,
                )

            if intent == "Optimizar_Plan_Fertilizacion_Riego":
                return self._flujo_optimizacion()

            if intent == "Generar_Reporte_PDF":
                return self._flujo_reporte()

            if intent == "Consultar_Precios_Mercado":
                p = actualizar_precios()
                return (
                    f"Indicadores de mercado:\n"
                    f"  - Precio del cafe: {p['precio_cafe_oro_qq_usd']} USD/qq\n"
                    f"  - Tipo de cambio: {p['tipo_cambio_usd_nio']} NIO/USD\n"
                    f"  - Urea: {p['precio_urea_qq_nio']} C$/qq\n"
                    f"  - KCl: {p['precio_kcl_qq_nio']} C$/qq\n"
                    f"  - Fungicida: {p['precio_fungicida_litro_nio']} C$/L\n"
                    f"  - Actualizado: {p['ultima_actualizacion']}",
                    intent, False,
                )

            if intent == "Analizar_Imagen_Hoja":
                return ("Para analizar una hoja, use el uploader del chat "
                        "o el tab 'Analizar Hoja' de la interfaz web.",
                        intent, False)

            if self.llm._esta_corriendo():
                contexto = self._contexto_finca_texto()
                return (self.llm.consultar_oraculo(texto_usuario, contexto),
                        "Consultar_Oraculo_LLM_Fallback", False)

            return ("No comprendi su consulta y el Oraculo LLM no esta disponible. "
                    "Escriba 'ayuda' para ver funciones.",
                    "Consultar_Oraculo_LLM_Fallback", False)

        except Exception as e:
            return (f"Error interno: {e}", intent, True)

    # --------------------------------------------------------
    def _flujo_diagnostico(self):
        if "lluvia_previa" not in self.ctx:
            self.ctx["flujo_pendiente"] = "lluvia"
            return ("Ha llovido fuerte en su parcela en las ultimas 24 horas? "
                    "(Si/No, o escriba 'no se' y lo obtengo automatico)",
                    "Consultar_Diagnostico_Sintoma", False)

        if "temperatura" not in self.ctx:
            self.ctx["flujo_pendiente"] = "temp"
            return ("Cual es la temperatura aproximada en su zona? "
                    "(en grados C, o escriba 'no se' y la obtengo automatico)",
                    "Consultar_Diagnostico_Sintoma", False)

        if "humedad_relativa" not in self.ctx:
            self.ctx["flujo_pendiente"] = "hr"
            return ("Cual es la humedad relativa aproximada? "
                    "(en %, o escriba 'no se' y la obtengo automatico)",
                    "Consultar_Diagnostico_Sintoma", False)

        self.ctx["flujo_pendiente"] = None
        hechos = {
            "sintoma_observado": self.ctx.get("sintoma_observado", ""),
            "humedad_relativa":  self.ctx["humedad_relativa"],
            "temperatura":       self.ctx["temperatura"],
            "lluvia_previa":     self.ctx["lluvia_previa"],
        }
        diags = self.motor.inferir(hechos)
        self.ctx["diagnosticos"] = diags

        riesgo = self.bayes.evaluar(
            lluvia=hechos["lluvia_previa"],
            hr=hechos["humedad_relativa"],
            temp=hechos["temperatura"],
            sintoma=hechos["sintoma_observado"],
        )
        self.ctx["riesgo"] = riesgo

        principal = diags[0]
        guardar_diagnostico(
            self.sesion_db_id,
            principal.get("regla_id"),
            principal.get("diagnostico", ""),
            riesgo,
        )

        nota = ""
        if "clima_auto" in self.ctx:
            nota = (f"\n(Nota: temperatura y humedad obtenidas de "
                    f"{self.ctx['clima_auto']['fuente']})")

        respuesta = (
            f"Diagnostico presuntivo: {principal['diagnostico']}\n"
            f"Recomendacion: {principal['recomendacion']}\n"
            f"Niveles de riesgo (modelo probabilistico):\n"
            f"  - Roya:        {riesgo['roya']*100:.1f}%\n"
            f"  - Antracnosis: {riesgo['antracnosis']*100:.1f}%\n"
            f"  - Ojo de gallo:{riesgo['ojo_gallo']*100:.1f}%\n"
            f"Riesgo global: {riesgo['riesgo_global']*100:.1f}%"
            f"{nota}"
        )
        return (respuesta, "Consultar_Diagnostico_Sintoma", False)

    # --------------------------------------------------------
    def _flujo_optimizacion(self):
        sup = self.ctx.get("superficie_manzanas", 1.0)
        riesgo_pct = self.ctx.get("riesgo", {}).get("roya", 0.65) * 100
        res = self.ag.optimizar(
            superficie_mz=sup, riesgo_roya_pct=riesgo_pct, verbose=False,
        )
        self.ctx["optimizacion"] = res
        guardar_optimizacion(self.sesion_db_id, res)

        d = res["dosis_por_mz"]
        depto = self.ctx.get("departamento_zona", "Matagalpa")

        # Mencionar si la superficie vino en otra unidad
        orig = self.ctx.get("superficie_original", {})
        nota_sup = ""
        if orig and orig.get("unidad", "manzana") != "manzana":
            nota_sup = f" ({orig['valor']} {orig['unidad']})"

        respuesta = (
            f"Plan bioeconomico optimizado para {sup} manzanas{nota_sup} "
            f"en {depto}:\n"
            f"  - Riego:      {d['riego_m3']} m3/mz\n"
            f"  - Nitrogeno:  {d['N_kg']} kg/mz\n"
            f"  - Fosforo:    {d['P_kg']} kg/mz\n"
            f"  - Potasio:    {d['K_kg']} kg/mz\n"
            f"  - Fungicida:  {d['fungicida_L']} L/mz\n"
            f"  - Rendimiento esperado: {res['rendimiento_qq_mz']} qq/mz\n"
            f"  - Costo total: C$ {res['costo_total_nio']:,.2f}\n"
            f"  - Beneficio neto: C$ {res['beneficio_neto_nio']:,.2f}"
        )
        return (respuesta, "Optimizar_Plan_Fertilizacion_Riego", False)

    # --------------------------------------------------------
    def _flujo_reporte(self):
        # --- AUTO-COMPLETADO ---
        if not self.ctx.get("clima"):
            try:
                depto = self.ctx.get("departamento_zona", "Matagalpa")
                self.clima.set_departamento(depto)
                d = self.clima.obtener_datos_actuales()
                self.ctx["clima"] = {
                    "temperatura":      d["temperatura"],
                    "humedad_relativa": d["humedad_relativa"],
                    "lluvia_previa":    d["precipitacion_24h"] > 0,
                    "fuente":           d["fuente"],
                }
                self.ctx.setdefault("temperatura",      d["temperatura"])
                self.ctx.setdefault("humedad_relativa", d["humedad_relativa"])
                self.ctx.setdefault("lluvia_previa",    d["precipitacion_24h"] > 0)
            except Exception:
                pass

        if not self.ctx.get("diagnosticos"):
            sintoma = self.ctx.get("sintoma_observado", "")
            if sintoma:
                hechos = {
                    "sintoma_observado": sintoma,
                    "humedad_relativa":  self.ctx.get("humedad_relativa", 80),
                    "temperatura":       self.ctx.get("temperatura", 22),
                    "lluvia_previa":     self.ctx.get("lluvia_previa", False),
                }
                self.ctx["diagnosticos"] = self.motor.inferir(hechos)
                self.ctx["riesgo"] = self.bayes.evaluar(
                    lluvia=hechos["lluvia_previa"],
                    hr=hechos["humedad_relativa"],
                    temp=hechos["temperatura"],
                    sintoma=hechos["sintoma_observado"],
                )

        if not self.ctx.get("optimizacion"):
            try:
                sup = self.ctx.get("superficie_manzanas", 1.0)
                riesgo_pct = self.ctx.get("riesgo", {}).get("roya", 0.65) * 100
                self.ctx["optimizacion"] = self.ag.optimizar(
                    superficie_mz=sup, riesgo_roya_pct=riesgo_pct,
                    verbose=False,
                )
            except Exception:
                pass

        # --- CRUCE IMAGEN + SINTOMA ---
        sintoma = self.ctx.get("sintoma_observado", "")
        if sintoma and self.ctx.get("imagenes_analizadas"):
            clase_esperada = SINTOMA_A_CLASE.get(sintoma)
            if clase_esperada:
                for img in self.ctx["imagenes_analizadas"]:
                    if img.get("clase") == "Sana" and not img.get("nota_cruce"):
                        img["clase_original"] = "Sana"
                        img["clase"] = clase_esperada
                        img["confianza"] = max(img.get("confianza", 0.55), 0.55)
                        img["nota_cruce"] = (
                            f"Corregida de 'Sana' a '{clase_esperada}' "
                            f"por sintomas declarados."
                        )

        # --- Armar datos ---
        datos = {
            "sesion_id":           self.sesion_uuid,
            "zona":                self.ctx.get("departamento_zona", "Matagalpa"),
            "superficie_manzanas": self.ctx.get("superficie_manzanas", 1.0),
            "superficie_original": self.ctx.get("superficie_original"),
            "clima":               self.ctx.get("clima", {}),
            "diagnosticos":        self.ctx.get("diagnosticos", []),
            "riesgo":              self.ctx.get("riesgo", {}),
            "optimizacion":        self.ctx.get("optimizacion", {}),
            "imagenes":            self.ctx.get("imagenes_analizadas", []),
        }
        nombre = f"reporte_{self.sesion_uuid}.pdf"
        ruta = generar_reporte(datos, nombre=nombre)
        ruta_descargas = exportar_a_descargas(ruta)

        secciones = sum([
            bool(datos["clima"]),
            bool(datos["diagnosticos"]),
            bool(datos["riesgo"]),
            bool(datos["optimizacion"]),
            bool(datos["imagenes"]),
        ])

        mensaje = (
            f"Reporte PDF generado ({secciones}/5 secciones):\n"
            f"  - Respaldo: {ruta}\n"
        )
        if ruta_descargas:
            mensaje += f"  - Copia en Descargas: {ruta_descargas}\n"
            mensaje += "  >> Use el boton 'Descargar PDF' debajo."
        else:
            mensaje += "  (No se pudo copiar a Descargas; use el boton.)"

        return (mensaje, "Generar_Reporte_PDF", False)

    # --------------------------------------------------------
    def _texto_ayuda(self):
        return (
            "Puedo ayudarle con:\n"
            "  1. Diagnostico fitosanitario (16 enfermedades):\n"
            "     roya, antracnosis, ojo de gallo, mal de hilachas,\n"
            "     mancha de hierro, mancha mantecosa, pudricion radicular,\n"
            "     broca, minador, nematodos, def. N/P/K/Mg/Zn/B.\n"
            "     >> Si no sabe temperatura/humedad/lluvia, escriba 'no se'\n"
            "        y las obtengo automatico del clima de su zona.\n"
            "  2. Clima: temperatura, humedad y lluvia en tiempo real.\n"
            "  3. Optimizacion: plan de fertilizacion y riego.\n"
            "  4. Reportes PDF: se guardan en salidas/ Y en Descargas.\n"
            "  5. Precios de mercado: cafe, tipo de cambio e insumos.\n"
            "  6. Consultas abiertas: Oraculo LLM.\n"
            "  7. Superficie: escriba '5 ha' o '2 acre' o use el panel lateral.\n"
            "Escriba 'cancelar' para detener cualquier flujo en curso."
        )

    # --------------------------------------------------------
    def _contexto_finca_texto(self):
        partes = []
        for k in ("departamento_zona", "superficie_manzanas",
                  "superficie_original", "clima", "diagnosticos",
                  "riesgo", "fase_fenologica", "tipo_insumo"):
            v = self.ctx.get(k)
            if v:
                partes.append(f"{k}={v}")
        return "; ".join(partes) if partes else "Sin datos previos."


# ------------------------------------------------------------
if __name__ == "__main__":
    bot = ChatbotCaficultura()
    bot.set_departamento("Granada")
    bot.set_superficie(2, "ha")
    print(f"Chatbot listo. Depto: {bot.ctx['departamento_zona']} | "
          f"Superficie: {bot.ctx['superficie_manzanas']} manzanas")
    print("-" * 55)
    for texto in [
        "Tengo manchas naranjas en las hojas",
        "no se",
        "no se",
        "no se",
        "generar reporte",
    ]:
        print(f"\nUSUARIO: {texto}")
        r, i = bot.responder(texto)
        print(f"ASISTENTE [{i}]: {r[:280]}")