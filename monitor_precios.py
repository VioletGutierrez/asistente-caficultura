# ============================================================
# monitor_precios.py
# Actualiza precios de mercado cada 6 horas
# Ejecutar: python monitor_precios.py
# ============================================================
import time
import schedule
from datetime import datetime
from modulos.precios import actualizar_precios


def tarea():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
          "Actualizando indicadores de mercado...")
    p = actualizar_precios()
    print(f"  Precio del cafe: {p['precio_cafe_oro_qq_usd']} USD/qq")
    print(f"  Tipo de cambio:  {p['tipo_cambio_usd_nio']} NIO/USD")


# Programar
schedule.every(6).hours.do(tarea)


if __name__ == "__main__":
    print("Monitor de precios iniciado.")
    print("Se actualiza cada 6 horas. Presione Ctrl+C para salir.")

    # Ejecutar una vez al inicio
    tarea()

    while True:
        schedule.run_pending()
        time.sleep(60)