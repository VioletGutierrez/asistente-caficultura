# ============================================================
# app_streamlit.py
# Interfaz web - Asistente Inteligente para la Caficultura
# ============================================================
import os
import re
import streamlit as st
import pandas as pd
from datetime import datetime

from modulos.chatbot        import ChatbotCaficultura, DEPARTAMENTOS
from modulos.vision_cnn     import ClasificadorVisionCNN
from modulos.precios        import leer_precios_actuales, actualizar_precios
from modulos.llm_fallback   import OraculoAgronomoLLM
from modulos.reporte_pdf    import generar_reporte, exportar_a_descargas
from modulos.kpis           import calcular_kpis, calcular_csat, registrar_turno
from modulos.db             import consultar_historial, obtener_stats
from modulos.sugerencias    import sugerencias_iniciales, sugerencias_para_contexto
from modulos.clima_api      import ModuloClima

st.set_page_config(page_title="Asistente Caficultura S3 - UNA", layout="wide", initial_sidebar_state="expanded")

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
    st.session_state.clima_api = ModuloClima()
    st.session_state.last_perfil = None
    st.session_state.last_depto = None

def _cargar_reporte_en_sesion(respuesta):
    m = re.search(r'([\w/\\:.\-]+\.pdf)', respuesta)
    if not m: return
    ruta = m.group(1).strip().rstrip(".").rstrip(",")
    if os.path.exists(ruta):
        try:
            with open(ruta, "rb") as f: st.session_state.reporte_bytes = f.read()
            st.session_state.reporte_nombre = os.path.basename(ruta)
        except Exception: pass

def _reiniciar_sesion(perfil_key, depto, sup_val, sup_uni):
    st.session_state.bot = ChatbotCaficultura()
    st.session_state.bot.set_perfil(perfil_key)
    st.session_state.bot.set_departamento(depto)
    st.session_state.bot.set_superficie(sup_val, sup_uni)
    st.session_state.chat_historial = []
    st.session_state.csat_enviado = False
    st.session_state.last_upload = None
    st.session_state.reporte_bytes = None
    st.session_state.reporte_nombre = None
    st.session_state.sugerencias_ultimas = set()

# SIDEBAR
with st.sidebar:
    st.title("Asistente Caficultura S3")
    st.caption("Plataforma Integrada de Inteligencia Agricola - UNA")
    st.divider()
    st.subheader("Perfil de usuario")
    
    perfil_label = st.radio("Seleccione su perfil:", [
        "Pequeno facilitador tradicional",
        "Extensionista tecnica de campo",
        "Administrador de finca o cooperativa"
    ], index=0)

    if "Pequeno" in perfil_label: 
        perfil_key = "pequeno_productor"; nivel_detalle = "simple"
    elif "Extensionista" in perfil_label: 
        perfil_key = "extensionista_tecnico"; nivel_detalle = "tecnico"
    else: 
        perfil_key = "administrador_finca"; nivel_detalle = "gerencial"

    if st.session_state.get("last_perfil") is not None and st.session_state["last_perfil"] != perfil_key:
        depto_actual_ini = st.session_state.bot.ctx.get("departamento_zona", "Matagalpa")
        sup_orig_ini = st.session_state.bot.ctx.get("superficie_original", {"valor": 1.0, "unidad": "manzana"})
        _reiniciar_sesion(perfil_key, depto_actual_ini, float(sup_orig_ini.get("valor", 1.0)), sup_orig_ini.get("unidad", "manzana"))
        st.session_state.last_perfil = perfil_key
        st.rerun()

    st.session_state["last_perfil"] = perfil_key
    st.session_state.bot.set_perfil(perfil_key)
    st.caption(f"Nivel de detalle: {nivel_detalle}")

    st.divider()
    st.subheader("Ubicacion de la finca")
    depto_actual = st.session_state.bot.ctx.get("departamento_zona", "Matagalpa")
    idx_default = DEPARTAMENTOS.index(depto_actual) if depto_actual in DEPARTAMENTOS else 11
    depto = st.selectbox("Departamento / Region", DEPARTAMENTOS, index=idx_default)
    st.session_state.bot.set_departamento(depto)
    st.session_state.clima_api.set_departamento(depto)
    st.caption(f"Zona activa: {depto}")

    st.divider()
    st.subheader("Superficie de la finca")
    sup_orig = st.session_state.bot.ctx.get("superficie_original", {"valor": 1.0, "unidad": "manzana"})
    unidades = ["manzana", "ha", "m2", "acre"]
    uni_actual = sup_orig.get("unidad", "manzana"); idx_uni = unidades.index(uni_actual) if uni_actual in unidades else 0
    col_sup1, col_sup2 = st.columns([2, 1])
    with col_sup1: sup_val = st.number_input("Valor", min_value=0.01, max_value=10000.0, value=float(sup_orig.get("valor", 1.0)), step=0.5, key="sup_input")
    with col_sup2: sup_uni = st.selectbox("Unidad", unidades, index=idx_uni, key="sup_unidad")
    st.session_state.bot.set_superficie(sup_val, sup_uni)
    st.caption(f"= {st.session_state.bot.ctx['superficie_manzanas']:.4f} manzanas")

    st.divider()
    st.subheader("Estado de modulos")
    st.write("Chatbot: activo")
    st.write("Oraculo LLM:", "activo" if st.session_state.llm._esta_corriendo() else "offline")
    st.write("Vision CNN: activa")
    st.write("Precios: en vivo (API)")

    st.divider()
    if st.button("Reiniciar conversacion", use_container_width=True):
        _reiniciar_sesion(perfil_key, depto, sup_val, sup_uni)
        st.rerun()

# PESTAÑAS
tab_nombres = ["Chat", "Analizar Hoja", "Precios", "Herramientas"]
if nivel_detalle in ("tecnico", "gerencial"):
    tab_nombres.append("Historial")
if nivel_detalle == "gerencial":
    tab_nombres.append("Admin")

tabs = st.tabs(tab_nombres)
tab_chat = tabs[0]
tab_img = tabs[1]
tab_precios = tabs[2]
tab_herramientas = tabs[3]

idx_historial = 4 if len(tab_nombres) > 4 else None
idx_admin = 5 if len(tab_nombres) > 5 else None

# TAB 1 - CHAT
with tab_chat:
    st.title("Conversacion con el Asistente")
    st.caption(f"Departamento activo: {depto} | Superficie: {st.session_state.bot.ctx['superficie_manzanas']:.2f} mz.")

    for rol, texto, intent in st.session_state.chat_historial:
        with st.chat_message("user" if rol == "usuario" else "assistant"):
            st.markdown(texto)
            if rol == "asistente" and nivel_detalle == "tecnico" and intent: st.caption(f"Intent detectado: {intent}")

    if st.session_state.reporte_bytes:
        st.success(f"Reporte listo: {st.session_state.reporte_nombre}")
        st.download_button(label=f"Descargar {st.session_state.reporte_nombre}", data=st.session_state.reporte_bytes, file_name=st.session_state.reporte_nombre, mime="application/pdf", key=f"dl_{st.session_state.reporte_nombre}_{len(st.session_state.chat_historial)}")
        st.caption("Tambien esta guardado en salidas/ (respaldo) y en la carpeta Descargas del equipo.")

    st.divider()
    st.markdown("**Subir una foto de hoja para analizarla ahora**")
    archivo_chat = st.file_uploader("Seleccione una imagen (JPG/PNG)", type=["jpg", "jpeg", "png"], key="chat_uploader")
    
    if (archivo_chat is not None and archivo_chat.name != st.session_state.last_upload):
        st.session_state.last_upload = archivo_chat.name
        os.makedirs("salidas", exist_ok=True)
        nombre_img = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{archivo_chat.name}"
        ruta_img = os.path.join("salidas", nombre_img)
        with open(ruta_img, "wb") as f: f.write(archivo_chat.getbuffer())

        with st.spinner("Clasificando imagen..."):
            resultado = st.session_state.cnn.clasificar_imagen(ruta_img, sintoma_textual=st.session_state.bot.ctx.get("sintoma_observado"))

        st.session_state.bot.registrar_imagen(ruta_img, resultado["clase"], resultado["confianza"], nota_cruce=resultado.get("nota_cruce"))
        
        justificacion = f"\n  - Detalle: {resultado.get('justificacion')}" if resultado.get("justificacion") else ""
        nota = f"\n  >> {resultado['nota_cruce']}" if resultado.get("nota_cruce") else ""
        top2 = f"\n  - Alternativa posible: {resultado['top_2']}" if resultado.get("top_2") else ""
        
        st.session_state.chat_historial.append(("usuario", f"[Imagen adjunta: {archivo_chat.name}]", None))
        st.session_state.chat_historial.append(("asistente", f"Analisis de imagen:\n  - Clase detectada: {resultado['clase']}\n  - Confianza: {resultado['confianza']*100:.1f}%\n  - Modo: {resultado.get('modo', 'N/A')}{justificacion}{top2}\nLa imagen se incluíra en el reporte PDF.{nota}", "Analizar_Imagen_Hoja"))
        st.rerun()

    prompt = st.chat_input("Escriba su consulta...")
    if prompt:
        st.session_state.chat_historial.append(("usuario", prompt, None))
        with st.spinner("Procesando..."):
            respuesta, intent = st.session_state.bot.responder(prompt)
        st.session_state.chat_historial.append(("asistente", respuesta, intent))
        if intent == "Generar_Reporte_PDF": _cargar_reporte_en_sesion(respuesta)
        st.rerun()

    st.divider()
    st.markdown("**Sugerencias rapidas**")
    ultimas = st.session_state.get("sugerencias_ultimas", set())
    
    if st.session_state.chat_historial: 
        pool = sugerencias_para_contexto(st.session_state.bot.ctx, n=6, excluir_ultimas=ultimas)
    else: 
        pool = sugerencias_iniciales(nivel_detalle, n=6)
        
    sugerencias = pool[:4]
    
    if sugerencias:
        st.session_state["sugerencias_ultimas"] = ultimas.union(set(sugerencias))
        cols = st.columns(len(sugerencias))
        for i, sug in enumerate(sugerencias):
            with cols[i]:
                label = sug if len(sug) <= 30 else sug[:28] + "..."
                if st.button(label, use_container_width=True, key=f"sug_{i}_{len(st.session_state.chat_historial)}"):
                    r, intent = st.session_state.bot.responder(sug)
                    st.session_state.chat_historial.append(("usuario", sug, None))
                    st.session_state.chat_historial.append(("asistente", r, intent))
                    if intent == "Generar_Reporte_PDF": _cargar_reporte_en_sesion(r)
                    st.rerun()

    st.divider()
    st.subheader("Encuesta de satisfaccion (CSAT)")
    if not st.session_state.csat_enviado:
        csat_val = st.slider("Califique la utilidad del asistente (1=pobre, 5=excelente)", min_value=1, max_value=5, value=5, key="csat_slider")
        if st.button("Enviar calificacion"):
            registrar_turno(sesion_uuid=st.session_state.bot.sesion_uuid, intent="CSAT_Feedback", entidades={"csat": int(csat_val)}, respuesta=f"Calificacion: {csat_val}", tiempo_seg=0.0)
            st.session_state.csat_enviado = True; st.success(f"Gracias por su calificacion: {csat_val}/5"); st.rerun()
    else: st.info("Ya registro su calificacion en esta sesion. Gracias!")

# TAB 2 - ANALIZAR HOJA
with tab_img:
    st.title("Analisis de Hoja de Cafe")
    st.caption("Suba una fotografia clara de una hoja para detectar enfermedades.")
    archivo = st.file_uploader("Seleccione una imagen (JPG o PNG)", type=["jpg", "jpeg", "png"], key="tab_img_uploader")
    
    if archivo is not None:
        col1, col2 = st.columns([1, 1])
        with col1: st.image(archivo, caption="Imagen cargada", use_container_width=True)
        with col2:
            os.makedirs("salidas", exist_ok=True)
            nombre_img = f"tab_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{archivo.name}"
            ruta = os.path.join("salidas", nombre_img)
            with open(ruta, "wb") as f: f.write(archivo.getbuffer())
            try:
                with st.spinner("Clasificando..."):
                    resultado = st.session_state.cnn.clasificar_imagen(ruta, sintoma_textual=st.session_state.bot.ctx.get("sintoma_observado"))
                
                st.success("Analisis completado")
                st.metric("Enfermedad detectada", resultado.get("clase", "?").replace("_", " "))
                st.metric("Confianza", f"{resultado.get('confianza', 0)*100:.1f}%")
                
                # AQUI SE MUESTRA SIEMPRE EL MODO Y EL ERROR
                st.info(f"Modo de analisis: **{resultado.get('modo')}**")
                if resultado.get("justificacion"): st.warning(f"Detalle: {resultado.get('justificacion')}")
                
                if resultado.get("top_2"): st.info(f"Segunda opcion posible: {resultado['top_2'].replace('_', ' ')}")
                if resultado.get("nota_cruce"): st.warning(f"Cruce con sintoma: {resultado['nota_cruce']}")
                
                st.session_state.bot.registrar_imagen(ruta, resultado["clase"], resultado["confianza"], nota_cruce=resultado.get("nota_cruce"))
                st.caption("Imagen registrada. Aparecera en el proximo reporte PDF.")
                
                if nivel_detalle in ("tecnico", "gerencial"): st.json(resultado)
            except Exception as e: st.error(f"Error al clasificar: {e}")

# TAB 3 - PRECIOS
with tab_precios:
    st.title("Indicadores de Mercado")
    p = leer_precios_actuales()
    col1, col2, col3 = st.columns(3)
    col1.metric("Precio del cafe (USD/qq)", f"${p['precio_cafe_oro_qq_usd']:.2f}")
    col2.metric("Tipo de cambio (NIO/USD)", f"C$ {p['tipo_cambio_usd_nio']:.2f}")
    col3.metric("Mano de obra (NIO/dia)", f"C$ {p['costo_mano_obra_dia_nio']:.0f}")
    
    st.divider()
    st.subheader("Insumos Agricolas")
    col4, col5, col6 = st.columns(3)
    col4.metric("Urea (C$/qq)", f"C$ {p['precio_urea_qq_nio']:.2f}")
    col5.metric("KCl (C$/qq)", f"C$ {p['precio_kcl_qq_nio']:.2f}")
    col6.metric("Fungicida (C$/L)", f"C$ {p['precio_fungicida_litro_nio']:.2f}")

    if st.button("Actualizar precios desde internet"):
        with st.spinner("Consultando APIs externas..."):
            nuevos = actualizar_precios()
        st.success(f"Actualizado: cafe ${nuevos['precio_cafe_oro_qq_usd']}/qq"); st.rerun()
    st.caption(f"Ultima actualizacion: {p.get('ultima_actualizacion', 'N/A')}")

# TAB 4 - HERRAMIENTAS
with tab_herramientas:
    st.title("Herramientas del Caficultor")
    st.caption("Calculadoras rapidas vinculadas a los precios en vivo del mercado.")

    sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs([
        "Rentabilidad", "Calendario de Labores", "Convertidor de Unidades", "Dosificacion de Fertilizante"
    ])

    precios_actuales = leer_precios_actuales()

    with sub_tab1:
        st.subheader("Calculadora de Rentabilidad")
        st.caption("Determina si tu cosecha genera ganancias o perdidas basandose en los precios actuales del mercado.")

        col_a, col_b = st.columns(2)
        with col_a:
            r_sup = st.number_input("Superficie (mz)", min_value=0.1, value=float(st.session_state.bot.ctx["superficie_manzanas"]), step=0.5, key="r_sup")
            r_rend = st.number_input("Rendimiento esperado (qq/mz)", min_value=1.0, value=20.0, step=0.5, key="r_rend")
            r_precio = st.number_input("Precio del cafe (USD/qq)", min_value=50.0, value=float(precios_actuales['precio_cafe_oro_qq_usd']), step=1.0, key="r_precio")
        with col_b:
            r_costo = st.number_input("Costo total de produccion (C$/mz)", min_value=0.0, value=15000.0, step=500.0, key="r_costo")
            r_cambio = st.number_input("Tipo de cambio (C$/USD)", min_value=1.0, value=float(precios_actuales['tipo_cambio_usd_nio']), step=0.1, key="r_cambio")

        ingreso_qq_nio = r_precio * r_cambio
        ingreso_total = ingreso_qq_nio * r_rend * r_sup
        costo_total = r_costo * r_sup
        beneficio = ingreso_total - costo_total
        margen = (beneficio / ingreso_total * 100) if ingreso_total > 0 else 0
        punto_eq = r_costo / ingreso_qq_nio if ingreso_qq_nio > 0 else 0

        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ingreso bruto (C$)", f"C$ {ingreso_total:,.0f}")
        c2.metric("Costo total (C$)", f"C$ {costo_total:,.0f}")
        c3.metric("Beneficio neto (C$)", f"C$ {beneficio:,.0f}", delta=f"{margen:.1f}% margen")
        c4.metric("Punto de equilibrio (qq/mz)", f"{punto_eq:.1f}", help="Rendimiento minimo para no perder dinero")

        if beneficio > 0:
            st.success(f"Resultado: La cosecha es RENTABLE. Ganancia estimada: C$ {beneficio:,.0f}")
        else:
            st.error(f"Resultado: La cosecha presenta PERDIDAS. Se requiere un minimo de {punto_eq:.1f} qq/mz para cubrir costos.")

    with sub_tab2:
        st.subheader("Calendario de Labores Agricolas")
        st.caption("Recomendaciones tecnicas segun la fase fenologica del cafe en Nicaragua.")

        mes = st.selectbox("Seleccione el mes:", [
            "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
        ])

        calendario = {
            "Enero": ("Floracion temprana", ["Aplicar fertilizante foliar (boro + zinc)", "Monitorear roya post-floracion", "Control manual de malezas", "Riego si hay sequia"]),
            "Febrero": ("Floracion principal", ["Aplicar fungicida preventivo (caldo bordeles)", "Fertilizacion nitrogenada (urea 2 qq/mz)", "Monitoreo de broca", "Manejo de sombra al 40-50%"]),
            "Marzo": ("Llenado de grano temprano", ["Fertilizacion potasica (KCl 1.5 qq/mz)", "Control de roya intensivo", "Poda sanitaria", "Instalacion de trampas para broca"]),
            "Abril": ("Llenado de grano", ["Riego complementario", "Monitoreo de antracnosis", "Fertilizacion foliar con magnesio", "Control de malezas"]),
            "Mayo": ("Maduracion inicial", ["Preparar infraestructura de beneficio", "Ultima aplicacion de fungicida", "Contratar mano de obra de corte"]),
            "Junio": ("Inicio de cosecha", ["Inicio de recoleccion selectiva", "Beneficiado humedo", "Registro de rendimientos", "Suspender fertilizacion"]),
            "Julio": ("Cosecha plena", ["Pico de recoleccion", "Control de calidad del grano", "Manejo de sombra", "Secado adecuado"]),
            "Agosto": ("Fin de cosecha", ["Ultimas recolecciones", "Limpieza de lotes", "Preparacion para poda"]),
            "Septiembre": ("Poda post-cosecha", ["Poda de renovacion", "Eliminacion de tejido enfermo", "Aplicacion de cal al suelo", "Analisis de suelo"]),
            "Octubre": ("Epoca lluviosa", ["Control intensivo de roya", "Prevencion de mal de hilachas", "Mejorar drenajes", "Fertilizacion con P y K"]),
            "Noviembre": ("Lluvia constante", ["Monitoreo de ojo de gallo", "Control de antracnosis", "Raleo de sombra", "Aplicacion de fungicidas"]),
            "Diciembre": ("Crecimiento vegetativo", ["Fertilizacion con N completo", "Preparacion para floracion", "Revision de drenajes", "Mantenimiento de herramientas"])
        }

        fase, labores = calendario[mes]
        st.markdown(f"### {fase}")
        st.markdown(f"**Labores recomendadas para {mes}:**")
        for lab in labores:
            st.markdown(f"- {lab}")

        st.info("Nota: Las labores deben ajustarse segun la altitud y el microclima especifico de cada finca.")

    with sub_tab3:
        st.subheader("Convertidor de Unidades")
        st.caption("Convierte unidades agricolas y financieras utilizando los datos del mercado del dia de hoy.")

        col_c1, col_c2 = st.columns(2)

        with col_c1:
            st.markdown("**Superficie**")
            sup_in = st.number_input("Manzanas", min_value=0.0, value=1.0, step=0.1, key="conv_mz")
            st.write(f"= **{sup_in * 1.4184:.4f}** hectareas")
            st.write(f"= **{sup_in * 14184:.0f}** metros cuadrados")
            st.write(f"= **{sup_in * 1.7443:.4f}** acres")

            st.markdown("**Peso**")
            qq_in = st.number_input("Quintales", min_value=0.0, value=1.0, step=0.1, key="conv_qq")
            st.write(f"= **{qq_in * 100:.0f}** libras")
            st.write(f"= **{qq_in * 45.36:.2f}** kilogramos")

        with col_c2:
            st.markdown("**Moneda**")
            usd_in = st.number_input("Dolares (USD)", min_value=0.0, value=100.0, step=10.0, key="conv_usd")
            cambio_actual = precios_actuales.get("tipo_cambio_usd_nio", 36.62)
            st.write(f"= **C$ {usd_in * cambio_actual:,.2f}** cordobas")
            st.caption(f"Tasa de cambio en vivo: C$ {cambio_actual:.2f}/USD")

            st.markdown("**Cafe oro**")
            latas_in = st.number_input("Latas de cafe (uva)", min_value=0.0, value=1.0, step=0.5, key="conv_lata")
            precio_qq_usd = precios_actuales.get("precio_cafe_oro_qq_usd", 220.0)
            st.write(f"= **{latas_in * 0.25:.2f}** quintales oro (aprox.)")
            st.write(f"= **USD {latas_in * 0.25 * precio_qq_usd:.2f}** (a precio actual)")

    with sub_tab4:
        st.subheader("Dosificacion y Costo de Fertilizante")
        st.caption("Calcula los quintales a comprar y el costo total basandose en los precios de insumos del dia.")

        f_sup = st.number_input("Superficie a fertilizar (mz)", min_value=0.1, value=float(st.session_state.bot.ctx["superficie_manzanas"]), step=0.5, key="f_sup")
        f_dosis = st.number_input("Dosis recomendada (qq/mz)", min_value=0.1, value=2.0, step=0.5, key="f_dosis")

        f_tipo = st.selectbox("Tipo de fertilizante:", [
            "Urea 46% (N)", "18-46-0 (P)", "KCl (K)", "Ferticafe Cosecha", "Formula completa 12-24-12"
        ])

        precios_ref = {
            "Urea 46% (N)": precios_actuales.get("precio_urea_qq_nio", 1650.0),
            "18-46-0 (P)": precios_actuales.get("precio_urea_qq_nio", 1800.0), 
            "KCl (K)": precios_actuales.get("precio_kcl_qq_nio", 1400.0),
            "Ferticafe Cosecha": 1900.0,
            "Formula completa 12-24-12": 1750.0,
        }

        p_qq = precios_ref[f_tipo]
        precio_edit = st.number_input("Precio por quintal (C$)", min_value=1.0, value=float(p_qq), step=50.0, key="f_precio")

        total_qq = f_sup * f_dosis
        costo_total = total_qq * precio_edit

        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total a aplicar", f"{total_qq:.2f} qq")
        c2.metric("Costo total", f"C$ {costo_total:,.0f}")
        c3.metric("Costo por manzana", f"C$ {costo_total/f_sup:,.0f}")

        st.info(f"Recomendacion: Para {f_sup} manzanas con dosis de {f_dosis} qq/mz de {f_tipo}, necesita adquirir {total_qq:.1f} quintales.")

# TAB 5 - HISTORIAL
if idx_historial is not None:
    with tabs[idx_historial]:
        st.title("Historial de Sesiones")
        hist = consultar_historial(limite=30)
        if hist:
            df = pd.DataFrame(hist); st.dataframe(df, use_container_width=True, hide_index=True)
        else: st.info("Aun no hay sesiones registradas.")

# TAB 6 - ADMIN
if idx_admin is not None:
    with tabs[idx_admin]:
        st.title("Panel del Administrador")
        st.info("Acceso exclusivo para Administradores de Finca.")
        stats = obtener_stats()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total sesiones", stats["total_sesiones"]); col2.metric("Total mensajes", stats["total_mensajes"])
        col3.metric("Fallbacks LLM",  stats["total_fallbacks"]); col4.metric("Tasa de fallback", f"{stats['tasa_fallback']*100:.1f}%")

        st.divider(); st.subheader("KPIs conversacionales")
        kpis = calcular_kpis()
        if "error" not in kpis:
            for k, v in kpis.items(): st.text(f"{k}: {v}")

        st.divider(); st.subheader("Satisfaccion del usuario (CSAT)")
        csat_avg = calcular_csat()
        if csat_avg is None: st.info("Aun no hay calificaciones CSAT registradas.")
        else:
            col_cs1, col_cs2 = st.columns(2)
            col_cs1.metric("CSAT promedio", f"{csat_avg}/5")
            col_cs2.metric("Meta (>= 4.0)", value="4.0/5", delta=("Cumple" if csat_avg >= 4.0 else "Por debajo"))

        st.divider(); st.subheader("Generar reporte consolidado")
        if st.button("Generar Reporte del Sistema"):
            bot = st.session_state.bot
            datos = {"sesion_id": bot.sesion_uuid, "zona": bot.ctx.get("departamento_zona", "Matagalpa"), "superficie_manzanas": bot.ctx.get("superficie_manzanas", 1.0), "clima": bot.ctx.get("clima", {}), "diagnosticos": bot.ctx.get("diagnosticos", []), "riesgo": bot.ctx.get("riesgo", {}), "optimizacion": bot.ctx.get("optimizacion", {}), "imagenes": bot.ctx.get("imagenes_analizadas", [])}
            ruta = generar_reporte(datos, nombre=f"admin_{bot.sesion_uuid}.pdf")
            ruta_desc = exportar_a_descargas(ruta)
            if ruta_desc: st.success(f"Copia en Descargas: {ruta_desc}")
            with open(ruta, "rb") as f: st.download_button(label="Descargar PDF", data=f.read(), file_name=os.path.basename(ruta), mime="application/pdf")

st.divider()
st.caption(f"Plataforma S3 - UNA | Sesion: {st.session_state.bot.sesion_uuid} | Perfil: {perfil_key} | Depto: {depto} | Superficie: {st.session_state.bot.ctx['superficie_manzanas']:.2f} mz | Hora: {datetime.now().strftime('%Y-%m-%d %H:%M')}")