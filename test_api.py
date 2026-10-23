import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY", "").strip()
print(f"Clave detectada: {api_key[:10]}...\n")

try:
    from google import genai
    client = genai.Client(api_key=api_key)
    
    print("--- MODELOS DISPONIBLES EN TU CUENTA ---")
    modelos_disponibles = []
    for m in client.models.list():
        print(f"- {m.name}")
        if "gemini" in m.name and "flash" in m.name:
            modelos_disponibles.append(m.name)
            
    print("\n--- PRUEBA DE CONEXION ---")
    if not modelos_disponibles:
        print("ERROR: No se encontraron modelos 'gemini' con 'flash' disponibles.")
    else:
        # Usamos el primer modelo flash que encontremos
        modelo_prueba = modelos_disponibles[0]
        print(f"Probando con el modelo: {modelo_prueba}")
        
        response = client.models.generate_content(
            model=modelo_prueba,
            contents='Di hola'
        )
        print("CONEXION EXITOSA. Respuesta:", response.text)
        
except Exception as e:
    print("ERROR DETALLADO:", str(e))