# ============================================================
# modulos/llm_fallback.py
# Oraculo agronomico de respaldo (Ollama local o Gemini)
# Referencia: IA.docx §4.7
#
# Prioridad:
#   1. OLLAMA si esta corriendo (offline, sin costo)
#   2. GEMINI si GEMINI_API_KEY en el entorno
#   3. Mensaje de "no configurado"
# ============================================================
import os


SYSTEM_PROMPT = (
    "Eres un experto agronomo especialista en caficultura de Nicaragua. "
    "Responde de forma tecnica, clara y prudente. "
    "Expresa costos en Cordobas (C$) y superficies en manzanas. "
    "Si la patologia no es clara, recomienda analisis de laboratorio o "
    "verificacion por un extensionista del INTA."
)


class OraculoAgronomoLLM:
    """Fallback generativo con Ollama o Gemini (via env vars)."""

    def __init__(self, modelo_ollama="llama3.2:3b"):
        self.modelo_ollama = modelo_ollama
        # NUNCA se pasa la key como parametro: se lee del entorno
        self.api_key_gemini = os.getenv("GEMINI_API_KEY", "").strip()
        self._ollama_ok = self._probar_ollama()

    # --------------------------------------------------------
    def _probar_ollama(self):
        try:
            import ollama
            ollama.list()
            return True
        except Exception:
            return False

    def _esta_corriendo(self):
        return self._ollama_ok or bool(self.api_key_gemini)

    # --------------------------------------------------------
    def consultar_oraculo(self, consulta, contexto_finca=""):
        if not self._esta_corriendo():
            return ("Servicio generativo no configurado. "
                    "Instale Ollama (ollama serve) o defina GEMINI_API_KEY. "
                    "Consulte al extensionista del INTA local.")

        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Contexto finca: {contexto_finca or 'Sin datos previos.'}\n"
            f"Consulta del productor: {consulta}"
        )

        # 1. Ollama
        if self._ollama_ok:
            try:
                import ollama
                r = ollama.chat(
                    model=self.modelo_ollama,
                    messages=[{"role": "user", "content": prompt}],
                )
                return r["message"]["content"]
            except Exception as e:
                print(f"[llm] Ollama fallo: {e}")

        # 2. Gemini
        if self.api_key_gemini:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key_gemini)
                modelo = genai.GenerativeModel("gemini-1.5-flash")
                resp = modelo.generate_content(prompt)
                return resp.text
            except Exception as e:
                return f"Error al procesar la consulta generativa: {e}"

        return ("No se pudo contactar al Oraculo (ni Ollama ni Gemini). "
                "Escriba 'ayuda' para ver funciones disponibles.")