"""
🚥 SUMO ADAPTIVE TRAFFIC LIGHT CONTROLLER 🚥
Modul Jembatan Antara Simulator SUMO (TraCI) dan Algoritma Cerdas
===================================================================
Modul ini bertindak sebagai driver/controller yang membaca kamera sensor E2
di SUMO, lalu mendelegasikan keputusan kendali ke TimeExtensionAlgorithm.
"""

import traci
from rich.console import Console
from .algorithm import TimeExtensionAlgorithm

console = Console()

class TimeExtensionController:
    def __init__(self, tls_id="center", min_green=10.0, max_green=50.0, yellow_duration=4.0):
        self.tls_id = tls_id
        
        # Instansiasi Mesin Logika Algoritma Murni
        self.algorithm = TimeExtensionAlgorithm(
            min_green=min_green,
            max_green=max_green,
            yellow_duration=yellow_duration
        )
        
        # Status kesehatan kamera sensor E2 per arah
        self.cams_healthy = {"N": True, "S": True, "E": True, "W": True}
        
        # Konfigurasi Sumbu Sisi Ganda
        self.counterpart = {"N": "S", "S": "N", "E": "W", "W": "E"}
        self.is_ganda = False
        
        # Pendeteksian dinamis program TLS (Tunggal vs Ganda) via TraCI
        try:
            logics = traci.trafficlight.getAllProgramLogics(self.tls_id)
            if logics:
                num_phases = len(logics[0].phases)
                if num_phases <= 4:
                    self.is_ganda = True
        except Exception as e:
            console.print(f"[bold yellow][WARNING][/bold yellow] Gagal deteksi program TLS secara dinamis: {e}")
            
        if self.is_ganda:
            # Mode Ganda (opposites): N-S satu fase, E-W satu fase
            self.dir_phases = {
                "N": {"green": 0, "yellow": 1},
                "S": {"green": 0, "yellow": 1},
                "E": {"green": 2, "yellow": 3},
                "W": {"green": 2, "yellow": 3}
            }
            console.print("  [STATUS] Deteksi TLS: Mode Ganda (opposites) terdeteksi otomatis.")
        else:
            # Mode Tunggal (incoming): tiap arah independen
            self.dir_phases = {
                "N": {"green": 0, "yellow": 1},
                "E": {"green": 2, "yellow": 3},
                "S": {"green": 4, "yellow": 5},
                "W": {"green": 6, "yellow": 7}
            }
            console.print("  [STATUS] Deteksi TLS: Mode Tunggal (incoming) terdeteksi otomatis.")
            
        self.cams = {
            "N": ["cam_N_0", "cam_N_1"],
            "S": ["cam_S_0", "cam_S_1"],
            "W": ["cam_W_0", "cam_W_1"],
            "E": ["cam_E_0", "cam_E_1"]
        }
        
        # Inisialisasi awal: paksa SUMO ke fase hijau awal (Utara)
        try:
            traci.trafficlight.setPhase(self.tls_id, self.dir_phases[self.algorithm.current_direction]["green"])
            traci.trafficlight.setPhaseDuration(self.tls_id, 9999.0) # Matikan timer internal SUMO
        except Exception as e:
            console.print(f"[bold yellow][WARNING][/bold yellow] Gagal inisialisasi awal TLS: {e}")
            
        # Dapatkan posisi simpang untuk meletakkan POI teks timer di layar SUMO
        try:
            cx, cy = traci.junction.getPosition(self.tls_id)
        except:
            cx, cy = 400.0, 400.0
            
        self.poi_positions = {
            "timer_N": (cx + 10.0, cy + 30.0),
            "timer_S": (cx - 10.0, cy - 30.0),
            "timer_W": (cx - 30.0, cy + 10.0),
            "timer_E": (cx + 30.0, cy - 10.0)
        }
        
        # Buat POI transparan untuk menampung visualisasi teks timer di GUI
        for poi_id, (px, py) in self.poi_positions.items():
            try:
                traci.poi.add(poi_id, x=px, y=py, color=(0,0,0,255), poiType="0", width=0.1, height=0.1)
            except Exception as e:
                pass
        
    def step(self, step_length=0.1):
        """Dipanggil setiap tick 0.1s di loop utama main.py"""
        # Pembaruan visual teks POI di GUI secara otomatis
        self.update_gui_poiss()
        
        # 1. Jika sedang dalam fase transisi Kuning
        if self.algorithm.is_yellow_phase:
            self.algorithm.elapsed_yellow += step_length
            if self.algorithm.elapsed_yellow >= self.algorithm.yellow_duration:
                self.algorithm.is_yellow_phase = False
                self.algorithm.elapsed_yellow = 0.0
                self.algorithm.elapsed_green = 0.0
                
                # Tentukan arah hijau berikutnya dari mesin keputusan algoritma
                next_dir = self.algorithm.select_next_direction(
                    self.is_ganda, self.dir_phases, self.counterpart, self.get_queue_count
                )
                
                old_dir = self.algorithm.current_direction
                self.algorithm.current_direction = next_dir
                
                # Hitung dan simpan estimasi tunggu awal untuk arah yang baru saja berubah merah
                self.algorithm.initial_red_wait[old_dir] = self.algorithm.calculate_estimated_wait(
                    old_dir, self.is_ganda, self.dir_phases, self.counterpart,
                    self.get_active_vehicles, self.get_queue_count
                )
                
                # Perintahkan SUMO ke fase hijau baru
                traci.trafficlight.setPhase(self.tls_id, self.dir_phases[next_dir]["green"])
                traci.trafficlight.setPhaseDuration(self.tls_id, 9999.0) # Matikan timer internal SUMO
                console.print(f"[bold green][GREEN][/bold green] Lampu [bold cyan]HIJAU[/bold cyan] menyala di arah [bold magenta]{next_dir}[/bold magenta] (min_green={self.algorithm.min_green}s)")
            return

        # 2. Jika sedang dalam fase Hijau, minta keputusan Gap-out/Max-out ke algoritma
        vehicles_detected = self.get_active_vehicles(self.algorithm.current_direction)
        if self.is_ganda:
            counter_detected = self.get_active_vehicles(self.counterpart[self.algorithm.current_direction])
            if vehicles_detected == 999 or counter_detected == 999:
                vehicles_detected = 999
            else:
                vehicles_detected += counter_detected
                
        is_healthy = self.cams_healthy[self.algorithm.current_direction]
        if self.is_ganda:
            is_healthy = is_healthy and self.cams_healthy[self.counterpart[self.algorithm.current_direction]]
            
        should_yellow, reason = self.algorithm.decide_yellow_transition(
            step_length, vehicles_detected, is_healthy
        )
        
        if should_yellow:
            # Pindah ke kuning di program utama & simulator
            self.algorithm.is_yellow_phase = True
            self.algorithm.elapsed_yellow = 0.0
            
            traci.trafficlight.setPhase(self.tls_id, self.dir_phases[self.algorithm.current_direction]["yellow"])
            traci.trafficlight.setPhaseDuration(self.tls_id, 9999.0) # Matikan timer internal SUMO
            
            # Cari prefix warna cetak konsol
            prefix = "[bold red][MAX-OUT][/bold red]" if "MAX" in reason else "[bold yellow][GAP-OUT][/bold yellow]"
            console.print(f"{prefix} Pindah ke Kuning arah [bold magenta]{self.algorithm.current_direction}[/bold magenta] karena {reason}.")

    def get_active_vehicles(self, direction):
        """Membaca jumlah kendaraan aktif dengan penanganan failsafe"""
        if not self.cams_healthy[direction]:
            return 999  # Trik failsafe: asumsikan ramai
            
        try:
            active_cams = self.cams[direction]
            return sum(traci.lanearea.getLastStepVehicleNumber(cam) for cam in active_cams)
        except traci.exceptions.TraCIException:
            console.print(f"[bold red][FAILSAFE][/bold red] Kamera arah '[bold yellow]{direction}[/bold yellow]' terdeteksi ERROR! Mengaktifkan fallback fixed-time.")
            self.cams_healthy[direction] = False
            return 999

    def get_queue_count(self, direction):
        """Membaca panjang antrean dengan penanganan failsafe"""
        if not self.cams_healthy[direction]:
            return 999  # Trik failsafe
            
        try:
            candidate_cams = self.cams[direction]
            return sum(traci.lanearea.getJamLengthVehicle(cam) for cam in candidate_cams)
        except traci.exceptions.TraCIException:
            console.print(f"[bold red][FAILSAFE][/bold red] Kamera arah '[bold yellow]{direction}[/bold yellow]' terdeteksi ERROR! Mengaktifkan fallback fixed-time.")
            self.cams_healthy[direction] = False
            return 999

    def update_gui_poiss(self):
        """Update teks timer dan antrean di GUI secara otomatis"""
        for poi_id in self.poi_positions.keys():
            dir_key = poi_id.split("_")[1] # N, S, W, atau E
            
            timer_text = self.algorithm.get_timer_text(
                dir_key, self.is_ganda, self.dir_phases, self.counterpart,
                self.get_active_vehicles, self.get_queue_count
            )
            
            try:
                if not self.cams_healthy[dir_key]:
                    count = 0
                else:
                    count = sum(traci.lanearea.getJamLengthVehicle(cam) for cam in self.cams[dir_key])
            except:
                count = 0
                
            combined_text = f"[{timer_text} | Queue: {count}]"
            try:
                traci.poi.setType(poi_id, combined_text)
            except:
                pass
