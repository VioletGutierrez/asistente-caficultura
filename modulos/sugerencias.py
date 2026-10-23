# ============================================================
# modulos/sugerencias.py
# Banco de sugerencias rapidas + seleccion contextual
# ~200 frases base -> miles de combinaciones con rotacion
# ============================================================
import random


# ============================================================
# Bancos por categoria
# ============================================================
SINTOMAS = [
    # Roya (5)
    "Tengo manchas naranjas en las hojas",
    "Veo polvo amarillo en el enves de las hojas",
    "Las hojas tienen pustulas anaranjadas",
    "Hay manchas amarillas con borde naranja",
    "Sospecho roya en mi cafetal",
    # Antracnosis (5)
    "Tengo manchas negras en las ramas",
    "Veo lesiones hundidas en las hojas",
    "Hay muerte de ramas en mi cafeto",
    "Los frutos se estan momificando",
    "Sospecho antracnosis",
    # Ojo de gallo (4)
    "Tengo manchas circulares con centro gris",
    "Veo borde cafe alrededor de manchas",
    "Hay hojas con centro gris y borde cafe",
    "Sospecho ojo de gallo",
    # Mal de hilachas (3)
    "Veo telarana blanca en las ramas",
    "Hay hilos blancos sobre las hojas",
    "Las ramas se estan muriendo de arriba hacia abajo",
    # Mancha de hierro (3)
    "Tengo mancha cafe rojiza con halo amarillo",
    "Veo manchas con centro blanco en hojas jovenes",
    "Sospecho mancha de hierro",
    # Mancha mantecosa (3)
    "Tengo mancha grasosa en las hojas",
    "Veo manchas cafe oscuras pegadas",
    "Sospecho mancha mantecosa",
    # Pudricion radicular (3)
    "Tengo raiz negra en la planta",
    "Hay necrosis radicular y muerte subita",
    "Sospecho pudricion radicular por Rosellinia",
    # Broca (4)
    "Tengo granos perforados por broca",
    "Veo perforaciones en los frutos del cafe",
    "Hay broca visible en los granos",
    "Sospecho broca del cafe",
    # Minador (3)
    "Tengo galerias hoja en las hojas",
    "Veo minas hoja blancas",
    "Sospecho minador de la hoja",
    # Nematodos (3)
    "Tengo raices nudosas y enanismo",
    "Hay amarillamiento general en las plantas",
    "Sospecho nematodos en el suelo",
    # Deficiencias (5)
    "Hojas amarillas en crecimiento",
    "Hojas purpuras en las plantas",
    "Borde hoja amarillo en llenado de grano",
    "Clorosis intervenal en hojas viejas",
    "Hojas pequenas y brotes arrugados",
]

FASES = [
    "Estamos en floracion",
    "Mi cafe esta en llenado de grano",
    "La planta esta en maduracion",
    "Esta en fase de crecimiento vegetativo",
    "Estamos en epoca de floracion",
    "Se acerca la cosecha",
    "Ya empezo el llenado de grano",
    "El cafe esta en produccion",
]

CLIMA = [
    "Como esta el clima hoy?",
    "Consultar el clima de mi zona",
    "Hay riesgo de lluvia fuerte?",
    "Esta lloviendo en mi departamento?",
    "Cual es la humedad relativa actual?",
    "Que temperatura hace en mi zona?",
    "Llueve mucho esta semana?",
    "Necesito sincronizar el clima",
]

OPTIMIZACION = [
    "Optimizar para 1 manzana",
    "Optimizar para 2 manzanas",
    "Plan de fertilizacion para 3 manzanas",
    "Cuanto debo aplicar de fertilizante?",
    "Calcular dosis de nitrogeno",
    "Optimizar riego y fertilizacion",
    "Necesito un plan bioeconomico",
    "Que dosis de fungicida uso?",
]

PRECIOS = [
    "Cual es el precio del cafe hoy?",
    "A cuanto esta el quintal de cafe?",
    "Consultar precio del cafe",
    "Necesito el tipo de cambio",
    "Precio de la urea",
    "Precio del KCl",
    "Cuanto cuesta el fungicida?",
    "Actualizar precios",
]

REPORTES = [
    "Generar reporte PDF",
    "Necesito el reporte tecnico",
    "Descargar el reporte",
    "Quiero un PDF de la sesion",
    "Generar el documento tecnico",
]

IMAGENES = [
    "Quiero analizar una hoja",
    "Analizar una foto de hoja",
    "Voy a subir una imagen",
    "Como analizo una foto?",
    "Subir imagen para diagnostico",
]

AYUDA = [
    "Ayuda",
    "Que puedes hacer?",
    "Mostrar funciones",
    "Como funciona el asistente?",
    "Que consultas puedo hacer?",
    "Cancelar operacion",
    "Reiniciar la conversacion",
]

# Mapa sintoma -> clase CNN (para cruce imagen/sintoma)
SINTOMA_A_CLASE = {
    "manchas_naranjas":   "Roya",
    "polvo_amarillo":     "Roya",
    "pustulas":           "Roya",
    "manchas_negras":     "Antracnosis",
    "lesiones_hundidas":  "Antracnosis",
    "muerte_ramas":       "Antracnosis",
    "hojas_amarillas":    "Deficiencia_Nitrogeno",
    "clorosis_uniforme":  "Deficiencia_Nitrogeno",
    "borde_hojas_amarillo":"Deficiencia_Nitrogeno",
    "necrosis_marginal":  "Deficiencia_Nitrogeno",
    "manchas_circulares": "Antracnosis",
    "borde_cafe":         "Antracnosis",
    "centro_gris":        "Antracnosis",
}


# ============================================================
# Funciones de seleccion
# ============================================================
def _mezclar(*listas):
    pool = []
    for l in listas:
        pool.extend(l)
    random.shuffle(pool)
    return pool


def sugerencias_para_contexto(ctx, n=4, excluir_ultimas=None):
    """
    Devuelve n sugerencias contextuales segun el estado del bot.
    - Si hay imagen: prioriza 2 sobre la clase detectada + 2 generales
    - Si hay riesgo alto de roya: prioriza fungicida/optimizar
    - Si hay fase fenologica: prioriza deficiencias
    - Si no hay contexto: mezcla general
    """
    excluir_ultimas = excluir_ultimas or set()
    ctx = ctx or {}

    pool = []
    imagenes = ctx.get("imagenes_analizadas") or []
    riesgo = ctx.get("riesgo") or {}
    sintoma = ctx.get("sintoma_observado", "")
    fase = ctx.get("fase_fenologica", "")

    # --- Contexto 1: imagen reciente ---
    if imagenes:
        ultima = imagenes[-1]
        clase = ultima.get("clase", "Sana")
        if clase == "Roya":
            pool.extend([
                "Aplicar fungicida para roya",
                "Ver plan de riego y fertilizacion",
                "Consultar precio del fungicida",
                "Tomar nueva foto para confirmar",
            ])
        elif clase == "Antracnosis":
            pool.extend([
                "Que fungicida uso para antracnosis?",
                "Ver plan bioeconomico",
                "Revisar otra hoja",
                "Consultar clima",
            ])
        elif clase == "Deficiencia_Nitrogeno":
            pool.extend([
                "Optimizar fertilizacion con nitrogeno",
                "Consultar precio de urea",
                "Ver plan de fertilizacion",
                "Revisar otra hoja",
            ])
        else:  # Sana
            pool.extend([
                "Tomar otra foto para verificar",
                "Consultar clima de mi zona",
                "Ver plan de riego preventivo",
                "Revisar si hay sintomas en campo",
            ])

    # --- Contexto 2: riesgo bayesiano alto ---
    if riesgo.get("riesgo_global", 0) > 0.5:
        pool.extend([
            "Optimizar plan con alto riesgo",
            "Que fungicida aplicar con este riesgo?",
            "Ver recomendaciones para roya",
        ])

    # --- Contexto 3: sintoma textual ---
    if sintoma:
        pool.extend([
            "Confirmar diagnostico con foto",
            "Optimizar tratamiento",
            "Buscar recomendaciones",
        ])

    # --- Contexto 4: fase fenologica ---
    if fase == "llenado_grano":
        pool.extend([
            "Deficiencia de potasio en llenado",
            "Optimizar fertilizacion para produccion",
        ])
    elif fase == "floracion":
        pool.extend([
            "Optimizar riego en floracion",
            "Ver plan de fertilizacion",
        ])

    # --- Fallback / complemento ---
    pool.extend(_mezclar(
        SINTOMAS[:20], FASES[:4], CLIMA[:5],
        OPTIMIZACION[:5], PRECIOS[:4], REPORTES, AYUDA[:3],
    ))

    # Quitar repetidas y excluidas
    vistas = set()
    resultado = []
    for s in pool:
        if s in vistas or s in excluir_ultimas:
            continue
        vistas.add(s)
        resultado.append(s)
        if len(resultado) >= n:
            break
    return resultado


def sugerencias_iniciales(nivel="simple", n=4):
    """Sugerencias iniciales segun el nivel de detalle del perfil."""
    if nivel == "simple":
        return [
            "Tengo manchas naranjas en las hojas",
            "Como esta el clima?",
            "Optimizar para 1 manzana",
            "Generar reporte PDF",
        ][:n]
    elif nivel == "tecnico":
        return [
            "Sospecho roya, mostrar probabilidades",
            "Analizar imagen de hoja",
            "Optimizar plan bioeconomico",
            "Generar reporte PDF",
        ][:n]
    else:  # gerencial
        return [
            "Consultar precio del cafe",
            "Optimizar para 5 manzanas",
            "Ver KPIs de la sesion",
            "Generar reporte PDF",
        ][:n]


def sugerencias_para_imagen(clase, n=4):
    """Sugerencias contextuales despues de clasificar una imagen."""
    base = {
        "Roya": [
            "Aplicar fungicida cuprico",
            "Ver riesgo de roya en mi zona",
            "Optimizar tratamiento",
            "Tomar otra foto",
        ],
        "Antracnosis": [
            "Podar ramas afectadas",
            "Aplicar benomil",
            "Consultar clima",
            "Revisar otra hoja",
        ],
        "Deficiencia_Nitrogeno": [
            "Aplicar urea 46%",
            "Optimizar fertilizacion",
            "Consultar precio de urea",
            "Revisar plan de riego",
        ],
        "Sana": [
            "Consultar clima de mi zona",
            "Optimizar plan preventivo",
            "Generar reporte PDF",
            "Revisar otra hoja",
        ],
    }
    return base.get(clase, base["Sana"])[:n]