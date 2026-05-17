#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate.py
===========
Script utama untuk:
  1. Membuat jaringan jalan (net.net.xml) via netconvert
  2. Membuat file rute dinamis (routes.rou.xml) dengan:
     - Arus kendaraan dari 4 arah
     - 3 jenis manuver (lurus, belok kiri, belok kanan)
     - Volume lalu lintas bervariasi per waktu (jam sibuk / normal)
     - Campuran jenis kendaraan (mobil, motor, bus, truk)
  3. Menjalankan sumo-gui

Cara pakai:
    python generate.py

Pastikan SUMO sudah terinstall dan PATH sudah di-set, atau ubah
variabel SUMO_HOME di bawah.
"""

import os
import sys
import random
import subprocess
import xml.etree.ElementTree as ET
from xml.dom import minidom
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

# Inisialisasi console Rich
console = Console()

# Setup jalur TraCI sebelum import
if 'SUMO_HOME' in os.environ:
    sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))
else:
    sys.path.append(os.path.join(r"C:\Program Files (x86)\Eclipse\Sumo", 'tools'))
import traci
from src.controller import TimeExtensionController

# Force UTF-8 output supaya tidak error di terminal Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------
#  KONFIGURASI PATH SUMO
# ---------------------------------------------------------
SUMO_HOME = os.environ.get("SUMO_HOME", r"C:\Program Files (x86)\Eclipse\Sumo")
SUMO_BIN  = os.path.join(SUMO_HOME, "bin")


def find_exe(name: str) -> str:
    """Cari executable SUMO di PATH sistem atau SUMO_BIN."""
    import shutil
    found = shutil.which(name)
    if found:
        return found
    candidate = os.path.join(SUMO_BIN, name)
    if os.path.isfile(candidate):
        return candidate
    raise FileNotFoundError(
        f"Tidak dapat menemukan '{name}'.\n"
        f"Pastikan SUMO terinstall dan SUMO_HOME di-set dengan benar.\n"
        f"SUMO_HOME saat ini: {SUMO_HOME}"
    )


# ---------------------------------------------------------
#  PARAMETER SIMULASI
# ---------------------------------------------------------
SIM_DURATION = 3600   # detik (1 jam simulasi)
RANDOM_SEED  = 42
BUILD_DIR    = "map"  # Folder untuk file simulasi
SRC_DIR      = "src"  # Folder untuk file sumber XML
random.seed(RANDOM_SEED)

# Volume Dasar (Akan diupdate via GUI)
TRAFFIC_VOLUME = {
    "north": [], "south": [], "west": [], "east": []
}

def set_traffic_volumes(crowded_directions):
    """Menentukan volume berdasarkan pilihan GUI."""
    normal_vol = [
        (0, 900, 180), (900, 1800, 350), (1800, 2700, 220), (2700, 3600, 320)
    ]
    crowded_vol = [
        (0, 900, 800), (900, 1800, 1500), (1800, 2700, 900), (2700, 3600, 1400)
    ]
    
    for direction in ["north", "south", "west", "east"]:
        if direction in crowded_directions:
            TRAFFIC_VOLUME[direction] = crowded_vol
        else:
            TRAFFIC_VOLUME[direction] = normal_vol

def get_crowded_from_cli():
    """Mengambil input kemacetan dari terminal dengan antarmuka interaktif minimalis."""
    console.print()
    console.print("[bold cyan]SUMO ADAPTIVE TRAFFIC LIGHT SIMULATOR[/bold cyan]")
    console.print("[dim]Sistem Kendali Lampu Lalu Lintas Cerdas Berbasis Time Extension & Phase Skipping[/dim]")
    console.print()
    
    try:
        # 1. Checkbox Kemacetan menggunakan Questionary (Bisa navigasi panah & spasi!)
        selected = questionary.checkbox(
            "Pilih arah yang ingin dibuat sangat ramai (Macet):",
            choices=[
                questionary.Choice("Utara (North)", value="north"),
                questionary.Choice("Selatan (South)", value="south"),
                questionary.Choice("Barat (West)", value="west"),
                questionary.Choice("Timur (East)", value="east"),
            ],
            instruction="(Gunakan [Spasi] untuk memilih/batal, [Enter] untuk konfirmasi)"
        ).ask()
        
        if selected is None:
            selected = []
            
        # 2. Opsi Mode Lampu Merah menggunakan Questionary (Radio input menu!)
        tls_choice = questionary.select(
            "Pilih Mode Program Lampu Lalu Lintas:",
            choices=[
                questionary.Choice("Tunggal (Satu per satu arah hijau)", value="1"),
                questionary.Choice("Ganda (Dua arah berlawanan hijau bareng)", value="2"),
            ]
        ).ask()
        
        tls_layout = "incoming" if tls_choice != "2" else "opposites"
        
        # 3. Opsi Ketertiban menggunakan Questionary
        ord_choice = questionary.select(
            "Pilih Tingkat Ketertiban Pengendara:",
            choices=[
                questionary.Choice("Tertib (Jaga jarak aman, kecepatan konstan)", value="1"),
                questionary.Choice("Semrawut (Ugal-ugalan, menyalip)", value="2"),
            ]
        ).ask()
        
        orderliness = "orderly" if ord_choice != "2" else "chaotic"
        
    except Exception:
        # FALLBACK: Jika dijalankan di terminal non-interaktif / IDE output panel yang tidak mendukung console screen buffer
        console.print("[dim]Note: Terminal non-interaktif terdeteksi, beralih ke input teks standar...[/dim]\n")
        
        # 1. Menu Pilihan Kemacetan
        table = Table(show_header=False, box=None)
        table.add_row("[bold green][n][/bold green] [cyan]North / Utara[/cyan]", "[bold green][s][/bold green] [cyan]South / Selatan[/cyan]")
        table.add_row("[bold green][w][/bold green] [cyan]West  / Barat[/cyan]", "[bold green][e][/bold green] [cyan]East  / Timur[/cyan]")
        
        console.print(Panel(
            table,
            title="PENGATURAN KEMACETAN (PILIH ARAH MACET)",
            subtitle="Ketik hurufnya saja (misal: 'n' atau 's,e'). Kosongkan jika normal."
        ))
        
        ans = Prompt.ask("Masukkan pilihan arah", default="").lower().replace(" ", "")
        
        mapping = {'n': 'north', 's': 'south', 'w': 'west', 'e': 'east'}
        selected = []
        
        if ans:
            parts = ans.split(",")
            for p in parts:
                if p in mapping:
                    selected.append(mapping[p])
                elif p in mapping.values():
                    selected.append(p)

        # 2. Opsi Mode Lampu Merah
        console.print("\nPilih Mode Program Lampu Lalu Lintas:")
        console.print(" [1] Tunggal (Satu per satu arah hijau bergantian)")
        console.print(" [2] Ganda   (Dua arah berlawanan hijau bersamaan)")
        
        tls_choice = Prompt.ask("Pilih Mode", choices=["1", "2"], default="1")
        tls_layout = "incoming" if tls_choice != "2" else "opposites"
        
        # 3. Opsi Ketertiban
        console.print("\nPilih Tingkat Ketertiban Pengendara:")
        console.print(" [1] Tertib   (Jaga jarak aman, kecepatan konstan)")
        console.print(" [2] Semrawut (Ugal-ugalan, menyalip)")
        
        ord_choice = Prompt.ask("Pilih Perilaku", choices=["1", "2"], default="1")
        orderliness = "orderly" if ord_choice != "2" else "chaotic"

    # Ringkasan Konfigurasi Sebelum Start
    console.print()
    console.print("[bold green]KONFIGURASI SIMULASI:[/bold green]")
    console.print(f"  • Status Kemacetan : [yellow]{'RAMAI (' + ', '.join([s.capitalize() for s in selected]) + ')' if selected else 'NORMAL'}[/yellow]")
    console.print(f"  • Mode Siklus TLS  : [cyan]{'TUNGGAL' if tls_layout == 'incoming' else 'GANDA'}[/cyan]")
    console.print(f"  • Ketertiban Jalan : [green]{orderliness.upper()}[/green]")
    console.print()
        
    return selected, tls_layout, orderliness

# Proporsi manuver per arah: (lurus, kiri, kanan)
TURN_RATIO = {
    "north": (0.55, 0.25, 0.20),
    "south": (0.55, 0.20, 0.25),
    "west":  (0.50, 0.25, 0.25),
    "east":  (0.50, 0.25, 0.25),
}

# Rute berdasarkan arah dan manuver
# Belok kiri sekarang melewati slip road (bypass simpang utama)
ROUTES = {
    "north": {
        "straight": ("north_in_1 north_in_2", "south_out_1 south_out_2"),
        "right":    ("north_in_1 north_in_2", "west_out_1 west_out_2"),
        "left":     ("north_in_1", "slip_ne east_out_2"),
    },
    "south": {
        "straight": ("south_in_1 south_in_2", "north_out_1 north_out_2"),
        "right":    ("south_in_1 south_in_2", "east_out_1 east_out_2"),
        "left":     ("south_in_1", "slip_sw west_out_2"),
    },
    "west": {
        "straight": ("west_in_1 west_in_2", "east_out_1 east_out_2"),
        "right":    ("west_in_1 west_in_2", "south_out_1 south_out_2"),  # LHT: west → east → belok kanan = selatan
        "left":     ("west_in_1", "slip_wn north_out_2"),
    },
    "east": {
        "straight": ("east_in_1 east_in_2", "west_out_1 west_out_2"),
        "right":    ("east_in_1 east_in_2", "north_out_1 north_out_2"),  # LHT: east → west → belok kanan = utara
        "left":     ("east_in_1", "slip_es south_out_2"),
    },
}

# Jenis kendaraan: (id, accel, decel, length_m, maxSpeed_ms, sigma, color_rgb, proporsi)
VEHICLE_TYPES = [
    ("car",        2.6, 4.5,  4.5,  13.89, 0.5, "255,200,0",  0.65),
    ("motorcycle", 3.0, 5.0,  2.0,  16.67, 0.6, "0,180,255",  0.20),
    ("bus",        1.5, 3.5, 12.0,  11.11, 0.3, "50,200,50",  0.08),
    ("truck",      1.2, 3.0, 10.0,  11.11, 0.3, "200,100,50", 0.07),
]

GUI_SHAPE = {
    "car": "passenger", "motorcycle": "motorcycle",
    "bus": "bus",       "truck": "truck",
}


# ---------------------------------------------------------
#  HELPER
# ---------------------------------------------------------
def ok(msg: str):
    console.print(f"  [green][OK][/green] {msg}")


def prettify(elem) -> str:
    raw = ET.tostring(elem, encoding="unicode")
    reparsed = minidom.parseString(raw)
    return reparsed.toprettyxml(indent="    ", encoding=None)


def write_xml(path: str, content: str):
    with open(path, "w", encoding="utf-8") as f:
        lines = content.split("\n")
        if lines[0].startswith("<?xml"):
            lines = lines[1:]
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write("\n".join(lines))
    ok(os.path.basename(path))


# ---------------------------------------------------------
#  STEP 1 : Buat net.net.xml via netconvert
# ---------------------------------------------------------
def build_network(tls_layout="opposites"):
    console.print("\n[bold cyan][1/3][/bold cyan] Membuat jaringan jalan dengan netconvert...")
    netconvert_bin = find_exe("netconvert.exe")
    cmd = [
        netconvert_bin,
        "--node-files",            os.path.join(SRC_DIR, "nodes.nod.xml"),
        "--edge-files",            os.path.join(SRC_DIR, "edges.edg.xml"),
        "--connection-files",      os.path.join(SRC_DIR, "connections.con.xml"),
        "--output-file",           os.path.join(BUILD_DIR, "net.net.xml"),
        "--tls.default-type",      "static",
        "--tls.layout",            tls_layout,
        "--tls.green.time",        "35",
        "--tls.yellow.time",       "4",
        "--tls.red.time",          "2",
        "--no-turnarounds",        "true",
        "--junctions.corner-detail", "5",
        "--lefthand",              "true",
        "--geometry.remove",       "true",
        "--verbose",               "false",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        console.print(f"[bold red]ERROR netconvert:[/bold red]\n{result.stderr}")
        sys.exit(1)
    ok("net.net.xml berhasil dibuat")


# ---------------------------------------------------------
#  STEP 2 : Buat routes.rou.xml
# ---------------------------------------------------------
def build_routes(orderliness="orderly"):
    console.print("[bold cyan][2/3][/bold cyan] Membuat rute kendaraan dinamis...")

    root = ET.Element("routes")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("xsi:noNamespaceSchemaLocation",
             "http://sumo.dlr.de/xsd/routes_file.xsd")

    # -- Definisi vType --
    for vtype_id, accel, decel, length, maxspeed, sigma, color, _ in VEHICLE_TYPES:
        # Penyesuaian ketertiban (Sigma & Tau)
        actual_sigma = sigma if orderliness == "chaotic" else 0.1
        actual_tau   = 1.0 if orderliness == "orderly" else 0.5

        vtype = ET.SubElement(root, "vType")
        vtype.set("id",          vtype_id)
        vtype.set("accel",       str(accel))
        vtype.set("decel",       str(decel))
        vtype.set("length",      str(length))
        vtype.set("maxSpeed",    str(maxspeed))
        vtype.set("sigma",       str(actual_sigma))
        vtype.set("tau",         str(actual_tau))
        vtype.set("color",       color)
        vtype.set("guiShape",    GUI_SHAPE[vtype_id])
        vtype.set("speedFactor", "normc(1.0,0.1,0.8,1.2)")

    # -- Definisi route --
    route_ids: dict = {}
    for direction, moves in ROUTES.items():
        for move, (edge_in, edge_out) in moves.items():
            rid = f"r_{direction}_{move}"
            route_ids[(direction, move)] = rid
            route_elem = ET.SubElement(root, "route")
            route_elem.set("id",    rid)
            route_elem.set("edges", f"{edge_in} {edge_out}")

    # -- Generate kendaraan --
    veh_id   = 0
    vehicles = []

    for direction, intervals in TRAFFIC_VOLUME.items():
        straight_r, left_r, right_r = TURN_RATIO[direction]
        move_choices = ["straight", "left", "right"]
        move_weights = [straight_r, left_r, right_r]

        for t_start, t_end, vol_per_hour in intervals:
            interval_sec = t_end - t_start
            n_veh        = int(vol_per_hour * interval_sec / 3600)

            for _ in range(n_veh):
                depart   = round(random.uniform(t_start, t_end - 1), 2)
                move     = random.choices(move_choices, weights=move_weights)[0]
                vtype_id = random.choices(
                    [v[0] for v in VEHICLE_TYPES],
                    weights=[v[7] for v in VEHICLE_TYPES]
                )[0]
                vehicles.append((depart, direction, move, vtype_id))

    # Wajib diurutkan berdasarkan waktu keberangkatan
    vehicles.sort(key=lambda x: x[0])

    for depart, direction, move, vtype_id in vehicles:
        vehicle = ET.SubElement(root, "vehicle")
        vehicle.set("id",          f"v{veh_id}")
        vehicle.set("type",        vtype_id)
        vehicle.set("route",       route_ids[(direction, move)])
        vehicle.set("depart",      str(depart))
        vehicle.set("departLane",  "random")
        vehicle.set("departSpeed", "random")
        veh_id += 1

    write_xml(os.path.join(BUILD_DIR, "routes.rou.xml"), prettify(root))
    ok(f"Total kendaraan: {veh_id}")


# ---------------------------------------------------------
#  STEP 2.5 : Buat sensors.add.xml (Kamera Virtual)
# ---------------------------------------------------------
def build_sensors():
    console.print("[bold cyan][2.5/4][/bold cyan] Membuat file sensor E2 Detector (Kamera)...")
    content = """<?xml version="1.0" encoding="UTF-8"?>
<additional>
    <!-- Kamera Utara -->
    <laneAreaDetector id="cam_N_0" lane="north_in_2_0" pos="0" endPos="-1" freq="1" file="NUL"/>
    <laneAreaDetector id="cam_N_1" lane="north_in_2_1" pos="0" endPos="-1" freq="1" file="NUL"/>
    
    <!-- Kamera Selatan -->
    <laneAreaDetector id="cam_S_0" lane="south_in_2_0" pos="0" endPos="-1" freq="1" file="NUL"/>
    <laneAreaDetector id="cam_S_1" lane="south_in_2_1" pos="0" endPos="-1" freq="1" file="NUL"/>
    
    <!-- Kamera Barat -->
    <laneAreaDetector id="cam_W_0" lane="west_in_2_0" pos="0" endPos="-1" freq="1" file="NUL"/>
    <laneAreaDetector id="cam_W_1" lane="west_in_2_1" pos="0" endPos="-1" freq="1" file="NUL"/>
    
    <!-- Kamera Timur -->
    <laneAreaDetector id="cam_E_0" lane="east_in_2_0" pos="0" endPos="-1" freq="1" file="NUL"/>
    <laneAreaDetector id="cam_E_1" lane="east_in_2_1" pos="0" endPos="-1" freq="1" file="NUL"/>
</additional>
"""
    sensor_path = os.path.join(BUILD_DIR, "sensors.add.xml")
    with open(sensor_path, "w", encoding="utf-8") as f:
        f.write(content)
    ok(f"{sensor_path} berhasil dibuat")


# ---------------------------------------------------------
#  STEP 3 : Buat config.sumocfg
# ---------------------------------------------------------
def build_config():
    console.print("[bold cyan][2.5/3][/bold cyan] Membuat file konfigurasi SUMO...")
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">

    <input>
        <net-file value="net.net.xml"/>
        <route-files value="routes.rou.xml"/>
        <additional-files value="sensors.add.xml"/>
    </input>

    <time>
        <begin value="0"/>
        <end value="{SIM_DURATION}"/>
        <step-length value="0.1"/>
    </time>

    <processing>
        <ignore-route-errors value="true"/>
        <collision.action value="warn"/>
        <time-to-teleport value="120"/>
        <lanechange.duration value="3"/>
    </processing>

    <random_number>
        <seed value="{RANDOM_SEED}"/>
    </random_number>

    <gui_only>
        <gui-settings-file value="../{SRC_DIR}/view.view.xml"/>
        <start value="true"/>
        <quit-on-end value="true"/>
        <tracker-interval value="0.1"/>
    </gui_only>

    <output>
        <summary-output value="../output/summary.xml"/>
        <tripinfo-output value="../output/tripinfo.xml"/>
        <queue-output value="../output/queue.xml"/>
    </output>

</configuration>
"""
    os.makedirs("output", exist_ok=True)
    config_path = os.path.join(BUILD_DIR, "config.sumocfg")
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)
    ok(f"{config_path} berhasil dibuat")
    ok("folder output/ disiapkan")


# ---------------------------------------------------------
#  STEP 4 : Jalankan sumo-gui
# ---------------------------------------------------------
def run_sumo_gui():
    console.print("[bold cyan][3/3][/bold cyan] Menjalankan sumo-gui via TraCI...")
    sumo_gui_bin = find_exe("sumo-gui.exe")
    config_path = os.path.join(BUILD_DIR, "config.sumocfg")
    
    # Jalankan TraCI
    cmd = [sumo_gui_bin, "-c", config_path, "--delay", "50", "--start", "--quit-on-end"]
    console.print(f"  -> [dim]{' '.join(cmd)}[/dim]\n")
    
    traci.start(cmd)
    ok("TraCI dan sumo-gui diluncurkan!")
    console.print("  [green][STATUS][/green] Simulasi sedang berjalan. Lampu adaptif dikontrol secara dinamis.\n")
    
    # Dapatkan posisi pusat simpang yang sebenarnya (setelah offset di netconvert)
    try:
        cx, cy = traci.junction.getPosition("center")
    except:
        cx, cy = 400, 400 # fallback jika getPosition gagal
        
    # Buat 4 POI transparan untuk menampilkan text Timer di GUI
    # Posisi POI disesuaikan dengan 4 lajur sebelum simpang
    poi_positions = {
        "timer_N": (cx + 10, cy + 30),
        "timer_S": (cx - 10, cy - 30),
        "timer_W": (cx - 30, cy + 10),
        "timer_E": (cx + 30, cy - 10)
    }
    
    for poi_id, (px, py) in poi_positions.items():
        try:
            # Gunakan warna solid (Hitam) agar teks terlihat. Ukuran diset sekecil mungkin.
            traci.poi.add(poi_id, x=px, y=py, color=(0,0,0,255), poiType="0", width=0.1, height=0.1)
        except Exception as e:
            print(f"Error POI: {e}")

    # Inisialisasi pengontrol lampu adaptif berbasis Time Extension & Phase Skipping
    controller = TimeExtensionController(tls_id="center")

    try:
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            
            # Jalankan logika pengontrol adaptif pada setiap step
            controller.step(step_length=0.1)
            
            # Update teks gabungan untuk masing-masing arah
            cams = {
                "N": ["cam_N_0", "cam_N_1"],
                "S": ["cam_S_0", "cam_S_1"],
                "W": ["cam_W_0", "cam_W_1"],
                "E": ["cam_E_0", "cam_E_1"]
            }
            
            for poi_id in poi_positions.keys():
                dir_key = poi_id.split("_")[1] # Ambil huruf N, S, W, atau E
                
                # Baca waktu sisa/estimasi langsung dari controller kita
                timer_text = controller.get_timer_text(dir_key)
                
                # Hitung antrean E2
                try:
                    count = sum(traci.lanearea.getJamLengthVehicle(cam) for cam in cams[dir_key])
                except traci.exceptions.TraCIException:
                    count = 0
                
                # Tampilkan rapi dalam satu baris
                combined_text = f"[{timer_text} | Queue: {count}]"
                traci.poi.setType(poi_id, combined_text)
                
    except (traci.exceptions.FatalTraCIError, KeyboardInterrupt, SystemExit):
        console.print("  [yellow][INFO][/yellow] Simulasi ditutup oleh pengguna.")
    finally:
        try:
            traci.close()
        except:
            pass


# ---------------------------------------------------------
#  MAIN
# ---------------------------------------------------------
if __name__ == "__main__":
    try:

        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        os.makedirs(BUILD_DIR, exist_ok=True)

        # 1. Pilih kemacetan, mode lampu, & ketertiban via CLI
        crowded_list, tls_layout, orderliness = get_crowded_from_cli()
        set_traffic_volumes(crowded_list)

        # 2. Jalankan proses simulasi
        build_network(tls_layout)
        build_routes(orderliness)
        build_sensors()
        build_config()
        run_sumo_gui()
    except KeyboardInterrupt:
        console.print("\n\n[bold yellow][INFO][/bold yellow] Simulasi dibatalkan oleh pengguna (Ctrl+C).")
        sys.exit(0)
