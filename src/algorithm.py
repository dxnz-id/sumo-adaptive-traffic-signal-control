"""
🧠 SUMO ADAPTIVE TRAFFIC LIGHT ALGORITHM 🧠
Modul Murni Logika & Pengambilan Keputusan Kendali Lampu Adaptif
===================================================================
Modul ini murni berisi matematika, pelacakan state keputusan,
serta logika Phase Skipping & Time Extension tanpa ketergantungan pada TraCI.
"""

from rich.console import Console

console = Console()

class TimeExtensionAlgorithm:
    def __init__(self, min_green=10.0, max_green=50.0, yellow_duration=4.0):
        self.min_green = min_green
        self.max_green = max_green
        self.yellow_duration = yellow_duration
        
        # State tracking keputusan
        self.elapsed_green = 0.0
        self.elapsed_yellow = 0.0
        self.is_yellow_phase = False
        self.current_direction = "N"  # Mulai dari Utara
        
        # Pelacakan durasi tunggu awal lampu merah
        self.initial_red_wait = {"N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0}

    def decide_yellow_transition(self, step_length, vehicles_detected, is_healthy):
        """
        Menentukan apakah lampu hijau saat ini harus bertransisi ke kuning
        berdasarkan logika Gap-out (celah kosong) dan Max-out (batas maksimal).
        """
        self.elapsed_green += step_length
        
        if self.elapsed_green >= self.min_green:
            # GAP-OUT: Jika kosong dan kamera sehat
            if vehicles_detected == 0 and is_healthy:
                return True, f"GAP-OUT (Celah kosong setelah {self.elapsed_green:.1f}s)"
            # MAX-OUT: Jika sudah mencapai batas waktu maksimal
            elif self.elapsed_green >= self.max_green:
                return True, f"MAX-OUT (Batas maksimal hijau {self.max_green}s tercapai)"
                
        return False, "KEEP"

    def select_next_direction(self, is_ganda, dir_phases, counterpart, get_queue_fn):
        """
        Mencari arah hijau berikutnya dengan logika Phase Skipping memutar.
        """
        sequence = ["N", "E", "S", "W"]
        curr_idx = sequence.index(self.current_direction)
        
        # Cek arah berikutnya dalam urutan memutar
        for i in range(1, 5):
            next_idx = (curr_idx + i) % 4
            candidate_dir = sequence[next_idx]
            
            # Jika mode Ganda, lewati arah yang se-fase dengan arah saat ini
            if is_ganda and dir_phases[candidate_dir]["green"] == dir_phases[self.current_direction]["green"]:
                continue
                
            queue_count = get_queue_fn(candidate_dir)
            if is_ganda:
                queue_count += get_queue_fn(counterpart[candidate_dir])
            
            if queue_count > 0:
                # Ada kendaraan! Berikan hijau
                if i > 1:
                    skipped = [sequence[(curr_idx + j) % 4] for j in range(1, i)]
                    # Di mode ganda, jangan tampilkan skip jika arah tersebut se-fase dengan candidate_dir atau current_direction
                    if is_ganda:
                        skipped = [d for d in skipped if dir_phases[d]["green"] != dir_phases[self.current_direction]["green"] and dir_phases[d]["green"] != dir_phases[candidate_dir]["green"]]
                    if skipped:
                        console.print(f"[bold blue][SKIP][/bold blue] Phase Skipping aktif! Melewati arah [bold red]{', '.join(skipped)}[/bold red] karena kosong.")
                return candidate_dir
                
        # Jika semua arah lain kosong melompati, tetap di arah saat ini
        return self.current_direction

    def calculate_estimated_wait(self, direction, is_ganda, dir_phases, counterpart, get_vehicles_fn, get_queue_fn):
        """
        Menghitung estimasi sisa waktu tunggu untuk arah lampu merah secara riil.
        """
        if is_ganda:
            # Di mode Ganda, jika target searah/se-fase dengan arah aktif saat ini, sisanya 0
            if dir_phases[direction]["green"] == dir_phases[self.current_direction]["green"]:
                return 0.0
                
            # Jika berbeda fase, waktu tunggu adalah sisa waktu dari fase aktif saat ini
            estimated_wait = 0.0
            if self.is_yellow_phase:
                estimated_wait += max(0.0, self.yellow_duration - self.elapsed_yellow)
            else:
                active_cams = get_vehicles_fn(self.current_direction) + get_vehicles_fn(counterpart[self.current_direction])
                # get_vehicles_fn di controller mengembalikan count, sesuaikan penerimaannya
                vehicles = active_cams
                
                if self.elapsed_green < self.min_green:
                    estimated_wait += (self.min_green - self.elapsed_green) + self.yellow_duration
                elif vehicles > 0:
                    estimated_wait += max(0.0, self.max_green - self.elapsed_green) + self.yellow_duration
                else:
                    estimated_wait += self.yellow_duration
            return estimated_wait

        sequence = ["N", "E", "S", "W"]
        curr_idx = sequence.index(self.current_direction)
        target_idx = sequence.index(direction)
        
        steps_away = (target_idx - curr_idx) % 4
        estimated_wait = 0.0
        
        # Sisa waktu dari fase aktif saat ini (hijau/kuning)
        if self.is_yellow_phase:
            estimated_wait += max(0.0, self.yellow_duration - self.elapsed_yellow)
        else:
            vehicles = get_vehicles_fn(self.current_direction)
                
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
            
            if get_queue_fn(intermediate_dir) > 0:
                estimated_wait += self.min_green + self.yellow_duration
                
        return estimated_wait

    def get_timer_text(self, direction, is_ganda, dir_phases, counterpart, get_vehicles_fn, get_queue_fn):
        """
        Mengestimasi sisa waktu secara dinamis untuk ditampilkan di GUI.
        """
        # 1. Jika arah tersebut sedang aktif (Hijau atau Kuning)
        is_active = (self.current_direction == direction)
        if is_ganda:
            is_active = (dir_phases[direction]["green"] == dir_phases[self.current_direction]["green"])
            
        if is_active:
            if self.is_yellow_phase:
                rem = max(0.0, self.yellow_duration - self.elapsed_yellow)
                return f"Yellow: {int(rem)}s/{int(self.yellow_duration)}s"
            else:
                # Tampilkan sisa waktu ke batas maksimal lampu hijau
                rem = max(0.0, self.max_green - self.elapsed_green)
                return f"Green: {int(rem)}s/{int(self.max_green)}s"
        
        # 2. Arah tersebut sedang Merah.
        rem = self.calculate_estimated_wait(direction, is_ganda, dir_phases, counterpart, get_vehicles_fn, get_queue_fn)
        total = self.initial_red_wait.get(direction, 0.0)
        
        # Failsafe visual: Jaga agar total tidak lebih kecil dari sisa waktu (rem)
        if rem > total:
            self.initial_red_wait[direction] = rem
            total = rem
            
        return f"Red: {int(rem)}s/{int(total)}s"
