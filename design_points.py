"""
Calcula parámetros PI de diseño para las 3 plantas del MMC y verifica
que todos los polos de lazo cerrado estén en el semiplano izquierdo.

Plantas:
  AC:       G_ac(s)  = 1 / (Ltot*s + R)          Ltot=2.5e-3, R=1
  DC ext:   G_dce(s) = 1 / (n*C*Vc*s)            n=3, C=1, Vc=150
  DC int:   G_dci(s) = 1 / (Ltot*s)              Ltot=2.5e-3

PI:  C(s) = (Kp*s + Ki) / s   →   variables a,b / c,d / e,f
"""

import numpy as np
from numpy.polynomial import polynomial as P

# ── Parámetros del circuito ───────────────────────────────────────────────────
Ltot = 2.5e-3 + 2*1e-3  # L + 2*Ll = 4.5e-3 H
R    = 1.0
n    = 3
C    = 1.0
Vc   = 150.0

# ── Funciones auxiliares ──────────────────────────────────────────────────────

def closed_loop_poles(Kp, Ki, plant_num, plant_den, positive_feedback=False):
    """
    T(s) = C*G / (1 ± C*G)
    C(s) = (Kp*s+Ki)/s  (Kp,Ki pueden ser negativos)
    G(s) = plant_num / plant_den

    positive_feedback=True  → denominador = s*plant_den - (Kp*s+Ki)*plant_num
    positive_feedback=False → denominador = s*plant_den + (Kp*s+Ki)*plant_num
    """
    s_plant_den = np.convolve([1, 0], plant_den)
    C_num       = np.polymul([Kp, Ki], plant_num)
    n1, n2 = len(s_plant_den), len(C_num)
    size = max(n1, n2)
    p1 = np.concatenate([np.zeros(size - n1), s_plant_den])
    p2 = np.concatenate([np.zeros(size - n2), C_num])
    cl_den = p1 - p2 if positive_feedback else p1 + p2
    poles = np.roots(cl_den)
    return poles


def is_stable(poles, tol=1e-6):
    return all(p.real < tol for p in poles)


def design_ac(bw=400.0):
    """
    Planta AC: 1/(Ltot*s + R)
    Polo planta: s = -R/Ltot = -400
    Cancelación: cero PI en s = -Ki/Kp = -R/Ltot  →  Ki = Kp*(R/Ltot)
    BW lazo: ganancia cruzamiento |L(j*bw)|=1
      L(s) = Kp*(s + R/Ltot) / (s*(Ltot*s+R)) = Kp/(Ltot*s)  tras cancelación
      |L(j*bw)| = Kp/(Ltot*bw) = 1  →  Kp = Ltot*bw
    Análisis con magnitudes positivas, signo se aplica al final.
    """
    Kp = Ltot * bw
    Ki = Kp * (R / Ltot)
    return Kp, Ki   # positivos para análisis


def design_dc_ext(bw=20.0):
    """
    Planta efectiva vista por el PI externo:
      G_eff(s) = (Gain1 * Gain) * G_int_cl(s) * G_dc(s)
               = (2 * 3/E) * 1 * 1/(n*C*Vc*s)
               = 1 / (E/6 * n*C*Vc * s)
               = 1 / (75 * n*C*Vc * s)   con E=450
    Los gains intermedios (×2, ×3/E) reducen la ganancia efectiva x75,
    por lo que Kp,Ki deben ser 75 veces mayores que sin considerar los gains.
    """
    E    = 450.0
    scale = (2 * 3 / E)          # = 6/450 = 1/75
    nCVc_eff = n * C * Vc / scale  # planta efectiva denominador = 75*n*C*Vc
    wz   = bw / 3.0
    Ki   = nCVc_eff * bw**2 / (bw / wz)
    Kp   = Ki / wz
    return Kp, Ki


def design_dc_int(bw=200.0):
    """
    Planta DC int: 1/(Ltot*s)  integrador puro
    Misma estructura que DC ext.
    """
    wz = bw / 3.0
    Ki = Ltot * bw**2 / (bw / wz)
    Kp = Ki / wz
    return Kp, Ki


def check_and_print(label, Kp, Ki, plant_num, plant_den, var1, var2, sign=-1):
    """
    Verifica estabilidad probando ambas topologías de lazo y elige la estable.
    sign=-1: variables en PLECS son negativas.
    """
    Kp_s, Ki_s = sign * Kp, sign * Ki
    # Probar realimentación negativa primero, luego positiva
    for pos_fb in (False, True):
        poles = closed_loop_poles(Kp_s, Ki_s, plant_num, plant_den,
                                  positive_feedback=pos_fb)
        stable = is_stable(poles)
        if stable:
            fb_str = "pos_fb" if pos_fb else "neg_fb"
            break
    print(f"\n[{label}]  {var1}={Kp_s:.4f}  {var2}={Ki_s:.4f}  ({fb_str})")
    print(f"  Polos LC: {[f'{p.real:.2f}{p.imag:+.2f}j' for p in poles]}")
    print(f"  Estable: {stable}  {'✓' if stable else '✗ REVISAR'}")
    return stable, Kp_s, Ki_s


# ── Cálculo y verificación ────────────────────────────────────────────────────

print("=" * 60)
print("  Diseño analítico de controladores PI — MMC")
print("=" * 60)

Kp_ac, Ki_ac = design_ac(bw=400.0)
stable_ac, a, b = check_and_print(
    "AC Port", Kp_ac, Ki_ac,
    plant_num=np.array([1.0]),
    plant_den=np.array([Ltot, R]),
    var1="a", var2="b", sign=+1)   # neg_fb clásico, controlador positivo

Kp_dce, Ki_dce = design_dc_ext(bw=20.0)
stable_dce, c, d = check_and_print(
    "DC Externo", Kp_dce, Ki_dce,
    plant_num=np.array([1.0]),
    plant_den=np.array([n * C * Vc, 0.0]),
    var1="c", var2="d", sign=+1)  # error = E - V0Σ → neg_fb clásico → positivo

Kp_dci, Ki_dci = design_dc_int(bw=200.0)
stable_dci, e, f = check_and_print(
    "DC Interno", Kp_dci, Ki_dci,
    plant_num=np.array([1.0]),
    plant_den=np.array([Ltot, 0.0]),
    var1="e", var2="f", sign=+1)   # lazo interno: realimentación negativa, controlador positivo

print()
all_stable = stable_ac and stable_dce and stable_dci
print("=" * 60)
print(f"  Todos estables: {all_stable}  {'→ listo para optimización' if all_stable else '→ AJUSTAR BW'}")
print("=" * 60)

print(f"""
  Punto inicial para optimización bayesiana:
    a={a:.4f}  b={b:.4f}
    c={c:.6f}  d={d:.4f}
    e={e:.4f}  f={f:.4f}
""")
