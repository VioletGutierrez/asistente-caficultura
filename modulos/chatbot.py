# ============================================================
# modulos/chatbot.py
# Sistema Experto con restricciones por perfil
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
    crear_sesion, guardar_mensaje, guardar_diagnostico, guardar_optimizacion,
)

DEPARTAMENTOS = list(DEPTO_COORDS.keys())
_DEPTO_ALIASES = { "boaco": "Boaco", "carazo": "Carazo", "chinandega": "Chinandega", "chontales": "Chontales", "esteli": "Esteli", "estelí": "Esteli", "granada": "Granada", "jinotega": "Jinotega", "leon": "Leon", "león": "Leon", "madriz": "Madriz", "managua": "Managua", "masaya": "Masaya", "matagalpa": "Matagalpa", "nueva segovia": "Nueva Segovia", "rio san juan": "Rio San Juan", "río san juan": "Rio San Juan", "rivas": "Rivas", "racen": "RACCN", "raccn": "RACCN", "costa caribe norte": "RACCN", "bilwi": "RACCN", "racas": "RACCS", "raccs": "RACCS", "costa caribe sur": "RACCS", "bluefields": "RACCS" }
NO_SE = ("no se", "no sé", "no lo se", "no lo sé", "no estoy seguro", "no estoy segura", "no tengo", "no tengo idea", "no recuerdo", "desconozco", "?", "??", "???", "nose", "ns")
SUPERFICIE_FACTORES = {"manzana": 1.0, "mz": 1.0, "hectarea": 1.4184, "hectárea": 1.4184, "ha": 1.4184, "m2": 0.00014184, "m²": 0.00014184, "metro": 0.00014184, "acre": 0.5735}

COMANDOS_DIRECTOS = {
    "Generar_Reporte_PDF": [r"^reporte", r"^generar reporte", r"^pdf", r"^documento"],
    "Optimizar_Plan_Fertilizacion_Riego": [r"^optimizar", r"^fertilizacion", r"^dosis", r"^plan de riego"],
    "Sincronizar_Clima_Entorno": [r"^clima", r"^tiempo", r"^va a llover", r"^temperatura actual"],
    "Consultar_Precios_Mercado": [r"^precio", r"^mercado", r"^c[oó]rdoba", r"^cambio", r"^cuanto cuesta"],
    "Solicitar_Ayuda": [r"^ayuda", r"^qu[eé] puedes", r"^funciones", r"^c[oó]mo funciona"],
    "Cancelar_Operacion": [r"^cancel", r"^olv[ií]dalo", r"^detente", r"^para$"],
}

_SINTOMAS_MAP = {
    "manchas naranjas": "manchas_naranjas", "polvo amarillo": "polvo_amarillo", "pustulas": "pustulas",
    "manchas negras": "manchas_negras", "lesiones hundidas": "lesiones_hundidas", "muerte de ramas": "muerte_ramas",
    "hojas amarillas": "hojas_amarillas", "clorosis uniforme": "clorosis_uniforme",
    "telarana blanca": "telarana_blanca", "hilos blancos": "hilos_blancos",
    "mancha cafe rojiza": "mancha_cafe_rojiza", "halo amarillo": "halo_amarillo",
    "mancha grasosa": "mancha_grasosa", "raiz negra": "raiz_negra",
    "granos perforados": "granos_perforados", "broca visible": "broca_visible",
    "galerias hoja": "galerias_hoja", "minas hoja": "minas_hoja",
}

class ChatbotCaficultura:
    def __init__(self, perfil="pequeno_productor"):
        self.motor = MotorReglas()
        self.bayes = RedBayesianaCafe()
        self.ag    = OptimizacionGenetica(generaciones=40, tam_poblacion=60)
        self.cnn   = ClasificadorVisionCNN()
        self.clima = ModuloClima(departamento="Matagalpa")
        self.llm   = OraculoAgronomoLLM(perfil=perfil)

        self.ctx = {
            "perfil": perfil, "flujo_pendiente": None, "departamento_zona": "Matagalpa",
            "imagenes_analizadas": [], "superficie_manzanas": 1.0, "superficie_original": {"valor": 1.0, "unidad": "manzana"},
        }
        self.historial_chat = []
        self.sesion_uuid  = str(uuid.uuid4())[:8]
        self.sesion_db_id = crear_sesion(self.sesion_uuid, perfil=perfil)

    def set_perfil(self, perfil): 
        self.ctx["perfil"] = perfil
        self.llm.set_perfil(perfil)
        
    def set_departamento(self, depto):
        if depto in DEPARTAMENTOS:
            self.ctx["departamento_zona"] = depto
            self.clima.set_departamento(depto)
            
    def set_superficie(self, valor, unidad="manzana"):
        factor = SUPERFICIE_FACTORES.get(unidad.lower(), 1.0)
        self.ctx["superficie_manzanas"] = round(valor * factor, 4)
        self.ctx["superficie_original"] = {"valor": valor, "unidad": unidad}

    def registrar_imagen(self, ruta, clase, confianza, nota_cruce=None):
        self.ctx.setdefault("imagenes_analizadas", []).append({
            "ruta": ruta, "clase": clase, "confianza": float(confianza),
            "fecha": time.strftime("%Y-%m-%d %H:%M"), "nota_cruce": nota_cruce,
        })

    def detectar_intent(self, texto):
        t = texto.lower().strip()
        palabras_pregunta = ["que", "qué", "como", "cómo", "por que", "por qué", "cuando", "cuándo", "donde", "dónde", "cual", "cuál", "y si", "me recomiendas"]
        if t.endswith("?") or t.startswith(tuple(palabras_pregunta)):
            return "Consultar_Oraculo_LLM_Fallback"
            
        for intent, patrones in COMANDOS_DIRECTOS.items():
            for p in patrones:
                if re.search(p, t): return intent
        return "Consultar_Oraculo_LLM_Fallback"

    def extraer_entidades(self, texto):
        t = texto.lower()
        ents = {}
        flujo = self.ctx.get("flujo_pendiente")
        stripped = t.strip()

        if flujo in ("temp", "hr", "lluvia") and stripped in NO_SE:
            ents["_auto_clima"] = True
            return ents

        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(manzana|mz|hectarea|hectárea|ha|m2|m²|metro|acre)", t)
        if m:
            valor = float(m.group(1).replace(",", ".")); unidad = m.group(2).lower()
            ents["superficie_manzanas"] = round(valor * SUPERFICIE_FACTORES.get(unidad, 1.0), 4)
            ents["superficie_original"] = {"valor": valor, "unidad": unidad}
        else:
            m = re.search(r"(\d+(?:\.\d+)?)\s*manzana", t)
            if m: ents["superficie_manzanas"] = float(m.group(1)); ents["superficie_original"] = {"valor": float(m.group(1)), "unidad": "manzana"}

        m = re.search(r"(\d+(?:\.\d+)?)\s*[°]?\s*(?:c\b|grados)", t)
        if m: ents["temperatura"] = float(m.group(1))
        elif flujo == "temp":
            m = re.search(r"(\d+(?:\.\d+)?)", t)
            if m: ents["temperatura"] = float(m.group(1))

        m = re.search(r"(\d+)\s*%\s*(?:de\s*)?humedad", t)
        if m: ents["humedad_relativa"] = float(m.group(1))
        elif flujo == "hr":
            m = re.search(r"(\d+)", t)
            if m: ents["humedad_relativa"] = float(m.group(1))

        if any(w in t for w in ("llovio", "llovió", "si llovio", "si, llovio", "sí, llovió")): ents["lluvia_previa"] = True
        elif flujo == "lluvia":
            if stripped in ("si", "sí", "s", "yes", "afirmativo"): ents["lluvia_previa"] = True
            elif stripped in ("no", "n", "negativo"): ents["lluvia_previa"] = False

        for kw, val in _SINTOMAS_MAP.items():
            if kw in t: ents["sintoma_observado"] = val; break

        for kw, val in {"floracion": "floracion", "llenado de grano": "llenado_grano", "maduración": "madurez", "crecimiento": "crecimiento"}.items():
            if kw in t: ents["fase_fenologica"] = val; break

        for alias, canon in _DEPTO_ALIASES.items():
            if alias in t: ents["departamento_zona"] = canon; break

        return ents

    def _autocompletar_clima(self):
        depto = self.ctx.get("departamento_zona", "Matagalpa")
        self.clima.set_departamento(depto)
        datos = self.clima.obtener_datos_actuales()
        self.ctx["temperatura"] = datos["temperatura"]
        self.ctx["humedad_relativa"] = datos["humedad_relativa"]
        self.ctx["lluvia_previa"] = datos["precipitacion_24h"] > 0
        self.ctx["clima_auto"] = datos
        return datos

    def responder(self, texto_usuario):
        t0 = time.time()
        self.historial_chat.append({"role": "user", "content": texto_usuario})
        
        flujo = self.ctx.get("flujo_pendiente")
        if flujo in ("lluvia", "temp", "hr"): 
            intent = "Consultar_Diagnostico_Sintoma"
        else: 
            intent = self.detectar_intent(texto_usuario)

        ents = self.extraer_entidades(texto_usuario)
        if ents.pop("_auto_clima", False):
            try: self._autocompletar_clima()
            except Exception: pass

        self.ctx.update(ents)
        guardar_mensaje(self.sesion_db_id, "usuario", texto_usuario, intent)
        respuesta, intent_final, error = self._despachar(intent, texto_usuario)
        guardar_mensaje(self.sesion_db_id, "asistente", respuesta, intent_final)
        self.historial_chat.append({"role": "assistant", "content": respuesta})

        registrar_turno(
            sesion_uuid=self.sesion_uuid, intent=intent_final, entidades=ents,
            respuesta=respuesta, tiempo_seg=time.time() - t0,
            fallback=(intent_final == "Consultar_Oraculo_LLM_Fallback"), error=error,
        )
        return respuesta, intent_final

    def _despachar(self, intent, texto_usuario):
        try:
            if intent == "Cancelar_Operacion":
                self.ctx["flujo_pendiente"] = None
                return ("Operacion cancelada.", intent, False)
            if intent == "Solicitar_Ayuda":
                return (self._texto_ayuda(), intent, False)
            if intent == "Optimizar_Plan_Fertilizacion_Riego":
                return self._flujo_optimizacion()
            if intent == "Generar_Reporte_PDF":
                return self._flujo_reporte()
            if intent == "Sincronizar_Clima_Entorno":
                depto = self.ctx.get("departamento_zona", "Matagalpa")
                self.clima.set_departamento(depto)
                datos = self.clima.obtener_datos_actuales()
                self.ctx["clima"] = {"temperatura": datos["temperatura"], "humedad_relativa": datos["humedad_relativa"], "lluvia_previa": datos["precipitacion_24h"] > 0, "fuente": datos["fuente"]}
                return (f"Clima en {depto}: {datos['temperatura']} C, HR {datos['humedad_relativa']} %, lluvia 24h: {datos['precipitacion_24h']} mm.", intent, False)
            if intent == "Consultar_Precios_Mercado":
                p = actualizar_precios()
                return (f"Precio del cafe: {p['precio_cafe_oro_qq_usd']} USD/qq. Tipo de cambio: {p['tipo_cambio_usd_nio']} NIO/USD.", intent, False)
            if intent == "Consultar_Diagnostico_Sintoma":
                return self._flujo_diagnostico()

            if self.llm._esta_corriendo():
                contexto = self._contexto_finca_texto()
                respuesta = self.llm.consultar_oraculo(texto_usuario, contexto, self.historial_chat)
                return (respuesta, "Consultar_Oraculo_LLM_Fallback", False)
                
            return ("El Oraculo LLM esta apagado.", "Consultar_Oraculo_LLM_Fallback", False)
        except Exception as e:
            return (f"Error interno: {e}", intent, True)

    def _flujo_diagnostico(self):
        if "lluvia_previa" not in self.ctx:
            self.ctx["flujo_pendiente"] = "lluvia"
            return ("Ha llovido fuerte en su parcela en las ultimas 24 horas? (Si/No/'no se')", "Consultar_Diagnostico_Sintoma", False)
        if "temperatura" not in self.ctx:
            self.ctx["flujo_pendiente"] = "temp"
            return ("Cual es la temperatura aproximada? (o escriba 'no se')", "Consultar_Diagnostico_Sintoma", False)
        if "humedad_relativa" not in self.ctx:
            self.ctx["flujo_pendiente"] = "hr"
            return ("Cual es la humedad relativa aproximada? (o escriba 'no se')", "Consultar_Diagnostico_Sintoma", False)

        self.ctx["flujo_pendiente"] = None
        sintoma_final = self.ctx.get("sintoma_observado", "")
        if not sintoma_final and self.ctx.get("imagenes_analizadas"):
            ultima_img = self.ctx["imagenes_analizadas"][-1]
            mapa = {"Roya": "manchas_naranjas", "Antracnosis": "manchas_negras", "Deficiencia_Nitrogeno": "hojas_amarillas"}
            sintoma_final = mapa.get(ultima_img.get("clase"), "")
            if sintoma_final: self.ctx["sintoma_observado"] = sintoma_final

        hechos = {"sintoma_observado": sintoma_final, "humedad_relativa": self.ctx["humedad_relativa"], "temperatura": self.ctx["temperatura"], "lluvia_previa": self.ctx["lluvia_previa"]}
        diags = self.motor.inferir(hechos)
        self.ctx["diagnosticos"] = diags
        riesgo = self.bayes.evaluar(lluvia=hechos["lluvia_previa"], hr=hechos["humedad_relativa"], temp=hechos["temperatura"], sintoma=hechos["sintoma_observado"])
        self.ctx["riesgo"] = riesgo

        principal = diags[0]
        guardar_diagnostico(self.sesion_db_id, principal.get("regla_id"), principal.get("diagnostico", ""), riesgo)

        # FILTRO POR PERFIL
        if self.ctx["perfil"] == "pequeno_productor":
            respuesta = (
                f"Diagnostico: Su cafe tiene {principal['diagnostico']}.\n"
                f"Que hacer: {principal['recomendacion']}\n"
                f"Nivel de riesgo: {'ALTO' if riesgo['riesgo_global'] > 0.5 else 'BAJO'}"
            )
        else:
            respuesta = (
                f"Diagnostico presuntivo: {principal['diagnostico']} ({principal.get('regla_id', 'N/A')})\n"
                f"Recomendacion: {principal['recomendacion']}\n"
                f"Niveles de riesgo (probabilidades):\n"
                f"  - Roya: {riesgo['roya']*100:.1f}%\n"
                f"  - Antracnosis: {riesgo['antracnosis']*100:.1f}%\n"
                f"  - Ojo de gallo: {riesgo['ojo_gallo']*100:.1f}%\n"
                f"Riesgo global: {riesgo['riesgo_global']*100:.1f}%"
            )
        return (respuesta, "Consultar_Diagnostico_Sintoma", False)

    def _flujo_optimizacion(self):
        sup = self.ctx.get("superficie_manzanas", 1.0)
        res = self.ag.optimizar(superficie_mz=sup, riesgo_roya_pct=self.ctx.get("riesgo", {}).get("roya", 0.65) * 100, verbose=False)
        self.ctx["optimizacion"] = res
        guardar_optimizacion(self.sesion_db_id, res)
        d = res["dosis_por_mz"]
        return (f"Plan para {sup} mz:\nRiego: {d['riego_m3']} m3\nN: {d['N_kg']} kg\nP: {d['P_kg']} kg\nK: {d['K_kg']} kg\nFungicida: {d['fungicida_L']} L\nBeneficio neto: C$ {res['beneficio_neto_nio']:,.2f}", "Optimizar", False)

    def _flujo_reporte(self):
        if not self.ctx.get("clima"):
            try:
                depto = self.ctx.get("departamento_zona", "Matagalpa"); self.clima.set_departamento(depto); d = self.clima.obtener_datos_actuales()
                self.ctx["clima"] = {"temperatura": d["temperatura"], "humedad_relativa": d["humedad_relativa"], "lluvia_previa": d["precipitacion_24h"] > 0, "fuente": d["fuente"]}
            except Exception: pass

        datos = {"sesion_id": self.sesion_uuid, "zona": self.ctx.get("departamento_zona", "Matagalpa"), "superficie_manzanas": self.ctx.get("superficie_manzanas", 1.0), "clima": self.ctx.get("clima", {}), "diagnosticos": self.ctx.get("diagnosticos", []), "riesgo": self.ctx.get("riesgo", {}), "optimizacion": self.ctx.get("optimizacion", {}), "imagenes": self.ctx.get("imagenes_analizadas", [])}
        ruta = generar_reporte(datos, nombre=f"reporte_{self.sesion_uuid}.pdf")
        ruta_desc = exportar_a_descargas(ruta)
        return (f"Reporte PDF generado: {ruta}\nCopia en Descargas: {ruta_desc}", "Generar_Reporte_PDF", False)

    def _texto_ayuda(self):
        return ("Soy tu Asistente Agrónomo Experto. Puedes preguntarme cualquier cosa (ej. '¿Cómo preparo caldo bordelés?'), pedirme que analice una foto, o pedirme un reporte.")

    def _contexto_finca_texto(self):
        partes = []
        if self.ctx.get("departamento_zona"): partes.append(f"Ubicación: {self.ctx['departamento_zona']}")
        if self.ctx.get("superficie_manzanas"): partes.append(f"Superficie: {self.ctx['superficie_manzanas']} mz")
        if self.ctx.get("imagenes_analizadas"):
            clases = [img["clase"] for img in self.ctx["imagenes_analizadas"]]
            partes.append(f"Enfermedades vistas en fotos: {', '.join(clases)}")
        if self.ctx.get("diagnosticos"):
            partes.append(f"Diagnóstico previo: {self.ctx['diagnosticos'][0]['diagnostico']}")
        return " | ".join(partes) if partes else "Sin datos previos."