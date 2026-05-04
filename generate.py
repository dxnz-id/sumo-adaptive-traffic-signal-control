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
random.seed(RANDOM_SEED)

# Volume kendaraan per arah per interval (kend/jam)
# Format: {arah: [(mulai_det, selesai_det, volume_per_jam), ...]}
TRAFFIC_VOLUME = {
    "north": [
        (   0,  900, 180),   # normal pagi
        ( 900, 1800, 400),   # jam sibuk pagi
        (1800, 2700, 220),   # normal siang
        (2700, 3600, 350),   # jam sibuk sore
    ],
    "south": [
        (   0,  900, 160),
        ( 900, 1800, 350),
        (1800, 2700, 200),
        (2700, 3600, 380),
    ],
    "west": [
        (   0,  900, 120),
        ( 900, 1800, 280),
        (1800, 2700, 150),
        (2700, 3600, 300),
    ],
    "east": [
        (   0,  900, 130),
        ( 900, 1800, 260),
        (1800, 2700, 160),
        (2700, 3600, 290),
    ],
}

# Proporsi manuver per arah: (lurus, kiri, kanan)
TURN_RATIO = {
    "north": (0.55, 0.25, 0.20),
    "south": (0.55, 0.20, 0.25),
    "west":  (0.50, 0.25, 0.25),
    "east":  (0.50, 0.25, 0.25),
}

# Rute berdasarkan arah dan manuver: (edge_masuk, edge_keluar)
ROUTES = {
    "north": {
        "straight": ("north_in", "south_out"),
        "left":     ("north_in", "east_out"),
        "right":    ("north_in", "west_out"),
    },
    "south": {
        "straight": ("south_in", "north_out"),
        "left":     ("south_in", "west_out"),
        "right":    ("south_in", "east_out"),
    },
    "west": {
        "straight": ("west_in", "east_out"),
        "left":     ("west_in", "north_out"),
        "right":    ("west_in", "south_out"),
    },
    "east": {
        "straight": ("east_in", "west_out"),
        "left":     ("east_in", "south_out"),
        "right":    ("east_in", "north_out"),
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
        "--node-files",            "nodes.nod.xml",
        "--edge-files",            "edges.edg.xml",
        "--connection-files",      "connections.con.xml",
        "--output-file",           "net.net.xml",
        "--tls.default-type",      "static",
        "--tls.green.time",        "35",
        "--tls.yellow.time",       "4",
        "--tls.red.time",          "2",
        "--no-turnarounds",        "true",
        "--junctions.corner-detail", "5",
        "--lefthand",              "false",
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

    write_xml("routes.rou.xml", prettify(root))
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
        <start value="true"/>
        <quit-on-end value="false"/>
        <tracker-interval value="0.1"/>
    </gui_only>

    <output>
        <summary-output value="output/summary.xml"/>
        <tripinfo-output value="output/tripinfo.xml"/>
        <queue-output value="output/queue.xml"/>
    </output>

</configuration>
"""
    os.makedirs("output", exist_ok=True)
    with open("config.sumocfg", "w", encoding="utf-8") as f:
        f.write(content)
    ok("config.sumocfg berhasil dibuat")
    ok("folder output/ disiapkan")


# ---------------------------------------------------------
#  STEP 4 : Jalankan sumo-gui
# ---------------------------------------------------------
def run_sumo_gui():
    print("\n[3/3] Menjalankan sumo-gui ...")
    sumo_gui_bin = find_exe("sumo-gui.exe")
    cmd = [sumo_gui_bin, "-c", "config.sumocfg", "--delay", "50"]
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

    build_network()
    build_routes()
    build_config()
    run_sumo_gui()
