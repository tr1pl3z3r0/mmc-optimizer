# MMC PI Controller Optimizer

Automated Bayesian optimization of PI controller parameters for a Modular Multilevel Converter (MMC) simulated in PLECS 5.0.2.

Optimizes 6 parameters simultaneously:
- **AC Port**: `a` (Kp), `b` (Ki) — targets SRF→RRF:1 = 15, SRF→RRF:2 = 2
- **DC Port external loop**: `c` (Kp), `d` (Ki) — targets V0Σ ≈ E = 450 V (±5%)
- **DC Port internal loop**: `e` (Kp), `f` (Ki) — cascaded with external

---

## Requirements

- Windows 10/11
- [PLECS 5.0.2](https://www.plexim.com/) with XML-RPC enabled on port 1080
- Python 3.10+
- The `.plecs` model file (not included in this repo — share separately)

---

## Setup

### 1. Clone the repo

```powershell
git clone https://github.com/<your-username>/mmc-optimizer.git
cd mmc-optimizer
```

### 2. Create a virtual environment

```powershell
python -m venv plecs_env
& .\plecs_env\Scripts\Activate.ps1
```

> If you get an execution policy error:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

### 3. Install dependencies

```powershell
pip install numpy pandas scipy scikit-optimize pywinauto pyautogui
```

### 4. Configure PLECS

1. Open the `.plecs` model file
2. Go to **Simulation → Preferences → XML-RPC** and verify port is **1080**
3. Open both scopes manually so their windows are visible:
   - `AC Port / Scope`
   - `DC Port / V0Σ output`

### 5. Edit `plecs_interface.py`

Change the `MODEL_NAME` constant to match the exact title bar of your PLECS model window:

```python
MODEL_NAME = "MMC_sinmodulacion - 24-08-26 - NO FUNCIONAL"  # ← change this
```

Change the CSV output paths if your Windows username is different:

```python
CSV_AC = Path(r"C:\Users\YOUR_USERNAME\mmc_tuning\results\scope_ac.csv")
CSV_DC = Path(r"C:\Users\YOUR_USERNAME\mmc_tuning\results\scope_dc.csv")
```

### 6. Create the results folder

```powershell
mkdir results
```

---

## Running the optimizer

```powershell
& .\plecs_env\Scripts\Activate.ps1
python optimize.py
```

- The optimizer starts from an analytically derived seed point (verified stable poles in left half-plane)
- Every evaluation is logged to `results/log.csv`
- To stop at any time: type **Q + Enter** in the terminal
- Optimal parameters are saved to `results/optimal_params.csv` when finished

---

## File structure

```
mmc-optimizer/
├── plecs_interface.py   # PLECS communication: XML-RPC + GUI automation
├── objective.py         # Error function: RMSE + settling + steady-state
├── optimize.py          # Bayesian optimization (scikit-optimize GP)
├── design_points.py     # Analytical PI design + closed-loop pole verification
├── run_iteration.py     # Final simulation run + plot generation
├── test_connection.py   # Connectivity test before running optimizer
├── results/
│   ├── log.csv          # Evaluation log (created at runtime)
│   ├── optimal_params.csv
│   ├── scope_ac.csv     # AC scope export (created at runtime)
│   └── scope_dc.csv     # DC scope export (created at runtime)
└── README.md
```

---

## How it works

```
optimize.py
  └─ objective_fn(a, b, c, d, e, f)
       ├─ plecs_interface.set_params()    → writes to InitializationCommands via XML-RPC
       ├─ plecs_interface.run_simulation() → Ctrl+T via pyautogui, waits for [running] to clear
       ├─ plecs_interface._export_scope_to() → File→Export→as CSV via pywinauto
       └─ objective.compute_error()       → combined error: AC (40%) + DC (60%) + settling penalty
```

**Stability filter**: before each simulation, `_is_stable_point()` computes closed-loop poles analytically. Points with any pole in the right half-plane are rejected without running PLECS.

**Loop topology**:
- AC loop and DC external loop: effective positive feedback (controller gains negative, plant gain negative → stable)
- DC internal loop: classical negative feedback (controller gains positive)

---

## Circuit parameters

| Symbol | Value | Description |
|--------|-------|-------------|
| `fcr`  | 5000 Hz | Carrier frequency |
| `L`    | 2.5e-3 H | Arm inductance |
| `R`    | 1 Ω | Arm resistance |
| `C`    | 1 F | SM capacitance |
| `Vc`   | 150 V | SM capacitor voltage |
| `E`    | 450 V | DC bus voltage |
| `n`    | 3 | SMs per arm |

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `No se puede conectar a PLECS` | Verify PLECS is open and XML-RPC is enabled on port 1080 |
| `Ventana del modelo PLECS no encontrada` | Check `MODEL_NAME` matches the exact window title |
| `No se encontró 'All...'` | Open the scope window manually before running |
| `Cannot modify circuit while simulation is running` | The stop detection uses `[running]` in the window title — make sure the model window is visible |
| Execution policy error | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |

---

## Known limitations

- Requires PLECS 5.0.2 — `plecs.simulate` XML-RPC call is broken in this version (relocation error), so simulation is triggered via GUI automation (Ctrl+T)
- Screen resolution changes may affect pyautogui coordinate-based menu navigation
- Only tested on Windows 10
