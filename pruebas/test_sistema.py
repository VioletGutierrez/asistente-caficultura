# ============================================================
# pruebas/test_sistema.py
# Pruebas unitarias y de integracion
# Referencia: IA_Entregable1.pdf Seccion 10.3
# Ejecutar: pytest pruebas/ -v
# ============================================================
import os
import numpy as np
import cv2
import pytest

from modulos.motor_reglas       import MotorReglas
from modulos.red_bayesiana      import RedBayesianaCafe
from modulos.algoritmo_genetico import OptimizacionGenetica
from modulos.clima_api          import ModuloClima
from modulos.vision_cnn         import ClasificadorVisionCNN
from modulos.precios            import leer_precios_actuales
from modulos.reporte_pdf        import generar_reporte
from modulos.db                 import (
    crear_sesion, guardar_mensaje, obtener_stats,
)
from modulos.kpis               import (
    registrar_turno, calcular_kpis, calcular_csat,
)
from modulos.chatbot            import ChatbotCaficultura


# ------------------------------------------------------------
# Pruebas unitarias
# ------------------------------------------------------------
def test_motor_reglas_roya():
    m = MotorReglas()
    hechos = {
        "sintoma_observado": "manchas_naranjas",
        "humedad_relativa":  80,
        "temperatura":       22,
        "lluvia_previa":     True,
    }
    resultado = m.inferir(hechos)
    assert resultado[0]["regla_id"] == "R001"
    assert "Roya" in resultado[0]["diagnostico"]


def test_motor_reglas_bloqueo_seguridad():
    """CP-03 del documento: bloqueo por anoxia y sobre-fertilizacion."""
    m = MotorReglas()
    hechos = {"dosis_nitrogeno": 180, "volumen_riego": 400}
    resultado = m.inferir(hechos)
    assert any(r["regla_id"] == "R_SEG_005" for r in resultado)


def test_motor_reglas_deficit_nitrogeno():
    """CP-01 del documento: deficit de nitrogeno en llenado de grano."""
    m = MotorReglas()
    hechos = {
        "fase_fenologica":  "llenado_grano",
        "nitrogeno_foliar": 1.8,
        "humedad_suelo":    70,
    }
    resultado = m.inferir(hechos)
    assert any(r["regla_id"] == "R_NUT_001" for r in resultado)


def test_motor_reglas_brote_roya():
    """CP-02 del documento: brote activo de roya con incidencia alta."""
    m = MotorReglas()
    hechos = {
        "presencia_pustula_roya": True,
        "incidencia_visual":      15,
    }
    resultado = m.inferir(hechos)
    assert any(r["regla_id"] == "R_FIT_002" for r in resultado)


def test_motor_reglas_operador_or():
    """R_OR_001 usa operador_logico=OR (fase 6)."""
    m = MotorReglas()
    # Solo coincide con R_OR_001 (falta humedad para R002, etc.)
    hechos = {"sintoma_observado": "manchas_negras"}
    ids = [r["regla_id"] for r in m.inferir(hechos)]
    assert "R_OR_001" in ids

    # Sintoma no contemplado: R_OR_001 no debe dispararse
    hechos2 = {"sintoma_observado": "hojas_amarillas"}
    ids2 = [r["regla_id"] for r in m.inferir(hechos2)]
    assert "R_OR_001" not in ids2


def test_motor_reglas_rango_temperatura():
    """R001 acepta rango '18-24' como condicion."""
    m = MotorReglas()
    hechos = {
        "sintoma_observado": "manchas_naranjas",
        "humedad_relativa":  80,
        "temperatura":       22,   # dentro de 18-24
        "lluvia_previa":     True,
    }
    assert m.inferir(hechos)[0]["regla_id"] == "R001"

    hechos["temperatura"] = 30      # fuera de rango
    ids = [r["regla_id"] for r in m.inferir(hechos)]
    assert "R001" not in ids


def test_red_bayesiana_escenario_seco():
    red = RedBayesianaCafe()
    r = red.evaluar(lluvia=False, hr=65, temp=29.5, precipitacion_24h=15)
    assert 0 <= r["roya"] <= 1
    assert r["detalle_roya"]["bajo"] > 0.5


def test_red_bayesiana_escenario_extremo():
    red = RedBayesianaCafe()
    r = red.evaluar(lluvia=True, hr=94, temp=22, precipitacion_24h=145)
    assert 0 <= r["riesgo_global"] <= 1
    assert r["detalle_roya"]["alto"] > 0.3


def test_red_bayesiana_nodo_ojo_gallo():
    """Verifica que el nuevo nodo R_Ojo este presente."""
    red = RedBayesianaCafe()
    r = red.evaluar(lluvia=True, hr=94, temp=22, precipitacion_24h=145)
    assert "detalle_ojo" in r
    assert "alto" in r["detalle_ojo"]
    assert 0 <= r["detalle_ojo"]["alto"] <= 1


def test_algoritmo_genetico_produce_plan_valido():
    ag = OptimizacionGenetica(generaciones=20, tam_poblacion=30)
    r = ag.optimizar(superficie_mz=1.0, riesgo_roya_pct=60)
    assert r["rendimiento_qq_mz"] > 0
    assert r["costo_total_nio"] > 0
    assert set(r["dosis_por_mz"]).issuperset(
        {"riego_m3", "N_kg", "P_kg", "K_kg", "fungicida_L"}
    )
    assert r["dosis_por_mz"]["riego_m3"] <= 400
    assert r["dosis_por_mz"]["N_kg"] <= 150


def test_clima_fallback():
    clima = ModuloClima()
    datos = clima._fallback()
    # Tolerar el sufijo del departamento: "Fallback Local (Depto)"
    assert "Fallback" in datos["fuente"]
    assert datos["temperatura"] > 0
    assert 0 <= datos["humedad_relativa"] <= 100


def test_vision_clasifica_estructura():
    cnn = ClasificadorVisionCNN()
    ruta = "salidas/_test_hoja.jpg"
    img = np.full((224, 224, 3), (40, 120, 40), dtype=np.uint8)
    cv2.imwrite(ruta, img)
    try:
        r = cnn.clasificar_imagen(ruta)
        assert "clase" in r
        assert "confianza" in r
        assert 0 <= r["confianza"] <= 1
    finally:
        if os.path.exists(ruta):
            os.remove(ruta)


def test_db_persistencia():
    sid = crear_sesion("test-uuid-fase5", perfil="test")
    assert sid > 0
    guardar_mensaje(sid, "usuario", "mensaje de prueba")
    stats = obtener_stats()
    assert stats["total_sesiones"] >= 1


def test_kpis_calculo():
    registrar_turno(
        sesion_uuid="test-kpi",
        intent="Test",
        entidades={"x": 1},
        respuesta="ok",
        tiempo_seg=0.5,
    )
    kpis = calcular_kpis()
    assert "total_turnos" in kpis
    assert kpis["total_turnos"] >= 1


def test_precios_json_valido():
    p = leer_precios_actuales()
    assert "precio_cafe_oro_qq_usd" in p
    assert "tipo_cambio_usd_nio" in p
    assert 50 <= p["precio_cafe_oro_qq_usd"] <= 500


# ------------------------------------------------------------
# Pruebas de integracion
# ------------------------------------------------------------
def test_chatbot_flujo_diagnostico_completo():
    bot = ChatbotCaficultura()
    r1, _ = bot.responder("Tengo manchas naranjas en hojas")
    assert "lluvia" in r1.lower() or "llovido" in r1.lower()

    r2, _ = bot.responder("si")
    assert "temperatura" in r2.lower()

    r3, _ = bot.responder("22")
    assert "humedad" in r3.lower()

    r4, _ = bot.responder("80")
    assert "diagnostico" in r4.lower() or "roya" in r4.lower()
    assert "riesgo" in r4.lower()


def test_chatbot_intent_confirmar_accion():
    """Verifica que el intent Confirmar_Accion este implementado."""
    bot = ChatbotCaficultura()
    r, intent = bot.responder("confirmo")
    assert intent == "Confirmar_Accion"
    assert "confirmada" in r.lower()


def test_chatbot_entidad_fase_fenologica():
    """Verifica extraccion de la entidad @fase_fenologica."""
    bot = ChatbotCaficultura()
    ents = bot.extraer_entidades("Estamos en llenado de grano")
    assert ents.get("fase_fenologica") == "llenado_grano"


def test_chatbot_entidad_tipo_insumo():
    """Verifica extraccion de la entidad @tipo_insumo."""
    bot = ChatbotCaficultura()
    ents = bot.extraer_entidades("Necesito aplicar fertilizante urea")
    assert ents.get("tipo_insumo") == "fertilizante"


def test_chatbot_flujo_optimizacion():
    bot = ChatbotCaficultura()
    r, intent = bot.responder("Optimizar fertilizacion para 2 manzanas")
    assert intent == "Optimizar_Plan_Fertilizacion_Riego"
    assert "Costo total" in r


def test_chatbot_flujo_reporte():
    bot = ChatbotCaficultura()
    bot.responder("Optimizar fertilizacion para 1 manzana")
    r, intent = bot.responder("Generar reporte PDF")
    assert intent == "Generar_Reporte_PDF"
    assert "generado" in r.lower()


def test_reporte_pdf_se_crea():
    datos = {
        "sesion_id":           "TEST-PDF",
        "zona":                "Matagalpa",
        "superficie_manzanas": 1.0,
        "clima":               {"temperatura": 22, "humedad_relativa": 80,
                                "lluvia_previa": True, "fuente": "test"},
        "diagnosticos":        [{"regla_id": "R001", "diagnostico": "Roya",
                                  "recomendacion": "Fungicida cuprico"}],
        "riesgo":              {"roya": 0.72, "antracnosis": 0.15,
                                "ojo_gallo": 0.13, "riesgo_global": 0.72},
        "optimizacion":        {
            "dosis_por_mz": {"riego_m3": 145, "N_kg": 92, "P_kg": 40,
                             "K_kg": 60, "fungicida_L": 1.8},
            "rendimiento_qq_mz": 24.5,
            "costo_total_nio": 12500,
            "beneficio_neto_nio": 48000,
            "precio_cafe_nio_qq": 8056.4,
        },
    }
    ruta = generar_reporte(datos, nombre="reporte_test_suite.pdf")
    try:
        assert os.path.exists(ruta)
        assert os.path.getsize(ruta) > 1000
    finally:
        if os.path.exists(ruta):
            os.remove(ruta)


# ------------------------------------------------------------
# Pruebas de la fase 6 (CSAT, OR, sensibilidad, endpoints)
# ------------------------------------------------------------
def test_csat_registro_y_calculo():
    """CSAT se registra y se promedia correctamente."""
    registrar_turno(
        sesion_uuid="test-csat",
        intent="CSAT_Feedback",
        entidades={"csat": 4},
        respuesta="Calificacion: 4",
        tiempo_seg=0.0,
    )
    registrar_turno(
        sesion_uuid="test-csat",
        intent="CSAT_Feedback",
        entidades={"csat": 5},
        respuesta="Calificacion: 5",
        tiempo_seg=0.0,
    )
    csat = calcular_csat()
    assert csat is not None
    assert 1 <= csat <= 5


def test_analisis_sensibilidad_devuelve_3_escenarios():
    """La funcion ejecutar_analisis devuelve los escenarios A, B, C."""
    from analisis_sensibilidad import ejecutar_analisis
    res = ejecutar_analisis()
    assert "escenarios" in res
    assert len(res["escenarios"]) == 3
    ids = {e["id"] for e in res["escenarios"]}
    assert ids == {"A", "B", "C"}
    for e in res["escenarios"]:
        assert 0.0 <= e["resultado"]["riesgo_global"] <= 1.0


def test_api_endpoints_existen():
    """Verifica que los endpoints clave esten montados en FastAPI."""
    from api.servidor import app
    paths = {r.path for r in app.routes}
    for ruta in (
        "/salud", "/health", "/chat", "/clima", "/precios",
        "/precios/actualizar", "/optimizar", "/imagen", "/oraculo",
        "/reporte", "/analisis/sensibilidad", "/kpis",
    ):
        assert ruta in paths, f"Falta endpoint {ruta}"


# ------------------------------------------------------------
# Pruebas fase 7 - Departamentos + enfermedades ampliadas
# ------------------------------------------------------------
def test_departamentos_17_unidades():
    """Verifica que esten las 15 + 2 RACCN/RACCS."""
    from modulos.chatbot import DEPARTAMENTOS
    assert len(DEPARTAMENTOS) == 17
    for d in ("Matagalpa", "Jinotega", "RACCN", "RACCS", "Nueva Segovia"):
        assert d in DEPARTAMENTOS


def test_set_departamento_chatbot():
    """El chatbot debe aceptar set_departamento()."""
    from modulos.chatbot import ChatbotCaficultura
    bot = ChatbotCaficultura()
    bot.set_departamento("Jinotega")
    assert bot.ctx["departamento_zona"] == "Jinotega"
    bot.set_departamento("Invalido")
    assert bot.ctx["departamento_zona"] == "Jinotega"  # sin cambio


def test_reglas_enfermedades_nuevas():
    """Verifica que las 12 reglas nuevas existan en el JSON."""
    from modulos.motor_reglas import MotorReglas
    m = MotorReglas()
    ids = {r["id"] for r in m.reglas}
    nuevas = {
        "R_FIT_003", "R_FIT_004", "R_FIT_005", "R_FIT_006",
        "R_PLA_001", "R_PLA_002", "R_PLA_003",
        "R_NUT_002", "R_NUT_003", "R_NUT_004",
        "R_NUT_005", "R_NUT_006",
    }
    faltantes = nuevas - ids
    assert not faltantes, f"Faltan reglas: {faltantes}"


def test_diagnostico_broca_del_cafe():
    """Verifica que un sintoma de broca dispare R_PLA_001."""
    from modulos.motor_reglas import MotorReglas
    m = MotorReglas()
    hechos = {"sintoma_observado": "granos_perforados"}
    ids = [r["regla_id"] for r in m.inferir(hechos)]
    assert "R_PLA_001" in ids


def test_extraer_departamento_desde_texto():
    """Un texto libre con depto debe extraer la entidad."""
    from modulos.chatbot import ChatbotCaficultura
    bot = ChatbotCaficultura()
    ents = bot.extraer_entidades("Estoy en Jinotega con mi parcela")
    assert ents.get("departamento_zona") == "Jinotega"


# ------------------------------------------------------------
# Pruebas fase 8 - Auto-clima
# ------------------------------------------------------------
def test_clima_por_departamento():
    """ModuloClima debe aceptar set_departamento() de los 17."""
    from modulos.clima_api import ModuloClima, DEPTO_COORDS
    assert len(DEPTO_COORDS) == 17
    c = ModuloClima(departamento="Jinotega")
    assert c.departamento == "Jinotega"
    assert c.lat != 0 and c.lon != 0
    c.set_departamento("RACCN")
    assert c.departamento == "RACCN"


def test_auto_clima_con_no_se():
    """Si el usuario dice 'no se', el bot obtiene el clima automatico."""
    from modulos.chatbot import ChatbotCaficultura
    bot = ChatbotCaficultura()
    bot.set_departamento("Matagalpa")
    bot.responder("Tengo manchas naranjas en las hojas")
    bot.responder("si")   # lluvia
    # Ahora pide temperatura; responde "no se" -> auto
    r, _ = bot.responder("no se")
    # Temperatura y humedad deben estar cargadas en ctx
    assert bot.ctx.get("temperatura") is not None
    # La respuesta debe seguir pidiendo humedad (o ya avanzar a diagnostico)
    assert "humedad" in r.lower() or "diagnostico" in r.lower() or "riesgo" in r.lower()