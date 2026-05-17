# Future Works

This document outlines planned enhancements and research directions for extending the adaptive traffic light simulator into a more sophisticated, AI-powered, and multi-intersection-aware system.

---

## 1. Reinforcement Learning Agent (Q-Learning / DQN)

### Current Limitation
The Time Extension algorithm uses **hand-crafted heuristics** (Gap-Out, Max-Out, Phase Skipping). While effective, these rules are deterministic and cannot learn from accumulated traffic patterns over time.

### Proposed Upgrade
Replace `TimeExtensionAlgorithm` with a **Reinforcement Learning (RL) agent** using the same TraCI sensor infrastructure. The RL agent learns an optimal policy by interacting with the simulation environment over many episodes.

#### State Space
```
state = [
    queue_North,    queue_South,
    queue_East,     queue_West,
    elapsed_green,  current_phase_index
]
```

#### Action Space
```
actions = [
    EXTEND_GREEN,     # Keep current direction green for another step
    SWITCH_TO_YELLOW  # Transition to yellow and cycle to next direction
]
```

#### Reward Function
```
reward = - (total_waiting_vehicles_this_step)
       + bonus if queue_cleared_direction == 0
       - penalty if max_green exceeded
```

#### Recommended Libraries
- [`stable-baselines3`](https://stable-baselines3.readthedocs.io/) for PPO / DQN agents.
- [`gymnasium`](https://gymnasium.farama.org/) for environment wrapping.
- SUMO's [TraCI-env wrappers](https://sumo.dlr.de/docs/Tutorials/TraCI4Traffic_Lights.html) for episode resets.

#### Migration Path
Because `TimeExtensionAlgorithm` is completely decoupled from TraCI, swapping it for an RL agent requires only replacing the class in `src/algorithm.py` and updating the callback interface in `TimeExtensionController`. The simulator driver, XML generators, and CLI remain unchanged.

---

## 2. Green Wave Coordinated System

### Current Limitation
This simulator models a **single isolated intersection**. In reality, urban arterial roads contain sequences of intersections that are operationally linked — a vehicle stopped at one intersection will arrive at the next during its red phase if signals are not coordinated.

### Proposed Enhancement
Implement a **Green Wave** (also called *signal progression* or *coordinated arterial control*) system across multiple simulated intersections:

1. **Multi-TLS TraCI Extension**: Extend `TimeExtensionController` to manage an array of `tls_id` nodes instead of a single junction.
2. **Offset Calculation**: Compute a time offset per intersection based on:
   - Average vehicle travel speed between intersections.
   - Distance between intersection stop lines.
   - Cycle length of the upstream intersection.
3. **Corridor Modeling**: Add a linked arterial road to `edges.edg.xml` and `nodes.nod.xml` with additional intermediate junctions.

```
[Intersection A] --offset=Δt--> [Intersection B] --offset=2Δt--> [Intersection C]
```

---

## 3. V2X Integration (Vehicle-to-Infrastructure)

### Current Limitation
All sensor data is collected via **fixed E2 lane area detectors** (simulated cameras). These sensors:
- Have a fixed detection zone limited to the approach lane.
- Cannot distinguish vehicle types or predict arrival patterns.

### Proposed Enhancement
Leverage SUMO's [`vehicle.getPosition()`](https://sumo.dlr.de/docs/TraCI/Vehicle_Value_Retrieval.html) TraCI API to simulate **Vehicle-to-Infrastructure (V2X)** data feeds:

1. **GPS Position Feeds**: Read the real-time position and speed of every vehicle in the simulation at each step.
2. **Predictive Arrival Model**: Estimate how many vehicles are approaching the intersection within the next `T` seconds, enabling **predictive phase extension** before queues actually form.
3. **Priority Vehicle Detection**: Detect emergency vehicles (ambulances, fire trucks) via their vehicle type ID and preemptively grant green to their approach direction.

```python
# Example: Get all approaching vehicles within 200m of junction
for veh_id in traci.vehicle.getIDList():
    dist = compute_distance(traci.vehicle.getPosition(veh_id), junction_pos)
    if dist < 200.0:
        approaching_vehicles.append(veh_id)
```

---

## 4. Real-World Data Calibration

### Current Limitation
Traffic volumes, turn ratios, and vehicle type proportions are manually estimated values. They approximate generic urban traffic patterns but are not calibrated against real field measurements.

### Proposed Enhancement
1. **Field Count Data Collection**: Use drone video footage or manual turning movement counts (TMC surveys) at a real Bandung/Jakarta intersection.
2. **SUMO Calibration Tool**: Use SUMO's [`calibrator`](https://sumo.dlr.de/docs/Simulation/Calibrator.html) element to dynamically adjust vehicle insertion rates to match observed real-world flow data at runtime.
3. **OD Matrix Import**: Convert origin-destination (OD) matrices from field surveys into SUMO route files using `od2trips` and `duarouter`.

---

## 5. Dashboard & Real-Time Visualization

### Proposed Enhancement
Build a separate lightweight real-time monitoring dashboard that reads SUMO's TraCI output and displays live metrics:

- **Queue length heatmap** per approach direction.
- **Phase timeline** (Green/Yellow/Red bars per direction over time).
- **Running KPI counters** (total waiting time, vehicles served, Gap-Out events vs Max-Out events).

**Recommended Stack:**
- [`streamlit`](https://streamlit.io/) for rapid Python-native dashboard development.
- [`plotly`](https://plotly.com/python/) for live-updating charts.
- TraCI data read from a shared queue (Python `multiprocessing.Queue`) to avoid blocking the simulation loop.
