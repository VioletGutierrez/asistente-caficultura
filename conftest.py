# ============================================================
# modulos/reporte_pdf.py
# Generacion de reportes tecnicos con ReportLab
# Referencia: IA.docx Pag. 46
# ============================================================
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from config import SALIDAS_DIR


# ------------------------------------------------------------
def _generar_grafico_riesgo(riesgo, ruta_png):
    """Genera el grafico de barras con los niveles de riesgo."""
    if not riesgo:
        return None

    enfermedades = ["Roya", "Antracnosis", "Ojo de gallo"]
    valores = [
        riesgo.get("roya", 0.0),
        riesgo.get("antracnosis", 0.0),
        riesgo.get("ojo_gallo", 0.0),
    ]
    colores = ["#c0392b", "#e67e22", "#2980b9"]

    plt.figure(figsize=(6, 3))
    barras = plt.bar(enfermedades, valores, color=colores)
    plt.ylim(0, 1.0)
    plt.ylabel("Probabilidad de riesgo")
    plt.title("Mapa de riesgo fitosanitario (Red Bayesiana)")
    for barra in barras:
        h = barra.get_height()
        plt.text(
            barra.get_x() + barra.get_width() / 2.0,
            h + 0.02,
            f"{h*100:.1f}%",
            ha="center", va="bottom", fontsize=9,
        )
    plt.tight_layout()
    plt.savefig(ruta_png, dpi=120)
    plt.close()
    return ruta_png


# ------------------------------------------------------------
def generar_reporte(datos, nombre="reporte_caficultura.pdf"):
    """
    Construye el PDF. IMPORTANTE: el archivo de la imagen temporal
    se borra SOLO despues de doc.build(), nunca antes.
    """
    ruta_pdf = str(SALIDAS_DIR / nombre)
    ruta_png = str(SALIDAS_DIR / "_tmp_riesgo.png")

    doc = SimpleDocTemplate(
        ruta_pdf, pagesize=letter,
        leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40,
    )

    estilos = getSampleStyleSheet()
    titulo_estilo = ParagraphStyle(
        "Titulo", parent=estilos["Title"],
        fontSize=16, textColor=colors.HexColor("#1e5631"),
    )
    seccion_estilo = ParagraphStyle(
        "Seccion", parent=estilos["Heading2"],
        fontSize=12, textColor=colors.HexColor("#1e5631"),
        spaceBefore=10, spaceAfter=6,
    )

    elementos = []
    archivos_temporales = []  # Se borran al final, despues de doc.build()

    # 1. Encabezado
    elementos.append(Paragraph(
        "ASISTENTE INTELIGENTE PARA LA CAFICULTURA", titulo_estilo
    ))
    elementos.append(Paragraph(
        "Reporte tecnico - Plataforma Integrada de Inteligencia Agricola S3",
        estilos["Normal"],
    ))
    elementos.append(Spacer(1, 12))

    # 2. Datos generales
    elementos.append(Paragraph("1. Datos generales", seccion_estilo))
    general = datos.get("general", {})
    if not general:
        general = {
            "Sesion":     datos.get("sesion_id", "N/A"),
            "Zona":       datos.get("zona", "Matagalpa, Nicaragua"),
            "Superficie": f"{datos.get('superficie_manzanas', 1.0)} manzanas",
            "Fecha":      datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    for k, v in general.items():
        elementos.append(Paragraph(f"<b>{k}:</b> {v}", estilos["Normal"]))
    elementos.append(Spacer(1, 8))

    # 3. Clima
    elementos.append(Paragraph("2. Condiciones climaticas", seccion_estilo))
    clima = datos.get("clima", {})
    if clima:
        elementos.append(Paragraph(
            f"<b>Temperatura:</b> {clima.get('temperatura', 'N/A')} C",
            estilos["Normal"]))
        elementos.append(Paragraph(
            f"<b>Humedad relativa:</b> {clima.get('humedad_relativa', 'N/A')} %",
            estilos["Normal"]))
        elementos.append(Paragraph(
            f"<b>Lluvia previa:</b> "
            f"{'Si' if clima.get('lluvia_previa') else 'No'}",
            estilos["Normal"]))
        elementos.append(Paragraph(
            f"<b>Fuente:</b> {clima.get('fuente', 'N/A')}",
            estilos["Normal"]))
    else:
        elementos.append(Paragraph(
            "No se registraron datos climaticos en esta sesion.",
            estilos["Normal"]))
    elementos.append(Spacer(1, 8))

    # 4. Diagnostico
    elementos.append(Paragraph("3. Diagnostico fitosanitario", seccion_estilo))
    diagnosticos = datos.get("diagnosticos", [])
    if diagnosticos:
        for d in diagnosticos:
            elementos.append(Paragraph(
                f"<b>[{d.get('regla_id', 'N/A')}] "
                f"{d.get('diagnostico', 'Desconocido')}</b>",
                estilos["Normal"]))
            elementos.append(Paragraph(
                f"Recomendacion: {d.get('recomendacion', 'Sin recomendacion')}",
                estilos["Normal"]))
            elementos.append(Spacer(1, 4))
    else:
        elementos.append(Paragraph(
            "No se emitio diagnostico determinista en esta sesion.",
            estilos["Normal"]))
    elementos.append(Spacer(1, 8))

    # 5. Mapa de riesgo
    elementos.append(Paragraph("4. Mapa de riesgo (Red Bayesiana)", seccion_estilo))
    riesgo = datos.get("riesgo", {})
    if riesgo:
        ruta_grafico = _generar_grafico_riesgo(riesgo, ruta_png)
        if ruta_grafico and os.path.exists(ruta_grafico):
            elementos.append(Image(ruta_grafico, width=380, height=190))
            archivos_temporales.append(ruta_grafico)
        elementos.append(Paragraph(
            f"<b>Riesgo global:</b> "
            f"{riesgo.get('riesgo_global', 0)*100:.1f}%",
            estilos["Normal"]))
    else:
        elementos.append(Paragraph(
            "No se calcularon probabilidades de riesgo.",
            estilos["Normal"]))
    elementos.append(Spacer(1, 8))

    # 6. Plan bioeconomico
    elementos.append(Paragraph("5. Plan bioeconomico optimizado (C$)",
                               seccion_estilo))
    opt = datos.get("optimizacion", {})
    if opt:
        d = opt.get("dosis_por_mz", {})
        data_tabla = [
            ["Insumo prescrito", "Cantidad / mz",
             "Costo unitario (C$)", "Subtotal (C$)"],
            ["Riego", f"{d.get('riego_m3', 0)} m3", "12.00",
             f"{d.get('riego_m3', 0) * 12.00:,.2f}"],
            ["Nitrogeno (N)", f"{d.get('N_kg', 0)} kg", "16.50",
             f"{d.get('N_kg', 0) * 16.50:,.2f}"],
            ["Fosforo (P)", f"{d.get('P_kg', 0)} kg", "17.50",
             f"{d.get('P_kg', 0) * 17.50:,.2f}"],
            ["Potasio (K)", f"{d.get('K_kg', 0)} kg", "23.33",
             f"{d.get('K_kg', 0) * 23.33:,.2f}"],
            ["Fungicida", f"{d.get('fungicida_L', 0)} L", "950.00",
             f"{d.get('fungicida_L', 0) * 950.00:,.2f}"],
            ["Mano de obra", "1 jornada", "500.00", "500.00"],
        ]
        tabla = Table(data_tabla, colWidths=[130, 110, 120, 110])
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d5e8d4")),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN",      (1, 1), (-1, -1), "CENTER"),
            ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ]))
        elementos.append(tabla)
        elementos.append(Spacer(1, 10))

        elementos.append(Paragraph("6. Resumen financiero", seccion_estilo))
        elementos.append(Paragraph(
            f"<b>Rendimiento esperado:</b> "
            f"{opt.get('rendimiento_qq_mz', 0)} qq oro / mz",
            estilos["Normal"]))
        elementos.append(Paragraph(
            f"<b>Precio del cafe usado:</b> "
            f"{opt.get('precio_cafe_nio_qq', 0):,.2f} C$ / qq",
            estilos["Normal"]))
        elementos.append(Paragraph(
            f'<font color="#c0392b"><b>Costo total:</b> '
            f'{opt.get("costo_total_nio", 0):,.2f} C$</font>',
            estilos["Normal"]))
        elementos.append(Paragraph(
            f'<font color="#27ae60"><b>Beneficio neto:</b> '
            f'{opt.get("beneficio_neto_nio", 0):,.2f} C$</font>',
            estilos["Normal"]))
    else:
        elementos.append(Paragraph(
            "No se solicito optimizacion bioeconomica en esta sesion.",
            estilos["Normal"]))

    # 7. Pie
    elementos.append(Spacer(1, 20))
    elementos.append(Paragraph(
        f"<i>Generado el {datetime.now().strftime('%Y-%m-%d a las %H:%M')} "
        f"por la Plataforma S3 - UNA Managua</i>",
        estilos["Italic"]))

    # === Construir el PDF (aca se leen las imagenes) ===
    try:
        doc.build(elementos)
    finally:
        # Ahora SI, despues de que ReportLab leyo la imagen, la borramos
        for ruta in archivos_temporales:
            try:
                if os.path.exists(ruta):
                    os.remove(ruta)
            except Exception as e:
                print(f"[reporte_pdf] No se pudo borrar {ruta}: {e}")

    return ruta_pdf


# ------------------------------------------------------------
if __name__ == "__main__":
    demo = {
        "sesion_id": "DEMO-1234",
        "zona": "Matagalpa, Nicaragua",
        "superficie_manzanas": 1.5,
        "clima": {
            "temperatura": 22.5, "humedad_relativa": 82,
            "lluvia_previa": True, "fuente": "Open-Meteo",
        },
        "diagnosticos": [{
            "regla_id": "R001",
            "diagnostico": "Hemileia vastatrix (Roya)",
            "recomendacion": "Aplicar fungicida cuprico mas triadimefon.",
        }],
        "riesgo": {"roya": 0.72, "antracnosis": 0.15,
                   "ojo_gallo": 0.13, "riesgo_global": 0.72},
        "optimizacion": {
            "dosis_por_mz": {
                "riego_m3": 145, "N_kg": 92, "P_kg": 40,
                "K_kg": 60, "fungicida_L": 1.8,
            },
            "rendimiento_qq_mz": 24.5,
            "costo_total_nio": 12500,
            "beneficio_neto_nio": 48000,
            "precio_cafe_nio_qq": 8056.40,
        },
    }
    ruta = generar_reporte(demo, "reporte_demo.pdf")
    print(f"Reporte generado: {ruta}")