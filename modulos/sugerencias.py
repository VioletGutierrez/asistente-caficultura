# ============================================================
# modulos/sugerencias.py
# ============================================================
import random

SINTOMAS = ["Tengo manchas naranjas en las hojas", "Veo polvo amarillo en el enves", "Hay manchas negras en las ramas", "Sospecho roya en mi cafetal", "Tengo granos perforados por broca", "Hojas amarillas en crecimiento"]
CLIMA = ["Como esta el clima hoy?", "Cual es la humedad actual?", "Va a llover en mi zona?", "Que temperatura hace?"]
OPTIMIZACION = ["Optimizar para 1 manzana", "Dame un plan de fertilizacion", "Cuanto debo aplicar de nitrogeno?", "Optimizar riego"]
PRECIOS = ["Cual es el precio del cafe hoy?", "Consultar tipo de cambio", "Precio de la urea", "Cuanto cuesta el fungicida?"]
TEORIA = ["Que es la antracnosis?", "Como preparo caldo bordeles?", "Por que se caen las hojas?", "Como controlo la broca?"]
REPORTES = ["Generar reporte PDF", "Necesito el reporte tecnico", "Descargar el reporte"]

def sugerencias_iniciales(nivel="simple", n=4):
    if nivel == "simple":
        return ["Tengo manchas naranjas", "Como esta el clima?", "Optimizar para 1 manzana", "Generar reporte PDF"][:n]
    return ["Que es la roya?", "Subir foto de hoja", "Optimizar plan bioeconomico", "Generar reporte PDF"][:n]

def sugerencias_para_contexto(ctx, n=4, excluir_ultimas=None):
    excluir_ultimas = excluir_ultimas or set()
    pool = []
    
    # 1. Si hay imágenes analizadas, sugerir preguntas sobre ellas
    imagenes = ctx.get("imagenes_analizadas") or []
    if imagenes:
        ultima = imagenes[-1].get("clase", "Sana")
        if ultima == "Roya":
            pool.extend(["Que fungicida aplico para roya?", "Como prevenir la roya?", "Ver plan de fertilizacion"])
        elif ultima == "Antracnosis":
            pool.extend(["Que es la antracnosis?", "Como trato la antracnosis?", "Ver plan de fertilizacion"])
        else:
            pool.extend(["Que hago si mi hoja esta sana?", "Como mantener mi cafe sano?", "Ver plan de fertilizacion"])

    # 2. Si hay riesgo alto, sugerir clima o tratamiento
    if ctx.get("riesgo", {}).get("riesgo_global", 0) > 0.4:
        pool.extend(["Como controlo el riesgo alto?", "Ver recomendaciones tecnicas"])

    # 3. Sugerencias generales
    pool.extend(random.sample(TEORIA, 2))
    pool.extend(random.sample(CLIMA, 1))
    pool.extend(random.sample(OPTIMIZACION, 1))
    pool.extend(random.sample(REPORTES, 1))
    pool.extend(random.sample(PRECIOS, 1))

    resultado = []
    vistos = set()
    for s in pool:
        if s not in vistos and s not in excluir_ultimas:
            vistos.add(s)
            resultado.append(s)
            if len(resultado) >= n:
                break
                
    # Fallback de seguridad
    if not resultado:
        resultado = ["Como esta el clima?", "Que es la roya?", "Generar reporte PDF", "Optimizar riego"]
        
    return resultado