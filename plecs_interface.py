import re
import time
import xmlrpc.client
from pathlib import Path

import numpy as np
import pyautogui
import pandas as pd
from pywinauto import Desktop, Application

MODEL_NAME  = "MMC_sinmodulacion - 24-08-26 - NO FUNCIONAL"
PLECS_URL   = "http://localhost:1080/RPC2"

SCOPE_AC_TITLE = f"{MODEL_NAME}/AC Port/Scope"
SCOPE_DC_TITLE = f"{MODEL_NAME}/DC Port/V0\u03a3 output"

CSV_AC = Path(r"C:\Users\danie\mmc_tuning\results\scope_ac.csv")
CSV_DC = Path(r"C:\Users\danie\mmc_tuning\results\scope_dc.csv")

pyautogui.FAILSAFE = True
pyautogui.PAUSE    = 0.1


# ── XML-RPC ───────────────────────────────────────────────────────────────────

def _server():
    return xmlrpc.client.Server(PLECS_URL)


def _read_init(server) -> str:
    return server.plecs.get(MODEL_NAME, "InitializationCommands")


def _write_init(server, cmd: str):
    server.plecs.set(MODEL_NAME, "InitializationCommands", cmd)


def _update_var(cmd: str, name: str, value: float) -> str:
    # \b asegura que no matchee subcadenas (ej: "c" no matchea "Tsc" ni "Vc")
    pattern = rf"(?<![A-Za-z0-9_])({re.escape(name)})(\s*=\s*)[^\n;]+"
    new_cmd, n = re.subn(pattern, rf"\g<1>\g<2>{value}", cmd)
    if n == 0:
        new_cmd = cmd.rstrip() + f"\n{name} = {value}"
    return new_cmd


def set_params(params: dict):
    """Escribe a,b,c,d,e,f en InitializationCommands via XML-RPC."""
    _stop_simulation()
    srv = _server()
    try:
        cmd = _read_init(srv)
        for name, value in params.items():
            cmd = _update_var(cmd, name, float(value))
        _write_init(srv, cmd)
    except ConnectionRefusedError:
        raise RuntimeError("No se puede conectar a PLECS.")
    except Exception as e:
        raise RuntimeError(f"Error al setear parámetros: {e}")


def get_model_params() -> dict:
    srv = _server()
    try:
        cmd = _read_init(srv)
    except Exception as e:
        raise RuntimeError(f"Error al leer InitializationCommands: {e}")

    def _extract(name):
        m = re.search(rf"{re.escape(name)}\s*=\s*([0-9eE+\-\.]+)", cmd)
        if m:
            return float(m.group(1))
        raise RuntimeError(f"Variable '{name}' no encontrada en InitializationCommands.")

    return {k: _extract(k) for k in ("a", "b", "c", "d", "e", "f")}


# ── GUI helpers ───────────────────────────────────────────────────────────────

def _focus_model_win():
    wins = [w for w in Desktop(backend="uia").windows()
            if MODEL_NAME in w.window_text()
            and "Scope" not in w.window_text()
            and "Port" not in w.window_text()
            and "output" not in w.window_text()]
    if not wins:
        raise RuntimeError("Ventana del modelo PLECS no encontrada.")
    wins[0].set_focus()
    time.sleep(0.4)


def _is_sim_running() -> bool:
    for w in Desktop(backend="uia").windows():
        t = w.window_text()
        if MODEL_NAME in t and "[running]" in t:
            return True
    return False


def _stop_simulation():
    if not _is_sim_running():
        return
    _focus_model_win()
    pyautogui.hotkey("ctrl", "t")
    deadline = time.time() + 20.0
    while time.time() < deadline:
        time.sleep(0.5)
        if not _is_sim_running():
            return
    raise RuntimeError("No se pudo detener la simulación en 20 segundos.")


def _run_simulation_gui():
    _stop_simulation()
    time.sleep(0.2)
    _focus_model_win()
    pyautogui.hotkey("ctrl", "t")

    print("    [sim] Esperando inicio...", flush=True)
    deadline_start = time.time() + 10.0
    while time.time() < deadline_start:
        if _is_sim_running():
            break
        time.sleep(0.2)

    print("    [sim] Simulando — esperando fin...", flush=True)
    deadline_end = time.time() + 30.0  # 0.05s sim no debería tardar más de 30s
    while time.time() < deadline_end:
        if not _is_sim_running():
            break
        time.sleep(0.2)

    time.sleep(0.5)


# ── CSV export ────────────────────────────────────────────────────────────────

def _export_scope_to(scope_title: str, csv_path: Path):
    """Exporta un scope específico a la ruta indicada."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    app = Application(backend="uia").connect(title=scope_title)
    scope_win = app.window(title=scope_title)
    scope_win.set_focus()
    time.sleep(0.3)

    scope_win.child_window(title="File", control_type="MenuItem").click_input()
    time.sleep(0.3)
    scope_win.child_window(title="Export", control_type="MenuItem").click_input()
    time.sleep(0.3)

    csv_item = scope_win.child_window(title="as CSV", control_type="MenuItem")
    rect = csv_item.rectangle()
    pyautogui.moveTo((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
    time.sleep(0.3)

    desktop = Desktop(backend="uia")
    all_item = None
    for w in desktop.windows():
        try:
            for item in w.descendants(control_type="MenuItem"):
                if "All" in item.window_text():
                    all_item = item
                    break
        except Exception:
            pass
        if all_item:
            break

    if not all_item:
        raise RuntimeError(f"No se encontró 'All...' en el submenú de Export ({scope_title}).")

    rect2 = all_item.rectangle()
    pyautogui.click((rect2.left + rect2.right) // 2, (rect2.top + rect2.bottom) // 2)
    time.sleep(1.0)

    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.15)
    pyautogui.typewrite(str(csv_path), interval=0.02)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.8)

    # Confirmar reemplazo
    pyautogui.press("left")
    time.sleep(0.15)
    pyautogui.press("enter")
    time.sleep(0.5)

    if not csv_path.exists():
        raise RuntimeError(f"CSV no fue generado en {csv_path}.")


def _read_csv_ac() -> dict:
    """Columnas: Time, Id, Iq, SRF->RRF:1, SRF->RRF:2"""
    df = pd.read_csv(CSV_AC, header=None, comment="%")
    df = df.apply(pd.to_numeric, errors="coerce").dropna()
    if df.shape[1] < 5:
        raise RuntimeError(f"scope_ac.csv tiene {df.shape[1]} columnas, se esperaban 5.")
    return {
        "time": df.iloc[:, 0].to_numpy(),
        "sig1": df.iloc[:, 3].to_numpy(),  # SRF->RRF:1  target=15
        "sig2": df.iloc[:, 4].to_numpy(),  # SRF->RRF:2  target=2
    }


def _read_csv_dc() -> dict:
    """Columnas: Time, Zero-Order Hold (V0Σ real), Vc* (referencia=450)"""
    df = pd.read_csv(CSV_DC, header=None, comment="%")
    df = df.apply(pd.to_numeric, errors="coerce").dropna()
    if df.shape[1] < 2:
        raise RuntimeError(f"scope_dc.csv tiene {df.shape[1]} columnas, se esperaban ≥2.")
    return {
        "time": df.iloc[:, 0].to_numpy(),
        "v0s":  df.iloc[:, 1].to_numpy(),  # Zero-Order Hold = V0Σ real, target=450
    }


def run_simulation() -> dict:
    """Corre simulación, exporta ambos scopes y retorna datos combinados."""
    _run_simulation_gui()
    _export_scope_to(SCOPE_AC_TITLE, CSV_AC)
    _export_scope_to(SCOPE_DC_TITLE, CSV_DC)
    ac = _read_csv_ac()
    dc = _read_csv_dc()
    return {
        "time": ac["time"],
        "sig1": ac["sig1"],   # SRF->RRF:1  target=15
        "sig2": ac["sig2"],   # SRF->RRF:2  target=2
        "v0s":  dc["v0s"],    # V0Σ         target=450
        "time_dc": dc["time"],
    }
