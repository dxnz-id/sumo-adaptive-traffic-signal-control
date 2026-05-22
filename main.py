"""
SUMO ADAPTIVE TRAFFIC LIGHT SIMULATOR
Intelligent Intersection Traffic Control System Based on Time Extension & Phase Skipping
=====================================================================================
Main Entry Point to run the adaptive traffic light simulation.
"""

import os
import sys
from rich.console import Console

# Setup TraCI path before importing SUMO tools
if 'SUMO_HOME' in os.environ:
    sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))
else:
    sys.path.append(os.path.join(r"C:\Program Files (x86)\Eclipse\Sumo", 'tools'))
import traci

# Import modularized components
from src.config import BUILD_DIR, set_traffic_volumes
from src.cli import get_congestion_from_cli
from src.generator import find_exe, build_network, build_routes, build_sensors, build_config
from src.controller import TimeExtensionController, FixedTimeController

console = Console()

# Force UTF-8 stdout encoding for Windows compatibility
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

def run_sumo_gui(use_adaptive=True, congested_list=None, run_fast=False):
    console.print("[bold cyan][3/3][/bold cyan] Launching sumo-gui via TraCI...")
    sumo_gui_bin = find_exe("sumo-gui.exe")
    config_path = os.path.join(BUILD_DIR, "config.sumocfg")
    
    # Run TraCI (set delay to 0 for maximum CPU speed, 50ms for normal mode)
    delay_val = "0" if run_fast else "50"
    cmd = [sumo_gui_bin, "-c", config_path, "--delay", delay_val, "--start", "--quit-on-end"]
    console.print(f"  -> [dim]{' '.join(cmd)}[/dim]\n")
    
    traci.start(cmd)
    console.print("  [green][OK][/green] TraCI and sumo-gui launched successfully!")
    
    if use_adaptive:
        console.print("  [green][STATUS][/green] Simulation running. Adaptive lights controlled dynamically.\n")
        # Initialize adaptive traffic light controller (Time Extension & Phase Skipping)
        # POI timer and queue overlays are automatically drawn and updated by the controller
        controller = TimeExtensionController(tls_id="center")
    else:
        console.print("  [yellow][STATUS][/yellow] Simulation running. Using SUMO built-in fixed-time program (no adaptive control).\n")
        # Initialize passive read-only controller for countdown timer overlay only
        controller = FixedTimeController(tls_id="center")

    try:
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            
            # Execute controller logic tick (adaptive or fixed-time countdown overlay)
            controller.step(step_length=0.1)
                
    except (traci.exceptions.FatalTraCIError, KeyboardInterrupt, SystemExit):
        console.print("  [yellow][INFO][/yellow] Simulation closed by user.")
    finally:
        try:
            traci.close()
        except:
            pass
        
        # 4. Generate post-simulation reports
        mode_label = "Adaptive-Control" if use_adaptive else "Fixed-Time-Program"
        from src.analyzer import print_simulation_report
        print_simulation_report(mode_label=mode_label, congested=congested_list)

if __name__ == "__main__":
    try:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        os.makedirs(BUILD_DIR, exist_ok=True)

        # 1. Fetch congestion, TLS layout, driver orderliness, and adaptive mode inputs from CLI
        congested_list, tls_layout, orderliness, use_adaptive, run_fast = get_congestion_from_cli()
        set_traffic_volumes(congested_list)

        # 2. Build SUMO XML infrastructure & network configuration files
        build_network(tls_layout)
        build_routes(orderliness)
        build_sensors()
        build_config()
        
        # 3. Launch execution GUI
        run_sumo_gui(use_adaptive, congested_list, run_fast)
        
    except KeyboardInterrupt:
        console.print("\n\n[bold yellow][INFO][/bold yellow] Simulation cancelled by user (Ctrl+C).")
        sys.exit(0)
