# ============================================================
# modulos/reporte_pdf.py
# Generador de reportes PDF
# ============================================================
import os
import shutil
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
)

COLOR_PRIMARIO = colors.HexColor("#2d6a4f")
COLOR_SEC       = colors.HexColor("#b7e4c7")
COLOR_FONDO     = colors.HexColor("#f1f8f5")

def _safe_image(ruta, max_w=8*cm, max_h=5*cm):
    try:
        if ruta and os.path.exists(ruta):
            return Image(ruta, width=max_w, height=max_h, kind="proportional")
    except Exception:
        pass
    return None

def _carpeta_descargas():
    home = Path.home()
    for nombre in ("Downloads", "Descargas", "downloads"):
        c = home / nombre
        if c.exists() and c.is_dir(): return c
    destino = home / "Downloads"
    try:
        destino.mkdir(parents=True, exist_ok=True)
        return destino
    except Exception: return None

def exportar_a_descargas(ruta_origen):
    try:
        destino_dir = _carpeta_descargas()
        if destino_dir is None: return None
        nombre = os.path.basename(ruta_origen)
        destino = destino_dir / nombre
        if destino.exists():
            base, ext = os.path.splitext(nombre)
            ts = datetime.now().strftime("%H%M%S")
            destino = destino_dir / f"{base}_{ts}{ext}"
        shutil.copy2(ruta_origen, destino)
        return str(destino)
    except Exception as e:
        return None

def generar_reporte(datos, nombre="reporte_tecnico.pdf"):
    os.makedirs("salidas", exist_ok=True)
    ruta = os.path.join("salidas", nombre)

    doc = SimpleDocTemplate(ruta, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    estilos = getSampleStyleSheet()
    estilos.add(ParagraphStyle(name="Titulo", parent=estilos["Title"], textColor=COLOR_PRIMARIO, fontSize=18, spaceAfter=6))
    estilos.add(ParagraphStyle(name="Sub", parent=estilos["Heading2"], textColor=COLOR_PRIMARIO, fontSize=13, spaceAfter=6))
    estilos.add(ParagraphStyle(name="Body2", parent=estilos["BodyText"], fontSize=9, leading=12))

    flow = []
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Encabezado
    flow.append(Paragraph("ASISTENTE INTELIGENTE PARA LA CAFICULTURA", estilos["Titulo"]))
    flow.append(Paragraph("Reporte tecnico - Plataforma Integrada de Inteligencia Agricola S3", estilos["Body2"]))
    flow.append(Spacer(1, 0.4*cm))

    # 1. Datos generales
    flow.append(Paragraph("1. Datos generales", estilos["Sub"]))
    tabla_datos = [
        ["Sesion:", str(datos.get("sesion_id", "N/A"))],
        ["Zona:", str(datos.get("zona", "N/A"))],
        ["Superficie:", f"{datos.get('superficie_manzanas', 1.0)} manzanas"],
        ["Fecha:", fecha],
    ]
    t = Table(tabla_datos, colWidths=[4*cm, 12*cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("GRID",     (0,0), (-1,-1), 0.3, colors.grey),
        ("BACKGROUND", (0,0), (0,-1), COLOR_FONDO),
    ]))
    flow.append(t)
    flow.append(Spacer(1, 0.4*cm))

    # 2. Clima
    flow.append(Paragraph("2. Condiciones climaticas", estilos["Sub"]))
    clima = datos.get("clima", {}) or {}
    if clima:
        tabla_clima = [["Variable", "Valor"]]
        tabla_clima.append(["Temperatura", f"{clima.get('temperatura','N/A')} C"])
        tabla_clima.append(["Humedad relativa", f"{clima.get('humedad_relativa','N/A')} %"])
        tabla_clima.append(["Lluvia previa", "Si" if clima.get("lluvia_previa") else "No"])
        tabla_clima.append(["Fuente", str(clima.get("fuente", "N/A"))])
        t = Table(tabla_clima, colWidths=[6*cm, 10*cm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("BACKGROUND", (0,0), (-1,0), COLOR_PRIMARIO),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("GRID", (0,0), (-1,-1), 0.3, colors.grey),
        ]))
        flow.append(t)
    else:
        flow.append(Paragraph("<i>No se registraron datos climaticos.</i>", estilos["Body2"]))
    flow.append(Spacer(1, 0.4*cm))

    # 3. Imagenes (Diagnostico IA)
    imagenes = datos.get("imagenes") or []
    if imagenes:
        flow.append(Paragraph("3. Analisis de imagenes foliares", estilos["Sub"]))
        tabla_img = [["#", "Archivo", "Clase detectada", "Confianza", "Motor"]]
        for i, img in enumerate(imagenes, 1):
            tabla_img.append([
                str(i),
                os.path.basename(img.get("ruta", "N/A")),
                img.get("clase", "N/A").replace("_", " "),
                f"{img.get('confianza', 0)*100:.1f}%",
                img.get("modo", "N/A")
            ])
        t = Table(tabla_img, colWidths=[1*cm, 5*cm, 4*cm, 2.5*cm, 3.5*cm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("BACKGROUND", (0,0), (-1,0), COLOR_PRIMARIO),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("GRID", (0,0), (-1,-1), 0.3, colors.grey),
            ("ALIGN", (3,1), (3,-1), "CENTER"),
        ]))
        flow.append(t)
        flow.append(Spacer(1, 0.3*cm))
        
        for img in imagenes:
            img_obj = _safe_image(img.get("ruta"))
            just = img.get("justificacion", "")
            nota = img.get("nota_cruce", "")
            texto = f"<b>Diagnostico:</b> {img.get('clase','').replace('_',' ')}<br/>"
            if just: texto += f"<b>Justificacion tecnica:</b> {just}<br/>"
            if nota: texto += f"<i>{nota}</i>"
            
            if img_obj:
                flow.append(Paragraph(texto, estilos["Body2"]))
                flow.append(img_obj)
                flow.append(Spacer(1, 0.3*cm))
        flow.append(Spacer(1, 0.2*cm))

    # 4. Diagnostico General
    flow.append(Paragraph("4. Diagnostico fitosanitario general", estilos["Sub"]))
    diagnosticos = datos.get("diagnosticos") or []
    if diagnosticos:
        for i, d in enumerate(diagnosticos, 1):
            regla = d.get("regla_id", "N/A")
            flow.append(Paragraph(f"<b>{i}. {d.get('diagnostico','N/A')}</b> <font size=7 color='#666'>({regla})</font>", estilos["Body2"]))
            flow.append(Paragraph(f"Recomendacion: {d.get('recomendacion','N/A')}", estilos["Body2"]))
            flow.append(Spacer(1, 0.2*cm))
    else:
        flow.append(Paragraph("<i>No se emitio diagnostico determinista.</i>", estilos["Body2"]))
    flow.append(Spacer(1, 0.4*cm))

    # 5. Riesgo
    flow.append(Paragraph("5. Mapa de riesgo (Red Bayesiana)", estilos["Sub"]))
    riesgo = datos.get("riesgo") or {}
    if riesgo:
        tabla_riesgo = [["Enfermedad", "Probabilidad"]]
        for k in ("roya", "antracnosis", "ojo_gallo"):
            v = riesgo.get(k, 0)
            tabla_riesgo.append([k.capitalize(), f"{v*100:.1f}%"])
        tabla_riesgo.append(["Riesgo global", f"{riesgo.get('riesgo_global',0)*100:.1f}%"])
        t = Table(tabla_riesgo, colWidths=[8*cm, 8*cm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("BACKGROUND", (0,0), (-1,0), COLOR_PRIMARIO),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("GRID", (0,0), (-1,-1), 0.3, colors.grey),
        ]))
        flow.append(t)
    else:
        flow.append(Paragraph("<i>No se calcularon probabilidades.</i>", estilos["Body2"]))
    flow.append(Spacer(1, 0.4*cm))

    # 6. Optimizacion
    flow.append(Paragraph("6. Plan bioeconomico optimizado (C$)", estilos["Sub"]))
    opt = datos.get("optimizacion") or {}
    dosis = opt.get("dosis_por_mz") or {}
    if dosis:
        tabla_opt = [["Insumo", "Dosis / mz", "Costo aprox."]]
        costo_aprox = {"riego_m3": ("Riego", 12.0), "N_kg": ("Nitrogeno", 45.0), "P_kg": ("Fosforo", 52.0), "K_kg": ("Potasio", 40.0), "fungicida_L": ("Fungicida", 350.0)}
        for k, (nombre_insumo, costo_unit) in costo_aprox.items():
            val = dosis.get(k, 0)
            tabla_opt.append([nombre_insumo, f"{val}", f"C$ {val*costo_unit:,.2f}"])
        tabla_opt.append(["COSTO TOTAL PLAN", "", f"C$ {opt.get('costo_total_nio',0):,.2f}"])
        t = Table(tabla_opt, colWidths=[6*cm, 5*cm, 5*cm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("BACKGROUND", (0,0), (-1,0), COLOR_PRIMARIO),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("GRID", (0,0), (-1,-1), 0.3, colors.grey),
            ("BACKGROUND", (0,-1), (-1,-1), COLOR_SEC),
            ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
        ]))
        flow.append(t)
        flow.append(Spacer(1, 0.2*cm))
        flow.append(Paragraph(f"<b>Rendimiento esperado:</b> {opt.get('rendimiento_qq_mz',0)} qq/mz &nbsp;&nbsp; <b>Beneficio neto:</b> C$ {opt.get('beneficio_neto_nio',0):,.2f}", estilos["Body2"]))
    else:
        flow.append(Paragraph("<i>No se solicito optimizacion.</i>", estilos["Body2"]))
    flow.append(Spacer(1, 0.4*cm))

    # 7. Recomendaciones
    flow.append(Paragraph("7. Recomendaciones generales", estilos["Sub"]))
    for r in ["Monitorear el cultivo cada 7-15 dias en epoca lluviosa.", "Mantener registro escrito de aplicaciones y sintomas.", "Consultar al extensionista del INTA si los sintomas persisten.", "Realizar analisis foliar al menos 2 veces por ciclo."]:
        flow.append(Paragraph(f"- {r}", estilos["Body2"]))
    flow.append(Spacer(1, 0.6*cm))

    flow.append(Paragraph(f"<i>Generado el {fecha} por la Plataforma S3 - UNA Managua</i>", estilos["Body2"]))
    doc.build(flow)
    return ruta