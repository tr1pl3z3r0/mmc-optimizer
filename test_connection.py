"""
Valida que la conexión con PLECS funciona correctamente antes de optimizar.

Ejecutar:
    python test_connection.py

Pasos que verifica:
  1. Conexión XML-RPC a localhost:1080
  2. Lectura de parámetros a y b del modelo
  3. Simulación de prueba con los valores actuales
  4. Gráfica baseline de las dos señales
"""

import sys
import matplotlib.pyplot as plt
import numpy as np

from objective import TARGET_SIG1, TARGET_SIG2, BAND_PCT
from plecs_interface import get_model_params, run_simulation, PLECS_URL, MODEL_NAME


def main():
    print("=" * 55)
    print("  Test de conexión PLECS — MMC AC Port")
    print("=" * 55)
    print(f"  URL  : {PLECS_URL}")
    print(f"  Modelo: {MODEL_NAME}")
    print()

    # 1. Leer parámetros actuales
    print("[1/3] Leyendo parámetros del modelo...")
    try:
        params = get_model_params()
        print(f"      a = {params['a']}")
        print(f"      b = {params['b']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        print()
        print("  Checklist:")
        print("    - PLECS 5.2 abierto con el modelo cargado")
        print("    - Preferences > General > XML-RPC > Enable  (puerto 1080)")
        print("    - Ningún firewall bloqueando localhost:1080")
        sys.exit(1)

    # 2. Correr simulación de prueba
    print()
    print("[2/3] Corriendo simulación de prueba...")
    try:
        sim_data = run_simulation()
        time = sim_data["time"]
        sig1 = sim_data["sig1"]
        sig2 = sim_data["sig2"]
        print(f"      Simulación OK — {len(time)} puntos de tiempo")
        print(f"      sig1: min={sig1.min():.3f}  max={sig1.max():.3f}  final={sig1[-1]:.3f}  (objetivo: {TARGET_SIG1})")
        print(f"      sig2: min={sig2.min():.3f}  max={sig2.max():.3f}  final={sig2[-1]:.3f}  (objetivo: {TARGET_SIG2})")
    except Exception as e:
        print(f"  ERROR al simular: {e}")
        sys.exit(1)

    # 3. Gráfica baseline
    print()
    print("[3/3] Generando gráfica baseline...")
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    fig.suptitle(f"Baseline — a={params['a']}  b={params['b']}", fontsize=13)

    for ax, signal, target, label, color in [
        (axes[0], sig1, TARGET_SIG1, "SRF→RRF : 1", "steelblue"),
        (axes[1], sig2, TARGET_SIG2, "SRF→RRF : 2", "darkorange"),
    ]:
        band_lo = target * (1 - BAND_PCT)
        band_hi = target * (1 + BAND_PCT)
        ax.plot(time, signal, color=color, linewidth=1.5, label=label)
        ax.axhline(target, color="black", linestyle="--", linewidth=1, label=f"Objetivo = {target}")
        ax.axhline(band_hi, color="gray", linestyle=":", linewidth=1)
        ax.axhline(band_lo, color="gray", linestyle=":", linewidth=1)
        ax.fill_between(time, band_lo, band_hi, alpha=0.08, color="green", label="Banda ±5%")
        ax.set_ylabel(label)
        ax.legend(fontsize=8, loc="upper right")
        ax.grid(True, alpha=0.3)

    axes[1].set_xlabel("Tiempo [s]")
    plt.tight_layout()
    plt.show()

    print()
    print("  Test completado. El pipeline está listo para optimizar.")
    print("  Ejecuta:  python optimize.py")


if __name__ == "__main__":
    main()
