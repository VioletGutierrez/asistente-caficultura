# ============================================================
# app_streamlit.py
# Interfaz web - Asistente Inteligente para la Caficultura
# Ejecutar: streamlit run app_streamlit.py
# ============================================================
import os
import re
import tempfile
import streamlit as st
import pandas as pd
from datetime import datetime

from modulos.chatbot        import ChatbotCaficultura, DEPARTAMENTOS
from modulos.vision_cnn     import ClasificadorVisionCNN
from modulos.precios        import leer_precios_actuales, actualizar_precios
from modulos.llm_fallback   import OraculoAgronomoLLM
from modulos.reporte_pdf    import generar_reporte, exportar_a_descargas
from modulos.kpis           import (
    calcular_kpis, calcular_csat, registrar_turno,
)
from modulos.db             import (
    consultar_historial, obtener_stats,
)
from modulos.sugerencias    import (
    sugerencias_iniciales, sugerencias_para_contexto,
)


st.set_page_config(
    page_title="Asistente Caficultura S3",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# Estado de sesion
# ============================================================
if "bot" not in st.session_state:
    st.session_state.bot = ChatbotCaficultura()
    st.session_state.chat_historial = []
    st.session_state.cnn = ClasificadorVisionCNN()
    st.session_state.llm = OraculoAgronomoLLM()
    st.session_state.csat_enviado = False
    st.session_state.last_upload = None
    st.session_state.reporte_bytes = None
    st.session_state.reporte_nombre = None
    st.session_state.sugerencias_ultimas = set()


# ============================================================
# Helper: cargar PDF en session_state si la respuesta lo menciona
# ============================================================
def _cargar_reporte_en_sesion(respuesta):
    m = re.search(r'([\w/\\:.\-]+\.pdf)', respuesta)
    if not m:
        return
    ruta = m.group(1).strip().rstrip(".").rstrip(",")
    if os.path.exists(ruta):
        try:
            with open(ruta, "rb") as f:
                st.session_state.reporte_bytes = f.read()
            st.session_state.reporte_nombre = os.path.basename(ruta)
        except Exception:
            pass


# ============================================================
# BARRA LATERAL
# ============================================================
with st.sidebar:
    st.title("Asistente Caficultura S3")
    st.caption("Plataforma Integrada de Inteligencia Agricola")

    st.divider()
    st.subheader("Perfil de usuario")
    perfil_label = st.radio(
        "Seleccione su perfil:",
        [
            "Pequeno facilitador tradicional",
            "Extensionista tecnica de campo",
            "Administrador de finca o cooperativa",
        ],
        index=0,
    )

    if "Pequeno" in perfil_label:
        perfil_key = "pequeno_productor"
        nivel_detalle = "simple"
    elif "Extensionista" in perfil_label:
        perfil_key = "extensionista_tecnico"
        nivel_detalle = "tecnico"
    else:
        perfil_key = "administrador_finca"
        nivel_detalle = "gerencial"

    st.session_state.bot.set_perfil(perfil_key)
    st.caption(f"Nivel de detalle: {nivel_detalle}")

    # --- Departamento ---
    st.divider()
    st.subheader("Ubicacion de la finca")
    depto_actual = st.session_state.bot.ctx.get("departamento_zona", "Matagalpa")
    idx_default = (DEPARTAMENTOS.index(depto_actual)
                   if depto_actual in DEPARTAMENTOS else 11)
    depto = st.selectbox(
        "Departamento / Region",
        DEPARTAMENTOS, index=idx_default,
        help="Seleccione el departamento donde se ubica su parcela",
    )
    st.session_state.bot.set_departamento(depto)
    st.caption(f"Zona activa: **{depto}**")

    # --- Superficie con unidades ---
    st.divider()
    st.subheader("Superficie de la finca")
    sup_orig = st.session_state.bot.ctx.get(
        "superficie_original", {"valor": 1.0, "unidad": "manzana"}
    )
    unidades = ["manzana", "ha", "m²", "acre"]
    uni_actual = sup_orig.get("unidad", "manzana")
    idx_uni = unidades.index(uni_actual) if uni_actual in unidades else 0

    col_sup1, col_sup2 = st.columns([2, 1])
    with col_sup1:
        sup_val = st.number_input(
            "Valor",
            min_value=0.01, max_value=10000.0,
            value=float(sup_orig.get("valor", 1.0)),
            step=0.5,
            key="sup_input",
        )
    with col_sup2:
        sup_uni = st.selectbox(
            "Unidad", unidades, index=idx_uni, key="sup_unidad",
        )
    st.session_state.bot.set_superficie(sup_val, sup_uni)
    st.caption(
        f"= **{st.session_state.bot.ctx['superficie_manzanas']:.4f} manzanas**"
    )

    # --- Estado ---
    st.divider()
    st.subheader("Estado de modulos")
    st.write("Chatbot: activo")
    st.write("Oraculo LLM:",
             "activo" if st.session_state.llm._esta_corriendo() else "offline")
    st.write("Vision CNN: activa")
    st.write("Precios: en vivo")

    st.divider()
    if st.button("Reiniciar conversacion", use_container_width=True):
        st.session_state.bot = ChatbotCaficultura()
        st.session_state.bot.set_departamento(depto)
        st.session_state.bot.set_superficie(sup_val, sup_uni)
        st.session_state.chat_historial = []
        st.session_state.csat_enviado = False
        st.session_state.last_upload = None
        st.session_state.reporte_bytes = None
        st.session_state.reporte_nombre = None
        st.session_state.sugerencias_ultimas = set()
        st.rerun()


# ============================================================
# Pestanas
# ============================================================
tab_chat, tab_img, tab_precios, tab_oraculo, tab_historial, tab_admin = st.tabs([
    "Chat", "Analizar Hoja", "Precios", "Oraculo", "Historial", "Admin",
])


# ============================================================
# TAB 1 - CHAT
# ============================================================
with tab_chat:
    st.title("Conversacion con el Asistente")
    st.caption(
        f"Departamento activo: **{depto}** | "
        f"Superficie: **{st.session_state.bot.ctx['superficie_manzanas']:.2f} mz**. "
        "Puede describir sintomas, subir una foto o generar un reporte."
    )

    # --- Historial ---
    for rol, texto, intent in st.session_state.chat_historial:
        with st.chat_message("user" if rol == "usuario" else "assistant"):
            st.markdown(texto)
            if rol == "asistente" and nivel_detalle == "tecnico" and intent:
                st.caption(f"Intent detectado: {intent}")

    # --- Boton de descarga del reporte (persistente) ---
    if st.session_state.reporte_bytes:
        st.success(f"Reporte listo: **{st.session_state.reporte_nombre}**")
        st.download_button(
            label=f"Descargar {st.session_state.reporte_nombre}",
            data=st.session_state.reporte_bytes,
            file_name=st.session_state.reporte_nombre,
            mime="application/pdf",
            key=f"dl_{st.session_state.reporte_nombre}_"
                f"{len(st.session_state.chat_historial)}",
        )
        st.caption(
            "Tambien esta guardado en `salidas/` (respaldo) y en la carpeta "
            "Descargas del equipo."
        )

    # --- Uploader de imagen dentro del chat ---
    st.divider()
    st.markdown("**Subir una foto de hoja para analizarla ahora**")
    archivo_chat = st.file_uploader(
        "Seleccione una imagen (JPG/PNG)",
        type=["jpg", "jpeg", "png"],
        key="chat_uploader",
    )
    if (archivo_chat is not None
            and archivo_chat.name != st.session_state.last_upload):
        st.session_state.last_upload = archivo_chat.name
        os.makedirs("salidas", exist_ok=True)
        nombre_img = (f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}_"
                      f"{archivo_chat.name}")
        ruta_img = os.path.join("salidas", nombre_img)
        with open(ruta_img, "wb") as f:
            f.write(archivo_chat.getbuffer())

        with st.spinner("Clasificando imagen..."):
            resultado = st.session_state.cnn.clasificar_imagen(
                ruta_img,
                sintoma_textual=st.session_state.bot.ctx.get("sintoma_observado"),
            )

        st.session_state.bot.registrar_imagen(
            ruta_img,
            resultado["clase"],
            resultado["confianza"],
            nota_cruce=resultado.get("nota_cruce"),
        )

        # Mensaje en el chat
        nota = ""
        if resultado.get("nota_cruce"):
            nota = f"\n  >> {resultado['nota_cruce']}"
        st.session_state.chat_historial.append((
            "usuario",
            f"[Imagen adjunta: {archivo_chat.name}]",
            None,
        ))
        st.session_state.chat_historial.append((
            "asistente",
            f"Analisis de imagen:\n"
            f"  - Clase detectada: {resultado['clase']}\n"
            f"  - Confianza: {resultado['confianza']*100:.1f}%\n"
            f"  - Modo: {resultado.get('modo', 'N/A')}\n"
            f"La imagen se incluíra en el reporte PDF."
            f"{nota}",
            "Analizar_Imagen_Hoja",
        ))
        st.rerun()

    # --- Entrada de texto ---
    prompt = st.chat_input("Escriba su consulta...")
    if prompt:
        st.session_state.chat_historial.append(("usuario", prompt, None))
        with st.spinner("Procesando..."):
            respuesta, intent = st.session_state.bot.responder(prompt)
        st.session_state.chat_historial.append(("asistente", respuesta, intent))
        if intent == "Generar_Reporte_PDF":
            _cargar_reporte_en_sesion(respuesta)
        st.rerun()

    # --- Sugerencias rapidas DINAMICAS ---
    st.divider()
    st.markdown("**Sugerencias rapidas**")
    ultimas = st.session_state.get("sugerencias_ultimas", set())
    if st.session_state.chat_historial:
        pool = sugerencias_para_contexto(
            st.session_state.bot.ctx, n=6, excluir_ultimas=ultimas,
        )
    else:
        pool = sugerencias_iniciales(nivel_detalle, n=6)

    sugerencias = pool[:4]
    st.session_state["sugerencias_ultimas"] = ultimas.union(set(sugerencias))

    cols = st.columns(len(sugerencias))
    for i, sug in enumerate(sugerencias):
        with cols[i]:
            label = sug if len(sug) <= 30 else sug[:28] + "…"
            if st.button(
                label, use_container_width=True,
                key=f"sug_{i}_{len(st.session_state.chat_historial)}",
            ):
                r, intent = st.session_state.bot.responder(sug)
                st.session_state.chat_historial.append(("usuario", sug, None))
                st.session_state.chat_historial.append(
                    ("asistente", r, intent))
                if intent == "Generar_Reporte_PDF":
                    _cargar_reporte_en_sesion(r)
                st.rerun()

    # --- CSAT ---
    st.divider()
    st.subheader("Encuesta de satisfaccion (CSAT)")
    if not st.session_state.csat_enviado:
        csat_val = st.slider(
            "Califique la utilidad del asistente (1=pobre, 5=excelente)",
            min_value=1, max_value=5, value=5, key="csat_slider",
        )
        if st.button("Enviar calificacion"):
            registrar_turno(
                sesion_uuid=st.session_state.bot.sesion_uuid,
                intent="CSAT_Feedback",
                entidades={"csat": int(csat_val)},
                respuesta=f"Calificacion: {csat_val}",
                tiempo_seg=0.0,
            )
            st.session_state.csat_enviado = True
            st.success(f"Gracias por su calificacion: {csat_val}/5")
            st.rerun()
    else:
        st.info("Ya registro su calificacion en esta sesion. Gracias!")


# ============================================================
# TAB 2 - ANALISIS DE IMAGEN
# ============================================================
with tab_img:
    st.title("Analisis de Hoja de Cafe")
    st.caption("Suba una fotografia clara de una hoja para detectar enfermedades.")
    archivo = st.file_uploader(
        "Seleccione una imagen (JPG o PNG)",
        type=["jpg", "jpeg", "png"],
        key="tab_img_uploader",
    )
    if archivo is not None:
        col1, col2 = st.columns([1, 1])
        with col1:
            st.image(archivo, caption="Imagen cargada",
                     use_container_width=True)
        with col2:
            os.makedirs("salidas", exist_ok=True)
            nombre_img = (f"tab_{datetime.now().strftime('%Y%m%d_%H%M%S')}_"
                          f"{archivo.name}")
            ruta = os.path.join("salidas", nombre_img)
            with open(ruta, "wb") as f:
                f.write(archivo.getbuffer())
            try:
                with st.spinner("Clasificando..."):
                    resultado = st.session_state.cnn.clasificar_imagen(
                        ruta,
                        sintoma_textual=st.session_state.bot.ctx.get(
                            "sintoma_observado"),
                    )
                st.success("Analisis completado")
                st.metric("Enfermedad detectada",
                          resultado.get("clase", "?").capitalize())
                st.metric("Confianza",
                          f"{resultado.get('confianza', 0)*100:.1f}%")
                if resultado.get("requiere_retomar_foto"):
                    st.warning(
                        "Confianza baja. Tome una nueva foto con mejor "
                        "iluminacion o enfoque la zona afectada."
                    )
                if resultado.get("nota_cruce"):
                    st.info(f"Cruce con sintoma: {resultado['nota_cruce']}")
                st.session_state.bot.registrar_imagen(
                    ruta, resultado["clase"], resultado["confianza"],
                    nota_cruce=resultado.get("nota_cruce"),
                )
                st.caption(
                    "Imagen registrada. Aparecera en el proximo reporte PDF."
                )
                if nivel_detalle in ("tecnico", "gerencial"):
                    st.json(resultado)
            except Exception as e:
                st.error(f"Error al clasificar: {e}")


# ============================================================
# TAB 3 - PRECIOS
# ============================================================
with tab_precios:
    st.title("Indicadores de Mercado")
    p = leer_precios_actuales()
    col1, col2, col3 = st.columns(3)
    col1.metric("Precio del cafe", f"${p['precio_cafe_oro_qq_usd']:.2f}/qq")
    col2.metric("Tipo de cambio", f"C$ {p['tipo_cambio_usd_nio']:.2f}")
    col3.metric("Mano de obra",
                f"C$ {p['costo_mano_obra_dia_nio']:.0f}/dia")
    if st.button("Actualizar precios desde internet"):
        with st.spinner("Consultando APIs externas..."):
            nuevos = actualizar_precios()
        st.success(f"Actualizado: cafe ${nuevos['precio_cafe_oro_qq_usd']}/qq")
        st.rerun()
    st.caption(f"Ultima actualizacion: {p.get('ultima_actualizacion', 'N/A')}")


# ============================================================
# TAB 4 - ORACULO LLM
# ============================================================
with tab_oraculo:
    st.title("Oraculo Agronomico")
    if not st.session_state.llm._esta_corriendo():
        st.warning("Ollama no esta corriendo. Ejecute 'ollama serve'.")
    else:
        pregunta = st.text_area(
            "Escriba su consulta abierta:", height=100,
            placeholder="Ejemplo: Que factores influyen en la floracion del cafe?",
        )
        if st.button("Consultar al Oraculo") and pregunta.strip():
            with st.spinner("Consultando..."):
                respuesta = st.session_state.llm.consultar_oraculo(
                    pregunta,
                    contexto_finca=st.session_state.bot._contexto_finca_texto(),
                )
            st.markdown("### Respuesta")
            st.write(respuesta)


# ============================================================
# TAB 5 - HISTORIAL
# ============================================================
with tab_historial:
    st.title("Historial de Sesiones")
    hist = consultar_historial(limite=30)
    if hist:
        df = pd.DataFrame(hist)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Aun no hay sesiones registradas.")


# ============================================================
# TAB 6 - ADMIN
# ============================================================
with tab_admin:
    st.title("Panel del Administrador")
    if nivel_detalle != "gerencial":
        st.info("Este panel es mas util para el perfil Administrador de finca.")
    stats = obtener_stats()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total sesiones", stats["total_sesiones"])
    col2.metric("Total mensajes", stats["total_mensajes"])
    col3.metric("Fallbacks LLM",  stats["total_fallbacks"])
    col4.metric("Tasa de fallback", f"{stats['tasa_fallback']*100:.1f}%")

    st.divider()
    st.subheader("KPIs conversacionales")
    kpis = calcular_kpis()
    if "error" not in kpis:
        for k, v in kpis.items():
            st.text(f"{k}: {v}")

    st.divider()
    st.subheader("Satisfaccion del usuario (CSAT)")
    csat_avg = calcular_csat()
    if csat_avg is None:
        st.info("Aun no hay calificaciones CSAT registradas.")
    else:
        col_cs1, col_cs2 = st.columns(2)
        col_cs1.metric("CSAT promedio", f"{csat_avg}/5")
        col_cs2.metric("Meta", ">= 4.0",
                       delta=("Cumple" if csat_avg >= 4.0 else "Por debajo"))

    st.divider()
    st.subheader("Generar reporte consolidado")
    if st.button("Generar Reporte del Sistema"):
        bot = st.session_state.bot
        datos = {
            "sesion_id":           bot.sesion_uuid,
            "zona":                bot.ctx.get("departamento_zona", "Matagalpa"),
            "superficie_manzanas": bot.ctx.get("superficie_manzanas", 1.0),
            "superficie_original": bot.ctx.get("superficie_original"),
            "clima":               bot.ctx.get("clima", {}),
            "diagnosticos":        bot.ctx.get("diagnosticos", []),
            "riesgo":              bot.ctx.get("riesgo", {}),
            "optimizacion":        bot.ctx.get("optimizacion", {}),
            "imagenes":            bot.ctx.get("imagenes_analizadas", []),
        }
        ruta = generar_reporte(datos, nombre=f"admin_{bot.sesion_uuid}.pdf")
        ruta_desc = exportar_a_descargas(ruta)
        if ruta_desc:
            st.success(f"Copia en Descargas: {ruta_desc}")
        with open(ruta, "rb") as f:
            st.download_button(
                label="Descargar PDF",
                data=f.read(),
                file_name=os.path.basename(ruta),
                mime="application/pdf",
            )


# ============================================================
# Pie
# ============================================================
st.divider()
st.caption(
    f"Plataforma S3 | Sesion: {st.session_state.bot.sesion_uuid} | "
    f"Perfil: {perfil_key} | Depto: {depto} | "
    f"Superficie: {st.session_state.bot.ctx['superficie_manzanas']:.2f} mz | "
    f"Hora: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
)