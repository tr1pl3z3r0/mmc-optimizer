"""
Script de diagnóstico — prueba puntos específicos y reporta V0Σ e Id/Iq.
Correr con: python diagnostico.py
"""
import time
from plecs_interface import set_params, run_simulation
from objective import compute_error

PUNTOS = [
    # Vc*=150 fijo, a=0.01, b=10 fijos, variando c y d
    ("DC_d_grande",   0.01, 10.0, 1000.0,    10000000.0,  0.9, 60.0),
    ("DC_d_enorme",   0.01, 10.0, 1000.0,   100000000.0,  0.9, 60.0),
    ("DC_cd_grandes", 0.01, 10.0, 100000.0,  10000000.0,  0.9, 60.0),
]

print("=" * 70)
print("  Diagnóstico MMC — pruebas sistemáticas")
print("=" * 70)

for label, a, b, c, d, e, f in PUNTOS:
    params = {"a": a, "b": b, "c": c, "d": d, "e": e, "f": f}
    print(f"\n[{label}]")
    print(f"  a={a} b={b} c={c} d={d} e={e} f={f}")
    try:
        set_params(params)
        sim_data = run_simulation()
        err = compute_error(sim_data)
        print(f"  V0Σ:  ss={err['ss_error_v0s']:.2f}V  rmse={err['rmse_v0s']:.2f}  in_band={err['in_band_v0s']}")
        print(f"  Id:   ss={err['ss_error1']:.3f}A  rmse={err['rmse1']:.3f}  in_band={err['in_band1']}")
        print(f"  Iq:   ss={err['ss_error2']:.3f}A  rmse={err['rmse2']:.3f}  in_band={err['in_band2']}")
        print(f"  total_error={err['total']:.4f}  collapse={err.get('collapse', False)}")
    except Exception as ex:
        print(f"  ERROR: {ex}")
    time.sleep(1.0)

print("\n" + "=" * 70)
print("  Diagnóstico completo.")
print("=" * 70)
