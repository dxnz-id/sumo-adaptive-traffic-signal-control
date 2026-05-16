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
    """Mengambil input kemacetan dari terminal."""
    print("\n" + "="*40)
    print("      PENGATURAN KEMACETAN")
    print("="*40)
    print("Pilih arah yang ingin dibuat SANGAT RAMAI:")
    print(" [n] North / Utara")
    print(" [s] South / Selatan")
    print(" [w] West  / Barat")
    print(" [e] East  / Timur")
    print("-" * 40)
    print("Petunjuk: Ketik hurufnya saja (misal: 'n' atau 's,e')")
    print("          Kosongkan (langsung ENTER) untuk NORMAL.")
    
    ans = input("\nMasukkan pilihan: ").lower().replace(" ", "")
    if not ans:
        print("  >> Mode: NORMAL (Semua arah lurus)")
        return []
    
    mapping = {'n': 'north', 's': 'south', 'w': 'west', 'e': 'east'}
    selected = []
    
    parts = ans.split(",")
    for p in parts:
        # Cek shortcut (n, s, w, e)
        if p in mapping:
            selected.append(mapping[p])
        # Cek nama lengkap (north, south, etc)
        elif p in mapping.values():
            selected.append(p)
            
    if selected:
        print(f"  >> Mode RAMAI pada arah: {', '.join([s.capitalize() for s in selected])}")
    else:
        print("  >> Pilihan tidak dikenali, menggunakan mode NORMAL.")
        
    return selected

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
        "right":    ("west_in_1 west_in_2", "north_out_1 north_out_2"),
        "left":     ("west_in_1", "slip_wn north_out_2"),
    },
    "east": {
        "straight": ("east_in_1 east_in_2", "west_out_1 west_out_2"),
        "right":    ("east_in_1 east_in_2", "south_out_1 south_out_2"),
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
    print(f"  [OK] {msg}")


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
def build_network():
    print("\n[1/3] Membuat jaringan jalan dengan netconvert ...")
    netconvert_bin = find_exe("netconvert.exe")
    cmd = [
        netconvert_bin,
        "--node-files",            os.path.join(SRC_DIR, "nodes.nod.xml"),
        "--edge-files",            os.path.join(SRC_DIR, "edges.edg.xml"),
        "--connection-files",      os.path.join(SRC_DIR, "connections.con.xml"),
        "--output-file",           os.path.join(BUILD_DIR, "net.net.xml"),
        "--tls.default-type",      "static",
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
        print("ERROR netconvert:\n", result.stderr)
        sys.exit(1)
    ok("net.net.xml berhasil dibuat")


# ---------------------------------------------------------
#  STEP 2 : Buat routes.rou.xml
# ---------------------------------------------------------
def build_routes():
    print("\n[2/3] Membuat rute kendaraan dinamis ...")

    root = ET.Element("routes")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("xsi:noNamespaceSchemaLocation",
             "http://sumo.dlr.de/xsd/routes_file.xsd")

    # -- Definisi vType --
    for vtype_id, accel, decel, length, maxspeed, sigma, color, _ in VEHICLE_TYPES:
        vtype = ET.SubElement(root, "vType")
        vtype.set("id",          vtype_id)
        vtype.set("accel",       str(accel))
        vtype.set("decel",       str(decel))
        vtype.set("length",      str(length))
        vtype.set("maxSpeed",    str(maxspeed))
        vtype.set("sigma",       str(sigma))
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
#  STEP 3 : Buat config.sumocfg
# ---------------------------------------------------------
def build_config():
    print("\n[2.5/3] Membuat file konfigurasi SUMO ...")
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">

    <input>
        <net-file value="net.net.xml"/>
        <route-files value="routes.rou.xml"/>
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
        <quit-on-end value="false"/>
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
    print("\n[3/3] Menjalankan sumo-gui ...")
    sumo_gui_bin = find_exe("sumo-gui.exe")
    config_path = os.path.join(BUILD_DIR, "config.sumocfg")
    cmd = [sumo_gui_bin, "-c", config_path, "--delay", "50"]
    print(f"  -> {' '.join(cmd)}\n")
    subprocess.Popen(cmd)
    ok("sumo-gui diluncurkan!")
    print("\n" + "=" * 50)
    print("  Tekan Play [>] di sumo-gui untuk memulai simulasi")
    print("=" * 50)


# ---------------------------------------------------------
#  MAIN
# ---------------------------------------------------------
if __name__ == "__main__":
    print("=" * 50)
    print("  Simulasi Perempatan 4 Arah - SUMO")
    print("=" * 50)

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(BUILD_DIR, exist_ok=True)

    # 1. Pilih kemacetan via CLI
    crowded_list = get_crowded_from_cli()
    set_traffic_volumes(crowded_list)

    # 2. Jalankan proses simulasi
    build_network()
    build_routes()
    build_config()
    run_sumo_gui()
