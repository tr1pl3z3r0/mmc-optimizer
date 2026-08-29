"""
Revisión manual de una corrida con parámetros específicos.

Uso desde terminal:
    python run_iteration.py --a 1000 --b 400

O importado desde optimize.py:
    import run_iteration; run_iteration.run(a=1000, b=400)
"""

import argparse
import os

import matplotlib.pyplot as plt
import numpy as np

from objective import TARGET_SIG1, TARGET_SIG2, BAND_PCT, _settling_error, compute_error
from plecs_interface import set_params, run_simulation

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


def run(a: float, b: float, save_fig: bool = True, show_fig: bool = True):
    print(f"\nCorriendo simulación con a={a}  b={b} ...")
    set_params({"a": a, "b": b})
    sim_data = run_simulation()
    err = compute_error(sim_data, verbose=True)

    time = sim_data["time"]
    sig1 = sim_data["sig1"]
    sig2 = sim_data["sig2"]

    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    fig.suptitle(f"MMC — AC Port   a={a:.2f}   b={b:.2f}", fontsize=13)

    _plot_signal(axes[0], time, sig1, TARGET_SIG1, err["t_settling1"],
                 label="SRF→RRF : 1", color="steelblue")
    _plot_signal(axes[1], time, sig2, TARGET_SIG2, err["t_settling2"],
                 label="SRF→RRF : 2", color="darkorange")

    axes[1].set_xlabel("Tiempo [s]")
    plt.tight_layout()

    if save_fig:
        fig_path = os.path.join(RESULTS_DIR, f"result_a{a:.0f}_b{b:.0f}.png")
        plt.savefig(fig_path, dpi=150)
        print(f"Gráfica guardada en: {fig_path}")

    if show_fig:
        plt.show()

    return err


def _plot_signal(ax, time, signal, target, t_settling, label, color):
    band_lo = target * (1 - BAND_PCT)
    band_hi = target * (1 + BAND_PCT)

    ax.plot(time, signal, color=color, linewidth=1.5, label=label)
    ax.axhline(target, color="black", linestyle="--", linewidth=1, label=f"Objetivo = {target}")
    ax.axhline(band_hi, color="gray", linestyle=":", linewidth=1, label=f"+5% = {band_hi:.2f}")
    ax.axhline(band_lo, color="gray", linestyle=":", linewidth=1, label=f"−5% = {band_lo:.2f}")
    ax.fill_between(time, band_lo, band_hi, alpha=0.08, color="green")

    if t_settling > 0:
        ax.axvline(t_settling, color="red", linestyle="-.", linewidth=1.2,
                   label=f"t_settling = {t_settling:.3f} s")

    # Overshoot
    peak = np.max(signal) if np.max(signal) > target else np.min(signal)
    if abs(peak - target) / target > BAND_PCT:
        idx_peak = np.argmax(np.abs(signal - target))
        ax.annotate(
            f"OS={((peak - target) / target * 100):.1f}%",
            xy=(time[idx_peak], signal[idx_peak]),
            xytext=(time[idx_peak], signal[idx_peak] + 0.05 * target),
            arrowprops=dict(arrowstyle="->", color="purple"),
            color="purple", fontsize=9,
        )

    ax.set_ylabel(label)
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Correr una iteración manual del MMC")
    parser.add_argument("--a", type=float, default=1000.0, help="Ganancia a (default: 1000)")
    parser.add_argument("--b", type=float, default=400.0, help="Ganancia b (default: 400)")
    parser.add_argument("--no-show", action="store_true", help="No mostrar gráfica en pantalla")
    args = parser.parse_args()

    run(a=args.a, b=args.b, show_fig=not args.no_show)
