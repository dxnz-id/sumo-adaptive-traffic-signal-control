"""
SUMO ADAPTIVE TRAFFIC LIGHT ALGORITHM
Pure Logic & Decision-Making Module for Adaptive Control
===================================================================
This module contains pure mathematical formulas, decision state tracking,
and Phase Skipping & Time Extension logic, completely isolated from TraCI.
"""

from rich.console import Console

console = Console()

class TimeExtensionAlgorithm:
    def __init__(self, min_green=10.0, max_green=50.0, yellow_duration=4.0):
        self.min_green = min_green
        self.max_green = max_green
        self.yellow_duration = yellow_duration
        
        # Decision state tracking variables
        self.elapsed_green = 0.0
        self.elapsed_yellow = 0.0
        self.is_yellow_phase = False
        self.current_direction = "N"  # Start active from North
        
        # Initial red phase wait trackers per direction
        self.initial_red_wait = {"N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0}

    def decide_yellow_transition(self, step_length, vehicles_detected, is_healthy):
        """
        Determines whether the active green phase should transition to yellow
        based on Gap-out (empty gap detected) and Max-out (maximum limit reached).
        """
        self.elapsed_green += step_length
        
        if self.elapsed_green >= self.min_green:
            # GAP-OUT: If active camera is healthy and no vehicles are detected
            if vehicles_detected == 0 and is_healthy:
                return True, f"GAP-OUT (Empty gap detected after {self.elapsed_green:.1f}s)"
            # MAX-OUT: If green duration reaches the maximum configured limit
            elif self.elapsed_green >= self.max_green:
                return True, f"MAX-OUT (Maximum green limit of {self.max_green}s reached)"
                
        return False, "KEEP"

    def select_next_direction(self, is_dual_mode, direction_phases, counterpart, get_queue_fn):
        """
        Determines the next green phase direction utilizing circular Phase Skipping logic.
        """
        sequence = ["N", "E", "S", "W"]
        curr_idx = sequence.index(self.current_direction)
        
        # Scan next directions in circular queue order
        for i in range(1, 5):
            next_idx = (curr_idx + i) % 4
            candidate_dir = sequence[next_idx]
            
            # If in Dual mode, skip candidates sharing the same green phase as the current direction
            if is_dual_mode and direction_phases[candidate_dir]["green"] == direction_phases[self.current_direction]["green"]:
                continue
                
            queue_count = get_queue_fn(candidate_dir)
            if is_dual_mode:
                queue_count += get_queue_fn(counterpart[candidate_dir])
            
            if queue_count > 0:
                # Vehicles detected! Set next green direction
                if i > 1:
                    skipped = [sequence[(curr_idx + j) % 4] for j in range(1, i)]
                    # In Dual mode, suppress skip notifications for directions sharing phase with candidates or current
                    if is_dual_mode:
                        skipped = [d for d in skipped if direction_phases[d]["green"] != direction_phases[self.current_direction]["green"] and direction_phases[d]["green"] != direction_phases[candidate_dir]["green"]]
                    if skipped:
                        console.print(f"[bold blue][SKIP][/bold blue] Phase Skipping active! Skipping empty directions: [bold red]{', '.join(skipped)}[/bold red].")
                return candidate_dir
                
        # If all other directions are completely empty, keep the current green active
        return self.current_direction

    def calculate_estimated_wait(self, direction, is_dual_mode, direction_phases, counterpart, get_vehicles_fn, get_queue_fn):
        """
        Calculates the real-time estimated remaining wait time for a red light direction.
        """
        if is_dual_mode:
            # In Dual mode, if the target shares the same green phase as the currently active direction, wait time is 0
            if direction_phases[direction]["green"] == direction_phases[self.current_direction]["green"]:
                return 0.0
                
            # If opposite phase, wait time is equal to the remaining active duration of the current phase
            estimated_wait = 0.0
            if self.is_yellow_phase:
                estimated_wait += max(0.0, self.yellow_duration - self.elapsed_yellow)
            else:
                vehicles = get_vehicles_fn(self.current_direction) + get_vehicles_fn(counterpart[self.current_direction])
                
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
        
        # Calculate remaining active time of current active phase (Green/Yellow)
        if self.is_yellow_phase:
            estimated_wait += max(0.0, self.yellow_duration - self.elapsed_yellow)
        else:
            vehicles = get_vehicles_fn(self.current_direction)
                
            if self.elapsed_green < self.min_green:
                estimated_wait += (self.min_green - self.elapsed_green) + self.yellow_duration
            elif vehicles > 0:
                estimated_wait += max(0.0, self.max_green - self.elapsed_green) + self.yellow_duration
            else:
                estimated_wait += self.yellow_duration  # Immediate yellow transition
                
        # Add min_green + yellow for intermediate directions containing queued traffic (non-skipped)
        for i in range(1, steps_away):
            intermediate_idx = (curr_idx + i) % 4
            intermediate_dir = sequence[intermediate_idx]
            
            if get_queue_fn(intermediate_dir) > 0:
                estimated_wait += self.min_green + self.yellow_duration
                
        return estimated_wait

    def get_timer_text(self, direction, is_dual_mode, direction_phases, counterpart, get_vehicles_fn, get_queue_fn):
        """
        Dynamically calculates active/red phase durations for SUMO GUI text visualization.
        """
        # 1. If target direction is currently active (Green or Yellow)
        is_active = (self.current_direction == direction)
        if is_dual_mode:
            is_active = (direction_phases[direction]["green"] == direction_phases[self.current_direction]["green"])
            
        if is_active:
            if self.is_yellow_phase:
                rem = max(0.0, self.yellow_duration - self.elapsed_yellow)
                return f"Yellow: {int(rem)}s/{int(self.yellow_duration)}s"
            else:
                # Show countdown to maximum allowed green duration
                rem = max(0.0, self.max_green - self.elapsed_green)
                return f"Green: {int(rem)}s/{int(self.max_green)}s"
        
        # 2. If target direction is currently Red (show dynamic real-time wait estimation)
        rem = self.calculate_estimated_wait(direction, is_dual_mode, direction_phases, counterpart, get_vehicles_fn, get_queue_fn)
        total = self.initial_red_wait.get(direction, 0.0)
        
        # Visual failsafe: Ensure wait total is never less than remaining countdown wait time
        if rem > total:
            self.initial_red_wait[direction] = rem
            total = rem
            
        return f"Red: {int(rem)}s/{int(total)}s"
