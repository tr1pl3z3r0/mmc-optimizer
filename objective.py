import numpy as np

TARGET_SIG1 = 15.0    # SRF->RRF:1
TARGET_SIG2 = 2.0     # SRF->RRF:2
TARGET_V0S  = 450.0   # V0Σ

WEIGHT_AC  = 0.4   # peso loop AC (sig1 + sig2)
WEIGHT_DC  = 0.6   # peso loop DC (V0Σ) — más crítico

SETTLING_PENALTY = 1000.0
BAND_PCT = 0.05


def _settling_error(time, signal, target):
    band_lo = target * (1 - BAND_PCT)
    band_hi = target * (1 + BAND_PCT)
    out_of_band = np.where((signal < band_lo) | (signal > band_hi))[0]
    if len(out_of_band) == 0:
        return 0.0, 0.0, True
    t_settling = time[out_of_band[-1]]
    last = signal[-1]
    in_band = band_lo <= last <= band_hi
    penalty = 0.0 if in_band else SETTLING_PENALTY
    return t_settling, penalty, in_band


def _rmse_norm(simulated, target):
    ref = np.full_like(simulated, target, dtype=float)
    return float(np.sqrt(np.mean((simulated - ref) ** 2))) / abs(target)


def _ss_error_norm(signal, target):
    tail = max(1, int(len(signal) * 0.10))
    return abs(np.mean(signal[-tail:]) - target) / abs(target)


def compute_error(sim_data: dict, verbose: bool = False) -> dict:
    time    = sim_data["time"]
    time_dc = sim_data.get("time_dc", time)
    sig1    = sim_data["sig1"]
    sig2    = sim_data["sig2"]
    v0s     = sim_data["v0s"]

    rmse1 = _rmse_norm(sig1, TARGET_SIG1)
    rmse2 = _rmse_norm(sig2, TARGET_SIG2)
    rmse_v = _rmse_norm(v0s, TARGET_V0S)

    t_set1, pen1, in1 = _settling_error(time, sig1, TARGET_SIG1)
    t_set2, pen2, in2 = _settling_error(time, sig2, TARGET_SIG2)
    t_setv, penv, inv = _settling_error(time_dc, v0s, TARGET_V0S)

    ss1 = _ss_error_norm(sig1, TARGET_SIG1)
    ss2 = _ss_error_norm(sig2, TARGET_SIG2)
    ssv = _ss_error_norm(v0s, TARGET_V0S)

    ac_error = (rmse1 + ss1) * 0.5 + (rmse2 + ss2) * 0.5
    dc_error = rmse_v + ssv

    total = WEIGHT_AC * ac_error + WEIGHT_DC * dc_error + pen1 + pen2 + penv

    result = {
        "total": total,
        "rmse1": rmse1 * TARGET_SIG1,
        "rmse2": rmse2 * TARGET_SIG2,
        "rmse_v0s": rmse_v * TARGET_V0S,
        "t_settling1": t_set1,
        "t_settling2": t_set2,
        "t_settling_v0s": t_setv,
        "in_band1": in1,
        "in_band2": in2,
        "in_band_v0s": inv,
        "ss_error1": ss1 * TARGET_SIG1,
        "ss_error2": ss2 * TARGET_SIG2,
        "ss_error_v0s": ssv * TARGET_V0S,
    }

    if verbose:
        print(f"  AC: RMSE sig1={result['rmse1']:.3f}  sig2={result['rmse2']:.3f}")
        print(f"  DC: RMSE V0Σ={result['rmse_v0s']:.3f}")
        print(f"  t_set: sig1={t_set1:.4f}s  sig2={t_set2:.4f}s  V0Σ={t_setv:.4f}s")
        print(f"  in_band: sig1={in1}  sig2={in2}  V0Σ={inv}")
        print(f"  SS err: sig1={result['ss_error1']:.3f}  sig2={result['ss_error2']:.3f}  V0Σ={result['ss_error_v0s']:.3f}")
        print(f"  TOTAL = {total:.6f}")

    return result
