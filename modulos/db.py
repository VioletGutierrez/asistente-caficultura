# ============================================================
# modulos/db.py
# Persistencia SQLite de sesiones, mensajes y resultados
# Referencia: IA.docx Pag. 59 (recomendacion de persistencia)
# ============================================================
import sqlite3
from datetime import datetime
from config import RUTA_BD


# ------------------------------------------------------------
def iniciar_db():
    """Crea las tablas si no existen."""
    con = sqlite3.connect(RUTA_BD)
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sesiones (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            sesion_uuid TEXT UNIQUE,
            perfil      TEXT,
            zona        TEXT,
            inicio      TEXT
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mensajes (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            sesion_id INTEGER,
            rol       TEXT,
            texto     TEXT,
            intent    TEXT,
            timestamp TEXT,
            FOREIGN KEY (sesion_id) REFERENCES sesiones(id)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS diagnosticos (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            sesion_id    INTEGER,
            regla_id     TEXT,
            diagnostico  TEXT,
            riesgo_roya  REAL,
            riesgo_antra REAL,
            riesgo_ojo   REAL,
            timestamp    TEXT,
            FOREIGN KEY (sesion_id) REFERENCES sesiones(id)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS optimizaciones (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            sesion_id         INTEGER,
            superficie_mz     REAL,
            riego_m3          REAL,
            N_kg              REAL,
            P_kg              REAL,
            K_kg              REAL,
            fungicida_L       REAL,
            rendimiento_qq_mz REAL,
            costo_nio         REAL,
            beneficio_nio     REAL,
            timestamp         TEXT,
            FOREIGN KEY (sesion_id) REFERENCES sesiones(id)
        );
    """)

    con.commit()
    con.close()


# ------------------------------------------------------------
def crear_sesion(sesion_uuid, perfil="pequeño_productor",
                 zona="Matagalpa"):
    con = sqlite3.connect(RUTA_BD)
    cur = con.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO sesiones (sesion_uuid, perfil, zona, inicio) "
        "VALUES (?, ?, ?, ?)",
        (sesion_uuid, perfil, zona, datetime.now().isoformat()),
    )
    cur.execute("SELECT id FROM sesiones WHERE sesion_uuid = ?",
                (sesion_uuid,))
    sid = cur.fetchone()[0]
    con.commit()
    con.close()
    return sid


# ------------------------------------------------------------
def guardar_mensaje(sesion_id, rol, texto, intent=None):
    con = sqlite3.connect(RUTA_BD)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO mensajes (sesion_id, rol, texto, intent, timestamp) "
        "VALUES (?, ?, ?, ?, ?)",
        (sesion_id, rol, texto, intent, datetime.now().isoformat()),
    )
    con.commit()
    con.close()


# ------------------------------------------------------------
def guardar_diagnostico(sesion_id, regla_id, diagnostico, riesgo):
    con = sqlite3.connect(RUTA_BD)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO diagnosticos "
        "(sesion_id, regla_id, diagnostico, riesgo_roya, "
        "riesgo_antra, riesgo_ojo, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            sesion_id, regla_id, diagnostico,
            riesgo.get("roya", 0.0),
            riesgo.get("antracnosis", 0.0),
            riesgo.get("ojo_gallo", 0.0),
            datetime.now().isoformat(),
        ),
    )
    con.commit()
    con.close()


# ------------------------------------------------------------
def guardar_optimizacion(sesion_id, res):
    con = sqlite3.connect(RUTA_BD)
    cur = con.cursor()
    d = res.get("dosis_por_mz", {})
    cur.execute(
        "INSERT INTO optimizaciones "
        "(sesion_id, superficie_mz, riego_m3, N_kg, P_kg, K_kg, "
        "fungicida_L, rendimiento_qq_mz, costo_nio, beneficio_nio, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            sesion_id,
            res.get("superficie_mz", 1.0),
            d.get("riego_m3", 0.0),
            d.get("N_kg", 0.0),
            d.get("P_kg", 0.0),
            d.get("K_kg", 0.0),
            d.get("fungicida_L", 0.0),
            res.get("rendimiento_qq_mz", 0.0),
            res.get("costo_total_nio", 0.0),
            res.get("beneficio_neto_nio", 0.0),
            datetime.now().isoformat(),
        ),
    )
    con.commit()
    con.close()


# ------------------------------------------------------------
def consultar_historial(limite=30):
    con = sqlite3.connect(RUTA_BD)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("""
        SELECT s.id, s.sesion_uuid, s.perfil, s.zona, s.inicio,
               COUNT(m.id) AS num_mensajes
        FROM sesiones s
        LEFT JOIN mensajes m ON m.sesion_id = s.id
        GROUP BY s.id
        ORDER BY s.id DESC
        LIMIT ?
    """, (limite,))
    filas = [dict(r) for r in cur.fetchall()]
    con.close()
    return filas


# ------------------------------------------------------------
def obtener_stats():
    con = sqlite3.connect(RUTA_BD)
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM sesiones")
    total_sesiones = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM mensajes")
    total_mensajes = cur.fetchone()[0] or 0
    cur.execute(
        "SELECT COUNT(*) FROM mensajes "
        "WHERE intent = 'Consultar_Oraculo_LLM_Fallback'"
    )
    total_fallbacks = cur.fetchone()[0] or 0
    con.close()

    tasa_fallback = (
        total_fallbacks / total_mensajes if total_mensajes else 0.0
    )
    return {
        "total_sesiones":  total_sesiones,
        "total_mensajes":  total_mensajes,
        "total_fallbacks": total_fallbacks,
        "tasa_fallback":   round(tasa_fallback, 4),
    }


# Inicializacion al importar
iniciar_db()


# ------------------------------------------------------------
if __name__ == "__main__":
    iniciar_db()
    print("Base de datos inicializada en:", RUTA_BD)
    sid = crear_sesion("demo-uuid-001", perfil="extensionista")
    guardar_mensaje(sid, "usuario", "Tengo manchas naranjas")
    guardar_mensaje(sid, "asistente", "Diagnostico: roya", intent="Consultar_Diagnostico")
    guardar_diagnostico(sid, "R001", "Roya", {"roya": 0.72, "antracnosis": 0.15, "ojo_gallo": 0.13})
    print("Estadisticas:", obtener_stats())
    print("Historial:", consultar_historial(5))