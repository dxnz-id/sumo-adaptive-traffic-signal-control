import traci
from rich.console import Console

# Inisialisasi Console untuk log premium
console = Console()

class TimeExtensionController:
    def __init__(self, tls_id="center", min_green=10.0, max_green=50.0, extension_time=3.0, yellow_duration=4.0):
        self.tls_id = tls_id
        self.min_green = min_green
        self.max_green = max_green
        self.extension_time = extension_time
        self.yellow_duration = yellow_duration
        
        # State tracking
        self.elapsed_green = 0.0
        self.elapsed_yellow = 0.0
        
        self.is_yellow_phase = False
        self.current_direction = "N"  # Mulai dari Utara
        
        # Pelacakan durasi tunggu awal lampu merah
        self.initial_red_wait = {"N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0}
        
        # Status kesehatan kamera per arah
        self.cams_healthy = {"N": True, "S": True, "E": True, "W": True}
        
        # Mapping arah ke fase lampu hijau & kuning (Mode Tunggal / Incoming)
        self.dir_phases = {
            "N": {"green": 0, "yellow": 1},
            "E": {"green": 2, "yellow": 3},
            "S": {"green": 4, "yellow": 5},
            "W": {"green": 6, "yellow": 7}
        }
        
        self.cams = {
            "N": ["cam_N_0", "cam_N_1"],
            "S": ["cam_S_0", "cam_S_1"],
            "W": ["cam_W_0", "cam_W_1"],
            "E": ["cam_E_0", "cam_E_1"]
        }
        
        # Inisialisasi awal: paksa SUMO ke fase hijau Utara dan deaktifkan timer internal SUMO
        try:
            traci.trafficlight.setPhase(self.tls_id, self.dir_phases[self.current_direction]["green"])
            traci.trafficlight.setPhaseDuration(self.tls_id, 9999.0)
        except Exception as e:
            console.print(f"[bold yellow][WARNING][/bold yellow] Gagal inisialisasi awal TLS: {e}")
        
    def step(self, step_length=0.1):
        """Dipanggil setiap tick 0.1s di loop utama main.py"""
        # 1. Jika sedang fase Kuning, tunggu sampai durasi kuning selesai
        if self.is_yellow_phase:
            self.elapsed_yellow += step_length
            if self.elapsed_yellow >= self.yellow_duration:
                self.is_yellow_phase = False
                self.elapsed_yellow = 0.0
                self.elapsed_green = 0.0
                
                # Tentukan arah hijau berikutnya (Phase Skipping)
                next_dir = self.select_next_direction()
                
                # Arah saat ini (sebelumnya kuning) akan bertransisi ke MERAH
                old_dir = self.current_direction
                self.current_direction = next_dir
                self.initial_red_wait[old_dir] = self.calculate_estimated_wait(old_dir)
                
                traci.trafficlight.setPhase(self.tls_id, self.dir_phases[next_dir]["green"])
                traci.trafficlight.setPhaseDuration(self.tls_id, 9999.0) # Matikan timer internal SUMO
                console.print(f"[bold green][GREEN][/bold green] Lampu [bold cyan]HIJAU[/bold cyan] menyala di arah [bold magenta]{next_dir}[/bold magenta] (min_green={self.min_green}s)")
            return

        # 2. Jika sedang fase Hijau, jalankan logika Time Extension
        self.elapsed_green += step_length
        
        # Baca deteksi kendaraan aktif di arah hijau saat ini
        vehicles_detected = self.get_active_vehicles(self.current_direction)
        
        # Logika Gap-out & Max-out
        if self.elapsed_green >= self.min_green:
            # GAP-OUT: Jika kosong dan kamera sehat
            if vehicles_detected == 0 and self.cams_healthy[self.current_direction]:
                console.print(f"[bold yellow][GAP-OUT][/bold yellow] Celah kosong terdeteksi di arah [bold magenta]{self.current_direction}[/bold magenta] setelah [bold cyan]{self.elapsed_green:.1f}s[/bold cyan]. Pindah ke Kuning.")
                self.trigger_yellow()
            # MAX-OUT: Jika sudah mencapai batas waktu maksimal
            elif self.elapsed_green >= self.max_green:
                console.print(f"[bold red][MAX-OUT][/bold red] Batas maksimal hijau arah [bold magenta]{self.current_direction}[/bold magenta] ([bold cyan]{self.max_green}s[/bold cyan]) tercapai. Pindah ke Kuning.")
                self.trigger_yellow()
                
    def trigger_yellow(self):
        self.is_yellow_phase = True
        self.elapsed_yellow = 0.0
        traci.trafficlight.setPhase(self.tls_id, self.dir_phases[self.current_direction]["yellow"])
        traci.trafficlight.setPhaseDuration(self.tls_id, 9999.0) # Matikan timer internal SUMO
        
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

    def select_next_direction(self):
        """Mencari arah hijau berikutnya dengan fitur Phase Skipping"""
        sequence = ["N", "E", "S", "W"]
        curr_idx = sequence.index(self.current_direction)
        
        # Cek arah berikutnya dalam urutan memutar
        for i in range(1, 5):
            next_idx = (curr_idx + i) % 4
            candidate_dir = sequence[next_idx]
            
            queue_count = self.get_queue_count(candidate_dir)
            
            if queue_count > 0:
                # Ada kendaraan! Berikan hijau
                if i > 1:
                    skipped = [sequence[(curr_idx + j) % 4] for j in range(1, i)]
                    console.print(f"[bold blue][SKIP][/bold blue] Phase Skipping aktif! Melewati arah [bold red]{', '.join(skipped)}[/bold red] karena kosong.")
                return candidate_dir
                
        # Jika semua arah lain kosong melompati, tetap di arah saat ini
        return self.current_direction

    def calculate_estimated_wait(self, direction):
        """Menghitung estimasi sisa waktu tunggu untuk arah lampu merah secara riil"""
        sequence = ["N", "E", "S", "W"]
        curr_idx = sequence.index(self.current_direction)
        target_idx = sequence.index(direction)
        
        steps_away = (target_idx - curr_idx) % 4
        estimated_wait = 0.0
        
        # Sisa waktu dari fase aktif saat ini (hijau/kuning)
        if self.is_yellow_phase:
            estimated_wait += max(0.0, self.yellow_duration - self.elapsed_yellow)
        else:
            active_cams = self.cams[self.current_direction]
            try:
                vehicles = sum(traci.lanearea.getLastStepVehicleNumber(cam) for cam in active_cams)
            except:
                vehicles = 0
                
            if self.elapsed_green < self.min_green:
                estimated_wait += (self.min_green - self.elapsed_green) + self.yellow_duration
            elif vehicles > 0:
                estimated_wait += max(0.0, self.max_green - self.elapsed_green) + self.yellow_duration
            else:
                estimated_wait += self.yellow_duration # Segera kuning
                
        # Ditambah min_green + kuning untuk arah-arah di antaranya yang memiliki antrean (tidak di-skip)
        for i in range(1, steps_away):
            intermediate_idx = (curr_idx + i) % 4
            intermediate_dir = sequence[intermediate_idx]
            
            if self.get_queue_count(intermediate_dir) > 0:
                estimated_wait += self.min_green + self.yellow_duration
                
        return estimated_wait

    def get_timer_text(self, direction):
        """Mengestimasi sisa waktu secara dinamis untuk ditampilkan di GUI"""
        # 1. Jika arah tersebut sedang aktif (Hijau atau Kuning)
        if self.current_direction == direction:
            if self.is_yellow_phase:
                rem = max(0.0, self.yellow_duration - self.elapsed_yellow)
                return f"Yellow: {int(rem)}s/{int(self.yellow_duration)}s"
            else:
                # Tampilkan sisa waktu ke batas maksimal lampu hijau
                rem = max(0.0, self.max_green - self.elapsed_green)
                return f"Green: {int(rem)}s/{int(self.max_green)}s"
        
        # 2. Arah tersebut sedang Merah.
        rem = self.calculate_estimated_wait(direction)
        total = self.initial_red_wait.get(direction, 0.0)
        
        # Failsafe visual: Jaga agar total tidak lebih kecil dari sisa waktu (rem)
        if rem > total:
            self.initial_red_wait[direction] = rem
            total = rem
            
        return f"Red: {int(rem)}s/{int(total)}s"
