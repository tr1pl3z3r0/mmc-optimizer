"""
Optimización bayesiana de a,b (AC Port) y c,d,e,f (DC Port) del MMC.

Semilla analítica con polos de lazo cerrado verificados en semiplano izquierdo.
Escribí Q + Enter para detener tras la evaluación actual.

Ejecutar:
    python optimize.py
"""

import csv
import os
import sys
import threading
import time as _time
from datetime import datetime

import numpy as np
from skopt import gp_minimize
from skopt.space import Real
from skopt.utils import use_named_args

from plecs_interface import set_params, run_simulation
from objective import compute_error

# ── Parada manual ─────────────────────────────────────────────────────────────
_stop_requested = threading.Event()

def _listen_for_stop():
    print("  [!] Escribí Q + Enter para detener la optimización.", flush=True)
    for line in sys.stdin:
        if line.strip().lower() == "q":
            _stop_requested.set()
            print("\n  [!] Parada solicitada — terminando tras la evaluación actual...", flush=True)
            break

threading.Thread(target=_listen_for_stop, daemon=True).start()

# ── Puntos de diseño analíticos (semilla) ────────────────────────────────────
# Calculados en design_points.py — polos LC verificados en semiplano izquierdo
X0 = [1.8, 400.0, -9000.0, -60000.0, 0.9, 60.0]

# ── Espacio de búsqueda — centrado en la semilla, ±orden de magnitud ─────────
SPACE = [
    Real(0.01,      200.0,   name="a"),   # Kp AC — rango amplio por ganancia reducida de planta
    Real(10.0,      50000.0, name="b"),   # Ki AC
    Real(-50000.0, -100.0,   name="c"),   # Kp DC ext — negativo (pos_fb)
    Real(-500000.0,-1000.0,  name="d"),   # Ki DC ext — negativo (pos_fb)
    Real(0.01,      5.0,     name="e"),   # Kp DC int — positivo (neg_fb clásico)
    Real(1.0,       500.0,   name="f"),   # Ki DC int — positivo (neg_fb clásico)
]

PARAM_NAMES = ["a", "b", "c", "d", "e", "f"]

# ── Criterios ─────────────────────────────────────────────────────────────────
N_CALLS        = 60   # evaluaciones totales (incluye n_initial_points)
N_INITIAL      = 10   # exploraciones aleatorias antes de usar el modelo GP
MIN_ERROR      = 0.05

# ── Log ───────────────────────────────────────────────────────────────────────
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
LOG_FILE    = os.path.join(RESULTS_DIR, "log.csv")
os.makedirs(RESULTS_DIR, exist_ok=True)

_eval_count  = 0
_best_error  = np.inf
_best_params = None

_LOG_HEADER = [
    "eval", "a", "b", "c", "d", "e", "f",
    "rmse1", "rmse2", "rmse_v0s",
    "t_set1", "t_set2", "t_set_v0s",
    "in1", "in2", "in_v0s",
    "ss1", "ss2", "ss_v0s",
    "total_error", "timestamp",
]


def _init_log():
    with open(LOG_FILE, "w", newline="") as f:
        csv.writer(f).writerow(_LOG_HEADER)


def _append_log(row: dict):
    with open(LOG_FILE, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=_LOG_HEADER).writerow(row)


def _poles_stable(Kp, Ki, plant_num, plant_den, pos_fb=True):
    """Verifica que los polos de lazo cerrado estén en el semiplano izquierdo.
    pos_fb=True  → den = s·plant_den - C·plant_num  (realim. positiva efectiva)
    pos_fb=False → den = s·plant_den + C·plant_num  (realim. negativa clásica)
    """
    s_pd  = np.convolve([1, 0], plant_den)
    C_num = np.polymul([Kp, Ki], plant_num)
    n1, n2 = len(s_pd), len(C_num)
    sz = max(n1, n2)
    p1 = np.concatenate([np.zeros(sz - n1), s_pd])
    p2 = np.concatenate([np.zeros(sz - n2), C_num])
    poles = np.roots(p1 - p2 if pos_fb else p1 + p2)
    return all(p.real < 1e-6 for p in poles)


def _is_stable_point(a, b, c, d, e, f):
    Ltot, R, n_mmc, C_cap, Vc = 4.5e-3, 1.0, 3, 1.0, 150.0  # Ltot = L + 2*Ll
    # AC: realimentación negativa clásica, controlador positivo
    ok_ac  = _poles_stable(a, b, [1.0], [Ltot, R],                  pos_fb=False)
    # DC externo: realimentación positiva (controlador negativo, planta negativa)
    ok_dce = _poles_stable(c, d, [1.0], [n_mmc * C_cap * Vc, 0.0], pos_fb=True)
    # DC interno: realimentación negativa clásica, controlador positivo
    ok_dci = _poles_stable(e, f, [1.0], [Ltot, 0.0],                pos_fb=False)
    return ok_ac and ok_dce and ok_dci


@use_named_args(SPACE)
def objective_fn(a, b, c, d, e, f):
    global _eval_count, _best_error, _best_params

    if _stop_requested.is_set():
        return 1e6

    _eval_count += 1

    # Rechazar puntos inestables sin simular
    if not _is_stable_point(a, b, c, d, e, f):
        print(f"  [eval {_eval_count}] INESTABLE — descartado", flush=True)
        return 1e6

    params = {"a": a, "b": b, "c": c, "d": d, "e": e, "f": f}

    try:
        set_params(params)
        sim_data = run_simulation()
        err = compute_error(sim_data)
    except Exception as exc:
        print(f"  [eval {_eval_count}] ERROR: {exc}", flush=True)
        return 1e6

    total = err["total"]

    row = {
        "eval": _eval_count,
        **{nm: round(v, 5) for nm, v in params.items()},
        "rmse1":     round(err["rmse1"], 4),
        "rmse2":     round(err["rmse2"], 4),
        "rmse_v0s":  round(err["rmse_v0s"], 4),
        "t_set1":    round(err["t_settling1"], 4),
        "t_set2":    round(err["t_settling2"], 4),
        "t_set_v0s": round(err["t_settling_v0s"], 4),
        "in1":       err["in_band1"],
        "in2":       err["in_band2"],
        "in_v0s":    err["in_band_v0s"],
        "ss1":       round(err["ss_error1"], 4),
        "ss2":       round(err["ss_error2"], 4),
        "ss_v0s":    round(err["ss_error_v0s"], 4),
        "total_error": round(total, 8),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    _append_log(row)

    if total < _best_error:
        _best_error  = total
        _best_params = params.copy()
        print(f"  [eval {_eval_count}] MEJOR  a={a:.3f} b={b:.1f} "
              f"c={c:.1f} d={d:.1f} e={e:.4f} f={f:.3f}  → error={total:.5f}", flush=True)
    else:
        print(f"  [eval {_eval_count}] error={total:.5f}", flush=True)

    if _best_error < MIN_ERROR:
        print(f"\n  [!] Umbral {MIN_ERROR} alcanzado. Deteniendo.", flush=True)
        _stop_requested.set()

    return total


def main():
    print("=" * 65)
    print("  Optimización Bayesiana MMC — AC (a,b) + DC (c,d,e,f)")
    print("=" * 65)
    print(f"  N_calls={N_CALLS}  N_initial={N_INITIAL}  Umbral={MIN_ERROR}")
    print(f"  Semilla: {X0}")
    print()

    _init_log()
    t0 = _time.time()

    result = gp_minimize(
        objective_fn,
        dimensions=SPACE,
        n_calls=N_CALLS,
        n_initial_points=N_INITIAL,
        x0=X0,           # semilla analítica como primer punto
        acq_func="EI",   # Expected Improvement
        noise=1e-10,
        random_state=42,
        callback=[lambda r: _stop_requested.is_set()],  # para si se pidió stop
    )

    elapsed = _time.time() - t0
    opt = {n: v for n, v in zip(PARAM_NAMES, result.x)}

    print()
    print("=" * 65)
    print("  OPTIMIZACIÓN FINALIZADA")
    print("=" * 65)
    for nm, v in opt.items():
        print(f"  {nm} = {v:.6f}")
    print(f"  Error total = {result.fun:.6f}")
    print(f"  Evaluaciones: {_eval_count}   Tiempo: {elapsed:.1f}s")
    print()

    print("  Corriendo simulación final con parámetros óptimos...")
    set_params(opt)
    sim_data = run_simulation()
    err = compute_error(sim_data, verbose=True)

    opt_file = os.path.join(RESULTS_DIR, "optimal_params.csv")
    with open(opt_file, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(list(opt.keys()) + ["total_error"])
        w.writerow([round(v, 6) for v in opt.values()] + [round(result.fun, 8)])
    print(f"\n  Parámetros guardados en: {opt_file}")


if __name__ == "__main__":
    main()
