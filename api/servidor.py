# ============================================================
# api/servidor.py
# API REST con FastAPI - expone todos los modulos del sistema
# Ejecutar: uvicorn api.servidor:app --reload
# ============================================================
import os
import base64
import shutil
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel

from modulos.chatbot            import ChatbotCaficultura
from modulos.vision_cnn         import ClasificadorVisionCNN
from modulos.precios            import leer_precios_actuales, actualizar_precios
from modulos.llm_fallback       import OraculoAgronomoLLM
from modulos.kpis               import calcular_kpis
from modulos.clima_api          import ModuloClima
from modulos.algoritmo_genetico import OptimizacionGenetica
from modulos.reporte_pdf        import generar_reporte
from analisis_sensibilidad      import ejecutar_analisis


app = FastAPI(
    title="Asistente Caficultura API",
    description="API REST del Asistente Inteligente para la Caficultura Nicaraguense",
    version="1.0.0",
)

# Instancias unicas compartidas
bot   = ChatbotCaficultura()
cnn   = ClasificadorVisionCNN()
llm   = OraculoAgronomoLLM()
clima = ModuloClima()
ag    = OptimizacionGenetica(generaciones=40, tam_poblacion=60)


# ------------------------------------------------------------
# Modelos de entrada
# ------------------------------------------------------------
class ConsultaChat(BaseModel):
    texto: str

class ConsultaLLM(BaseModel):
    texto: str
    contexto_finca: str = ""

class OptimizarIn(BaseModel):
    superficie_mz: float = 1.0
    riesgo_roya_pct: float = 60.0

class ReporteIn(BaseModel):
    sesion_id: str = "API"
    zona: str = "Matagalpa"
    superficie_manzanas: float = 1.0
    clima: dict = {}
    diagnosticos: list = []
    riesgo: dict = {}
    optimizacion: dict = {}


# ------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------
@app.get("/salud")
def salud():
    return {"estado": "ok", "servicio": "Asistente Caficultura API"}


@app.get("/health")
def health():
    """Alias estandar de salud."""
    return {"status": "ok", "servicio": "Asistente Caficultura API"}


@app.post("/chat")
def chat(c: ConsultaChat):
    if not c.texto.strip():
        raise HTTPException(status_code=400, detail="Texto vacio")
    respuesta, intent = bot.responder(c.texto)
    return {"intent": intent, "respuesta": respuesta}


@app.post("/imagen")
async def subir_imagen(archivo: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        shutil.copyfileobj(archivo.file, tmp)
        ruta = tmp.name
    try:
        resultado = cnn.clasificar_imagen(ruta)
    finally:
        if os.path.exists(ruta):
            os.unlink(ruta)
    return resultado


@app.post("/oraculo")
def endpoint_oraculo(c: ConsultaLLM):
    if not llm._esta_corriendo():
        raise HTTPException(status_code=503, detail="Ollama no disponible")
    return {"respuesta": llm.consultar_oraculo(c.texto, c.contexto_finca)}


@app.get("/precios")
def get_precios():
    return leer_precios_actuales()


@app.post("/precios/actualizar")
def forzar_actualizacion():
    return actualizar_precios()


@app.get("/clima")
def get_clima():
    """Clima actual (Open-Meteo o fallback local)."""
    try:
        return clima.obtener_datos_actuales()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/optimizar")
def post_optimizar(inp: OptimizarIn):
    """Plan de fertilizacion y riego optimizado por AG."""
    try:
        return ag.optimizar(
            superficie_mz=inp.superficie_mz,
            riesgo_roya_pct=inp.riesgo_roya_pct,
            verbose=False,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reporte")
def post_reporte(inp: ReporteIn):
    """Genera PDF y lo devuelve codificado en base64."""
    try:
        try:
            datos = inp.model_dump()
        except AttributeError:
            datos = inp.dict()
        nombre = f"reporte_{datos['sesion_id']}.pdf"
        ruta = generar_reporte(datos, nombre=nombre)
        with open(ruta, "rb") as f:
            contenido = base64.b64encode(f.read()).decode("utf-8")
        return {
            "archivo":    os.path.basename(ruta),
            "pdf_base64": contenido,
            "bytes":      len(contenido),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analisis/sensibilidad")
def get_sensibilidad():
    """Analisis de sensibilidad con los 3 escenarios climaticos (A, B, C)."""
    try:
        return ejecutar_analisis()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/kpis")
def get_kpis():
    return calcular_kpis()


# ------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)