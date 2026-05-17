"""
🚥 SUMO ADAPTIVE TRAFFIC LIGHT SIMULATOR 🚥
Sistem Kendali Lampu Lalu Lintas Cerdas Berbasis Time Extension & Phase Skipping
=============================================================================
Entri Point Utama untuk menjalankan simulasi adaptif perempatan jalan.
"""

import os
import sys
from rich.console import Console

# Setup jalur TraCI sebelum import
if 'SUMO_HOME' in os.environ:
    sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))
else:
    sys.path.append(os.path.join(r"C:\Program Files (x86)\Eclipse\Sumo", 'tools'))
import traci

# Impor modul lokal hasil refaktorisasi modular
from src.config import BUILD_DIR, set_traffic_volumes
from src.cli import get_crowded_from_cli
from src.generator import find_exe, build_network, build_routes, build_sensors, build_config
from src.controller import TimeExtensionController

console = Console()

# Force UTF-8 output supaya tidak error di terminal Windows
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

def run_sumo_gui():
    console.print("[bold cyan][3/3][/bold cyan] Menjalankan sumo-gui via TraCI...")
    sumo_gui_bin = find_exe("sumo-gui.exe")
    config_path = os.path.join(BUILD_DIR, "config.sumocfg")
    
    # Jalankan TraCI
    cmd = [sumo_gui_bin, "-c", config_path, "--delay", "50", "--start", "--quit-on-end"]
    console.print(f"  -> [dim]{' '.join(cmd)}[/dim]\n")
    
    traci.start(cmd)
    console.print("  [green][OK][/green] TraCI dan sumo-gui diluncurkan!")
    console.print("  [green][STATUS][/green] Simulasi sedang berjalan. Lampu adaptif dikontrol secara dinamis.\n")
    
    # Inisialisasi pengontrol lampu adaptif berbasis Time Extension & Phase Skipping
    # POI Timer dan Queue akan dibuat dan diupdate secara otomatis di dalam kontroler
    controller = TimeExtensionController(tls_id="center")

    try:
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            
            # Jalankan logika pengontrol adaptif pada setiap step (termasuk update visual POI)
            controller.step(step_length=0.1)
                
    except (traci.exceptions.FatalTraCIError, KeyboardInterrupt, SystemExit):
        console.print("  [yellow][INFO][/yellow] Simulasi ditutup oleh pengguna.")
    finally:
        try:
            traci.close()
        except:
            pass

if __name__ == "__main__":
    try:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        os.makedirs(BUILD_DIR, exist_ok=True)

        # 1. Ambil input pilihan kemacetan, mode lampu, & ketertiban dari CLI
        crowded_list, tls_layout, orderliness = get_crowded_from_cli()
        set_traffic_volumes(crowded_list)

        # 2. Pembangkitan infrastruktur berkas SUMO XML
        build_network(tls_layout)
        build_routes(orderliness)
        build_sensors()
        build_config()
        
        # 3. Jalankan GUI utama
        run_sumo_gui()
        
    except KeyboardInterrupt:
        console.print("\n\n[bold yellow][INFO][/bold yellow] Simulasi dibatalkan oleh pengguna (Ctrl+C).")
        sys.exit(0)
