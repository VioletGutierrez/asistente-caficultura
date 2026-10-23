\# Asistente Inteligente para la Caficultura Nicaraguense



Sistema experto hibrido que integra reglas de produccion, redes bayesianas,

vision computacional (CNN), algoritmos geneticos y generacion de reportes PDF

para apoyar la toma de decisiones agronomicas en la caficultura de Nicaragua.



\## Requisitos del sistema



\- Windows 10 u 11 (64 bits)

\- Python 3.11.x (con "Add to PATH" activado)

\- Microsoft Visual C++ Redistributable 2015-2026 (x64)

\- Ollama (para el Oraculo LLM local)



\## Instalacion



```cmd

cd /d C:\\Users\\si\_vgutierrez.MANAGUA\\Downloads\\OCT\\asistente\_caficultura

py -3.11 -m venv .venv

call .venv\\Scripts\\activate.bat

pip install -r requirements.txt


---


## Estado del proyecto

- Tests: **25/25 PASSED** (~42s)
- Modulos: 14 implementados y probados
- Endpoints API: 12 expuestos via FastAPI
- Interfaces: consola (main.py), Streamlit (app_streamlit.py), API REST

## Arquitectura hibrida

| Componente | Tecnologia | Referencia |
|---|---|---|
| Motor de reglas | Forward chaining + AND/OR 
| Red Bayesiana | pgmpy + Variable Elimination (7 nodos) 
| Vision CNN | MobileNetV3 + HSV fallback 
| Algoritmo Genetico | BLX-alpha + mutacion gaussiana 
| Modelo agronomico | Mitscherlich-Baule 
| Oraculo LLM | Ollama (llama3.2:3b) 
| Reportes | ReportLab (PDF) 
| Persistencia | SQLite (4 tablas) 
| KPIs + CSAT | JSONL 


## Requisitos

- Python 3.11+
- Ollama (opcional, para Oraculo LLM): `ollama pull llama3.2:3b`
- Ver `requirements.txt` para dependencias Python

## Instalacion

```bash
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt