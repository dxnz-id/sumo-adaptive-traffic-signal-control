# Simulation Guide

This document explains how the SUMO simulation environment is configured, including vehicle profiles, driver behavior parameters, route generation, and traffic volume distributions.

---

## 1. Intersection Layout

The modeled intersection is a four-way urban junction with the following characteristics:

- **Left-hand traffic** (LHT) — vehicles drive on the left side of the road.
- **Two through-lanes per approach** (total 8 incoming lanes).
- **Slip roads** — dedicated left-turn bypass lanes at each corner. Left-turning vehicles skip the traffic light entirely via the slip road and merge downstream.
- **No U-turns** (`--no-turnarounds true`) — simulating common urban signage restrictions.

### Approach Directions

| Direction | Incoming Edges | Outgoing Edges |
| :--- | :--- | :--- |
| North | `north_in_1`, `north_in_2` | `north_out_1`, `north_out_2` |
| South | `south_in_1`, `south_in_2` | `south_out_1`, `south_out_2` |
| West | `west_in_1`, `west_in_2` | `west_out_1`, `west_out_2` |
| East | `east_in_1`, `east_in_2` | `east_out_1`, `east_out_2` |

---

## 2. Traffic Light Program Modes

Two TLS layout programs are available, selected via CLI at runtime:

### Single Mode (`--tls.layout incoming`)

Eight-phase program. Each of the four directions receives an independent green and yellow phase in sequence:

| Phase Index | State | Direction(s) |
| :--- | :--- | :--- |
| 0 | Green | North |
| 1 | Yellow | North |
| 2 | Green | East |
| 3 | Yellow | East |
| 4 | Green | South |
| 5 | Yellow | South |
| 6 | Green | West |
| 7 | Yellow | West |

### Dual Mode (`--tls.layout opposites`)

Four-phase program. Opposite directions (N-S and E-W) receive green simultaneously:

| Phase Index | State | Direction(s) |
| :--- | :--- | :--- |
| 0 | Green | North + South |
| 1 | Yellow | North + South |
| 2 | Green | East + West |
| 3 | Yellow | East + West |

---

## 3. Vehicle Profiles

Four vehicle types are defined, each with distinct physical and behavioral parameters:

| Type | Accel (m/s²) | Decel (m/s²) | Length (m) | Max Speed (m/s) | Color | Fleet % |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Car | 2.6 | 4.5 | 4.5 | 13.89 (50 km/h) | Yellow | 65% |
| Motorcycle | 3.0 | 5.0 | 2.0 | 16.67 (60 km/h) | Cyan | 20% |
| Bus | 1.5 | 3.5 | 12.0 | 11.11 (40 km/h) | Green | 8% |
| Truck | 1.2 | 3.0 | 10.0 | 11.11 (40 km/h) | Orange | 7% |

All vehicle types use SUMO's `speedFactor = normc(1.0, 0.1, 0.8, 1.2)` — a normally distributed speed variation capped between 80% and 120% of the road's speed limit.

---

## 4. Driver Orderliness Levels

Driver behavior is configured via the `sigma` (driver imperfection) and `tau` (minimum headway time) parameters:

| Parameter | Orderly | Chaotic | Effect |
| :--- | :--- | :--- | :--- |
| `sigma` | `0.1` (per type) | Vehicle's natural `sigma` | Higher = more erratic steering and speed variation |
| `tau` | `1.0s` | `0.5s` | Lower = vehicles follow more closely (aggressive tailgating) |

### Orderly Mode
Drivers maintain safe headway and constant speeds. Models disciplined traffic similar to Singapore or Japanese urban roads. Suitable for benchmarking ideal-case algorithm performance.

### Chaotic Mode
Drivers use each vehicle type's natural sigma value (up to `0.6` for motorcycles) and a headway of only `0.5s`. This models aggressive urban driving behavior — frequent lane weaving, aggressive merges, and minimal safety margins. Produces more realistic queue dynamics for high-density intersection studies.

---

## 5. Route Generation & Turn Ratios

Each vehicle is assigned a route based on:
1. **Origin direction** (North/South/West/East) — sampled from `TRAFFIC_VOLUME` intervals.
2. **Maneuver type** (straight/left/right) — sampled from `TURN_RATIO` per direction.

### Turn Ratios

| Origin | Straight | Left | Right |
| :--- | :--- | :--- | :--- |
| North | 55% | 25% | 20% |
| South | 55% | 20% | 25% |
| West | 50% | 25% | 25% |
| East | 50% | 25% | 25% |

Left-turn vehicles use the dedicated **slip road** edge (`slip_ne`, `slip_sw`, etc.) instead of entering the main intersection.

---

## 6. Traffic Volume & Poisson Flow Modelling

Traffic volume is defined in **vehicles per hour (vph)** over time intervals. The generator converts volume to individual vehicle departures using:

```
n_vehicles = int(vol_per_hour × interval_seconds / 3600)
depart_time = uniform(t_start, t_end - 1)
```

### Normal Traffic (Default)

| Time Interval | Volume (vph) |
| :--- | :--- |
| 00:00 – 15:00 | 180 |
| 15:00 – 30:00 | 350 |
| 30:00 – 45:00 | 220 |
| 45:00 – 60:00 | 320 |

### Congested Traffic (Selected via CLI)

| Time Interval | Volume (vph) |
| :--- | :--- |
| 00:00 – 15:00 | 800 |
| 15:00 – 30:00 | 1500 |
| 30:00 – 45:00 | 900 |
| 45:00 – 60:00 | 1400 |

Congested volume simulates peak-hour conditions with a threefold to fourfold increase in vehicle arrivals on the selected approach directions.

---

## 7. E2 Lane Area Detectors (Camera Sensors)

Two E2 detectors cover each approach lane, placed from position `0` to end of edge (`endPos=-1`), refreshed every `freq=1` second:

| Camera ID | Lane |
| :--- | :--- |
| `cam_N_0` | `north_in_2_0` |
| `cam_N_1` | `north_in_2_1` |
| `cam_S_0` | `south_in_2_0` |
| `cam_S_1` | `south_in_2_1` |
| `cam_W_0` | `west_in_2_0` |
| `cam_W_1` | `west_in_2_1` |
| `cam_E_0` | `east_in_2_0` |
| `cam_E_1` | `east_in_2_1` |

The controller aggregates both detectors per direction to determine active vehicle count and queue length.
