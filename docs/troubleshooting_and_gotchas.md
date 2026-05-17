# Troubleshooting & Known Gotchas

This document covers common setup errors, known compatibility issues, and their solutions.

---

## 1. `SUMO_HOME` Path Not Configured

**Symptom:**
```
FileNotFoundError: Unable to locate executable 'netconvert.exe'.
Ensure SUMO is installed correctly and SUMO_HOME is set in your environment variables.
```

**Cause:** The `SUMO_HOME` environment variable is not set, and SUMO is not installed at the default fallback path (`C:\Program Files (x86)\Eclipse\Sumo`).

**Solution:**

### Windows (PowerShell — temporary, current session only)
```powershell
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
```

### Windows (Permanent via System Settings)
1. Open **System Properties** → **Advanced** → **Environment Variables**.
2. Under **System variables**, click **New**.
3. Set **Variable name**: `SUMO_HOME`
4. Set **Variable value**: `C:\Program Files (x86)\Eclipse\Sumo` (adjust to your install path)
5. Restart your terminal.

### macOS / Linux
```bash
# Add to ~/.bashrc or ~/.zshrc
export SUMO_HOME="/usr/share/sumo"
source ~/.bashrc
```

---

## 2. `Cannot find module 'traci'`

**Symptom:**
```
ModuleNotFoundError: No module named 'traci'
```

**Cause:** The `SUMO_HOME/tools` directory containing `traci` is not in the Python path. `main.py` attempts to append it automatically, but only if `SUMO_HOME` is set.

**Solution:** Set `SUMO_HOME` as described above. Then verify the path is correct:
```powershell
ls "$env:SUMO_HOME\tools\traci"
```

---

## 3. Questionary CLI Input Fails in IDE / Non-Interactive Terminal

**Symptom:**
```
Note: Non-interactive terminal detected, switching to standard text inputs...
```

This is **not an error** — it is expected behavior. The `questionary` library requires a true interactive terminal with screen buffer support (arrow keys, space selection). IDE output panels (e.g., VS Code **Run** button, PyCharm console) do not support this.

**Solution:** Run the simulation from a **real terminal**:
```powershell
# VS Code integrated terminal (Ctrl+`)
uv run python main.py

# Windows Terminal or PowerShell directly
cd d:\Downloads\simulasi-perempatan
uv run python main.py
```

The text-based fallback prompts work identically in non-interactive mode — you simply type letters (`n`, `s`, `1`, `2`) instead of using arrow keys.

---

## 4. TraCI Port Conflict

**Symptom:**
```
traci.exceptions.FatalTraCIError: Could not connect to TraCI server
```
or
```
OSError: [WinError 10061] No connection could be made because the target machine actively refused it
```

**Cause:** A previous SUMO process did not close cleanly and is still holding the TraCI port (default: `8813`).

**Solution:**

### Windows
```powershell
# Find and kill any lingering sumo-gui.exe process
Get-Process -Name "sumo-gui" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name "sumo" -ErrorAction SilentlyContinue | Stop-Process -Force
```

### macOS / Linux
```bash
pkill -f sumo-gui
pkill -f sumo
```

---

## 5. SUMO GUI Closes Immediately Without Showing Simulation

**Cause:** A route file, network file, or additional sensor file contains a critical XML syntax error or references a non-existent edge ID.

**Solution:** Check the `map/build/` directory for generated files and validate them:
```powershell
# Check routes file for errors
& "$env:SUMO_HOME\bin\duarouter.exe" --route-files map/build/routes.rou.xml --net-file map/build/net.net.xml --output-file NUL
```
Any invalid edge references will be listed in the output.

---

## 6. Phase Index Out of Range (`TraCIException`)

**Symptom:**
```
traci.exceptions.TraCIException: The phase index 4 is not in the allowed range [0, 3]
```

**Cause:** The controller is attempting to set a phase index that does not exist in the active TLS program. This typically happens if:
- The dynamic detection logic fails to detect Dual Mode correctly.
- `getAllProgramLogics()` returns an empty list before SUMO finishes initializing.

**Solution:** The dynamic detection logic in `TimeExtensionController.__init__` reads the phase count at startup:
```python
logics = traci.trafficlight.getAllProgramLogics(self.tls_id)
num_phases = len(logics[0].phases)
self.is_dual_mode = (num_phases <= 4)
```
If this still fails, add a brief delay before reading:
```python
traci.simulationStep()  # Advance one tick to ensure TLS is fully initialized
logics = traci.trafficlight.getAllProgramLogics(self.tls_id)
```

---

## 7. UnicodeDecodeError in Terminal (Windows)

**Symptom:**
```
UnicodeDecodeError: 'charmap' codec can't decode byte 0xe2 in position ...
```

**Cause:** Windows terminals default to `cp1252` (Windows-1252) encoding, which cannot display UTF-8 characters used in SUMO output.

**Solution:** Already handled in `main.py`:
```python
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
```
If the problem persists, run:
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001
```
