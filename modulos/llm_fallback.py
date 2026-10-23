# ============================================================
# modulos/llm_fallback.py
# Agente Experto con fallback de modelos
# ============================================================
import os
import json
import time
from dotenv import load_dotenv

load_dotenv()

PROMPTS_PERFIL = {
    "pequeno_productor": "Eres un técnico agrónomo amigable. Usa un lenguaje muy sencillo y soluciones prácticas.",
    "extensionista_tecnico": "Eres un Ingeniero Agrónomo especialista en fitopatología. Usa terminología científica rigurosa.",
    "administrador_finca": "Eres un asesor agroeconómico. Enfoca tus respuestas en la rentabilidad y costos en Córdobas."
}

SYSTEM_PROMPT_BASE = "Tus respuestas deben ser claras y profesionales. NUNCA digas 'No sé'."

PROMPT_VISION = """
Eres un fitopatólogo experto en café. Analiza la imagen de esta hoja y clasifícala en UNA de las siguientes categorías exactas:
- Sana
- Roya
- Antracnosis
- Ojo_de_gallo
- Mancha_de_hierro
- Deficiencia_Nitrogeno

Devuelve ÚNICAMENTE un objeto JSON con esta estructura exacta, sin texto adicional ni bloques de código:
{"clase": "Roya", "confianza": 0.95, "justificacion": "Explicación breve de los síntomas visuales."}
"""

class OraculoAgronomoLLM:
    def __init__(self, modelo_ollama="llama3.2:3b", perfil="pequeno_productor"):
        self.modelo_ollama = modelo_ollama
        self.perfil = perfil
        self.api_key_gemini = os.getenv("GEMINI_API_KEY", "").strip()
        
        self.gemini_client = None
        self.error_gemini = ""
        
        if self.api_key_gemini:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=self.api_key_gemini)
            except Exception as e:
                self.error_gemini = f"Error al iniciar cliente: {str(e)}"
        else:
            self.error_gemini = "No se encontró GEMINI_API_KEY en el archivo .env"

        self._ollama_ok = self._probar_ollama()
        
        # LISTA DE MODELOS EN ORDEN DE PREFERENCIA (El 3.8 es el más nuevo, el 2.5 y 2.0 son estables)
        self.modelos_gemini = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-3.8-flash"]

    def set_perfil(self, perfil): self.perfil = perfil

    def _get_system_prompt(self):
        return f"{SYSTEM_PROMPT_BASE}\n\nROL: {PROMPTS_PERFIL.get(self.perfil, PROMPTS_PERFIL['pequeno_productor'])}"

    def _probar_ollama(self):
        try:
            import ollama
            ollama.list()
            return True
        except Exception:
            return False

    def _esta_corriendo(self):
        return bool(self.gemini_client) or self._ollama_ok

    def _generar_con_gemini(self, contents, system_prompt):
        """Intenta con múltiples modelos de Gemini hasta que uno funcione."""
        if not self.gemini_client:
            raise Exception("Cliente Gemini no inicializado.")
        
        from google.genai import types
        ultimo_error = None
        
        for modelo in self.modelos_gemini:
            try:
                response = self.gemini_client.models.generate_content(
                    model=modelo, contents=contents,
                    config=types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.4)
                )
                return response.text
            except Exception as e:
                ultimo_error = str(e)
                # Si es error 503 (saturado) o 404 (no encontrado), intenta el siguiente modelo
                if "503" in ultimo_error or "404" in ultimo_error or "UNAVAILABLE" in ultimo_error:
                    continue 
                else:
                    # Si es otro error (ej. 403 API deshabilitada), se detiene
                    raise Exception(ultimo_error)
        
        # Si llegamos aquí, todos los modelos fallaron
        raise Exception(f"Todos los modelos saturados. Último error: {ultimo_error}")

    def consultar_oraculo(self, consulta, contexto_finca="", historial=None):
        if not self._esta_corriendo():
            return "El servicio de IA no está disponible."

        contexto_completo = f"CONTEXTO ACTUAL: {contexto_finca}\n\nPREGUNTA: {consulta}"
        historial = historial or []
        system_prompt = self._get_system_prompt()

        if self.gemini_client:
            try:
                from google.genai import types
                contents = []
                for msg in historial[-6:]:
                    rol = "user" if msg["role"] == "user" else "model"
                    contents.append(types.Content(role=rol, parts=[types.Part(text=msg["content"])]))
                contents.append(types.Content(role="user", parts=[types.Part(text=contexto_completo)]))

                return self._generar_con_gemini(contents, system_prompt)
            except Exception as e:
                print(f"Error con Gemini: {e}") # Solo imprime en consola, no molesta al usuario

        if self._ollama_ok:
            try:
                import ollama
                mensajes = [{"role": "system", "content": system_prompt}]
                for msg in historial[-6:]:
                    mensajes.append({"role": msg["role"], "content": msg["content"]})
                mensajes.append({"role": "user", "content": contexto_completo})
                r = ollama.chat(model=self.modelo_ollama, messages=mensajes, options={"temperature": 0.4})
                return r["message"]["content"]
            except Exception as e:
                return f"Error de Ollama: {e}"
        return "No se pudo obtener respuesta."

    def analizar_imagen_con_ia(self, ruta_imagen):
        if not self.gemini_client:
            return {"error": self.error_gemini}

        try:
            from PIL import Image
            from google.genai import types
            
            img = Image.open(ruta_imagen)
            
            # Intentamos generar el contenido usando la lista de modelos
            texto_respuesta = self._generar_con_gemini([PROMPT_VISION, img], "Eres un fitopatólogo experto.")
            
            texto = texto_respuesta.strip()
            if texto.startswith("```json"): texto = texto[7:-3]
            elif texto.startswith("```"): texto = texto[3:-3]
                
            data = json.loads(texto)
            return {
                "clase": data.get("clase", "Sana").replace(" ", "_"),
                "confianza": float(data.get("confianza", 0.5)),
                "justificacion": data.get("justificacion", ""),
                "modo": "Gemini Vision AI"
            }
        except Exception as e:
            # Si TODOS los modelos fallaron o hubo un 403, devolvemos un error simplificado
            error_msg = str(e)
            if "403" in error_msg:
                return {"error": "API de Gemini deshabilitada. Active el servicio en Google Cloud."}
            elif "503" in error_msg:
                return {"error": "Servidores de Google saturados. Intente de nuevo."}
            else:
                return {"error": f"Fallo en Vision: {error_msg[:50]}..."}