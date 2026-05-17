import os
import random

# ---------------------------------------------------------
#  JALUR DIREKTORI & UTILITY
# ---------------------------------------------------------
BUILD_DIR = "map/build"    # Folder untuk berkas hasil generator otomatis
INPUT_DIR = "map"          # Folder untuk file sumber XML statis (Infrastruktur)

# ---------------------------------------------------------
#  PARAMETER SIMULASI
# ---------------------------------------------------------
SIM_DURATION = 3600        # detik (1 jam simulasi)
RANDOM_SEED  = 42
random.seed(RANDOM_SEED)

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
        "right":    ("west_in_1 west_in_2", "south_out_1 south_out_2"),
        "left":     ("west_in_1", "slip_wn north_out_2"),
    },
    "east": {
        "straight": ("east_in_1 east_in_2", "west_out_1 west_out_2"),
        "right":    ("east_in_1 east_in_2", "north_out_1 north_out_2"),
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

# Volume Dasar (Akan diupdate via CLI/get_crowded_from_cli)
TRAFFIC_VOLUME = {
    "north": [], "south": [], "west": [], "east": []
}

def set_traffic_volumes(crowded_directions):
    """Menentukan volume lalu lintas dinamis berdasarkan masukan CLI."""
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
