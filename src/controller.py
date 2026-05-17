"""
SUMO ADAPTIVE TRAFFIC LIGHT CONTROLLER
Driver Bridge Between SUMO Simulator (TraCI) and Decision Logic
===================================================================
This module acts as the driver/controller that reads E2 detector cameras
in SUMO and delegates adaptive traffic light decision-making to TimeExtensionAlgorithm.
"""

import traci
from rich.console import Console
from .algorithm import TimeExtensionAlgorithm

console = Console()

class TimeExtensionController:
    def __init__(self, tls_id="center", min_green=10.0, max_green=50.0, yellow_duration=4.0):
        self.tls_id = tls_id
        
        # Instantiate pure logic decision algorithm
        self.algorithm = TimeExtensionAlgorithm(
            min_green=min_green,
            max_green=max_green,
            yellow_duration=yellow_duration
        )
        
        # Camera sensor health trackers per direction
        self.cams_healthy = {"N": True, "S": True, "E": True, "W": True}
        
        # Dual opposites directions mapping
        self.counterpart = {"N": "S", "S": "N", "E": "W", "W": "E"}
        self.is_dual_mode = False
        
        # Dynamic TLS layout detection (Single vs Dual) via TraCI
        try:
            logics = traci.trafficlight.getAllProgramLogics(self.tls_id)
            if logics:
                num_phases = len(logics[0].phases)
                if num_phases <= 4:
                    self.is_dual_mode = True
        except Exception as e:
            console.print(f"[bold yellow][WARNING][/bold yellow] Failed to dynamically detect TLS program: {e}")
            
        if self.is_dual_mode:
            # Dual mode (opposites): N-S share one phase, E-W share one phase
            self.direction_phases = {
                "N": {"green": 0, "yellow": 1},
                "S": {"green": 0, "yellow": 1},
                "E": {"green": 2, "yellow": 3},
                "W": {"green": 2, "yellow": 3}
            }
            console.print("  [STATUS] TLS Detection: Dual mode (opposites) automatically detected.")
        else:
            # Single mode (incoming): each direction operates independently
            self.direction_phases = {
                "N": {"green": 0, "yellow": 1},
                "E": {"green": 2, "yellow": 3},
                "S": {"green": 4, "yellow": 5},
                "W": {"green": 6, "yellow": 7}
            }
            console.print("  [STATUS] TLS Detection: Single mode (incoming) automatically detected.")
            
        self.cams = {
            "N": ["cam_N_0", "cam_N_1"],
            "S": ["cam_S_0", "cam_S_1"],
            "W": ["cam_W_0", "cam_W_1"],
            "E": ["cam_E_0", "cam_E_1"]
        }
        
        # Initial state setup: Force initial active direction (North) to green in SUMO
        try:
            traci.trafficlight.setPhase(self.tls_id, self.direction_phases[self.algorithm.current_direction]["green"])
            traci.trafficlight.setPhaseDuration(self.tls_id, 9999.0)  # Suppress SUMO internal timers
        except Exception as e:
            console.print(f"[bold yellow][WARNING][/bold yellow] Failed to initialize TLS: {e}")
            
        # Get junction center position to offset POI timer labels in SUMO GUI
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
        
        # Add transparent POIs to hold timer and queue text in SUMO GUI
        for poi_id, (px, py) in self.poi_positions.items():
            try:
                traci.poi.add(poi_id, x=px, y=py, color=(0,0,0,255), poiType="0", width=0.1, height=0.1)
            except Exception as e:
                pass
        
    def step(self, step_length=0.1):
        """Executed at every 0.1s step in main.py execution loop."""
        # Refresh POI labels in SUMO GUI
        self.update_gui_pois()
        
        # 1. If currently in transition Yellow phase
        if self.algorithm.is_yellow_phase:
            self.algorithm.elapsed_yellow += step_length
            if self.algorithm.elapsed_yellow >= self.algorithm.yellow_duration:
                self.algorithm.is_yellow_phase = False
                self.algorithm.elapsed_yellow = 0.0
                self.algorithm.elapsed_green = 0.0
                
                # Retrieve the next green direction from decision engine
                next_dir = self.algorithm.select_next_direction(
                    self.is_dual_mode, self.direction_phases, self.counterpart, self.get_queue_count
                )
                
                old_dir = self.algorithm.current_direction
                self.algorithm.current_direction = next_dir
                
                # Estimate initial red wait duration for the direction transitioning to red
                self.algorithm.initial_red_wait[old_dir] = self.algorithm.calculate_estimated_wait(
                    old_dir, self.is_dual_mode, self.direction_phases, self.counterpart,
                    self.get_active_vehicles, self.get_queue_count
                )
                
                # Set active green phase in SUMO
                traci.trafficlight.setPhase(self.tls_id, self.direction_phases[next_dir]["green"])
                traci.trafficlight.setPhaseDuration(self.tls_id, 9999.0)  # Suppress SUMO internal timers
                console.print(f"[bold green][GREEN][/bold green] GREEN light active in direction [bold magenta]{next_dir}[/bold magenta] (min_green={self.algorithm.min_green}s)")
            return

        # 2. If in active Green phase, fetch sensor counts and query decision transition
        vehicles_detected = self.get_active_vehicles(self.algorithm.current_direction)
        if self.is_dual_mode:
            counter_detected = self.get_active_vehicles(self.counterpart[self.algorithm.current_direction])
            if vehicles_detected == 999 or counter_detected == 999:
                vehicles_detected = 999
            else:
                vehicles_detected += counter_detected
                
        is_healthy = self.cams_healthy[self.algorithm.current_direction]
        if self.is_dual_mode:
            is_healthy = is_healthy and self.cams_healthy[self.counterpart[self.algorithm.current_direction]]
            
        should_yellow, reason = self.algorithm.decide_yellow_transition(
            step_length, vehicles_detected, is_healthy
        )
        
        if should_yellow:
            self.algorithm.is_yellow_phase = True
            self.algorithm.elapsed_yellow = 0.0
            
            # Transition to yellow in SUMO
            traci.trafficlight.setPhase(self.tls_id, self.direction_phases[self.algorithm.current_direction]["yellow"])
            traci.trafficlight.setPhaseDuration(self.tls_id, 9999.0)  # Suppress SUMO internal timers
            
            prefix = "[bold red][MAX-OUT][/bold red]" if "MAX" in reason else "[bold yellow][GAP-OUT][/bold yellow]"
            console.print(f"{prefix} Transitioning to Yellow for direction [bold magenta]{self.algorithm.current_direction}[/bold magenta] due to {reason}.")

    def get_active_vehicles(self, direction):
        """Reads active vehicle count from lane area detectors (cameras) with failsafe check."""
        if not self.cams_healthy[direction]:
            return 999  # Failsafe fallback: assume high traffic density
            
        try:
            active_cams = self.cams[direction]
            return sum(traci.lanearea.getLastStepVehicleNumber(cam) for cam in active_cams)
        except traci.exceptions.TraCIException:
            console.print(f"[bold red][FAILSAFE][/bold red] Camera for direction '[bold yellow]{direction}[/bold yellow]' detected ERROR! Activating fixed-time fallback.")
            self.cams_healthy[direction] = False
            return 999

    def get_queue_count(self, direction):
        """Reads total queued vehicle length from lane area detectors (cameras) with failsafe check."""
        if not self.cams_healthy[direction]:
            return 999  # Failsafe fallback
            
        try:
            candidate_cams = self.cams[direction]
            return sum(traci.lanearea.getJamLengthVehicle(cam) for cam in candidate_cams)
        except traci.exceptions.TraCIException:
            console.print(f"[bold red][FAILSAFE][/bold red] Camera for direction '[bold yellow]{direction}[/bold yellow]' detected ERROR! Activating fixed-time fallback.")
            self.cams_healthy[direction] = False
            return 999

    def update_gui_pois(self):
        """Refreshes countdown timers and vehicle queue length texts in SUMO GUI."""
        for poi_id in self.poi_positions.keys():
            dir_key = poi_id.split("_")[1]  # N, S, W, or E
            
            timer_text = self.algorithm.get_timer_text(
                dir_key, self.is_dual_mode, self.direction_phases, self.counterpart,
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
