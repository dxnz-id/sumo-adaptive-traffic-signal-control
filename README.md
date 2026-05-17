# SUMO Adaptive Traffic Light Simulator

> An intelligent, actuated traffic signal control system for SUMO simulations, built on **Time Extension** and **Phase Skipping** decision logic. Models a realistic urban four-way intersection with mixed vehicle types, driver behavior profiles, and left-hand-drive road geometry.

![Python](https://img.shields.io/badge/Python-3.12%2B-blue?style=flat-square&logo=python)
![SUMO](https://img.shields.io/badge/SUMO-1.20%2B-green?style=flat-square)
![TraCI](https://img.shields.io/badge/TraCI-API-orange?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-purple?style=flat-square)
![uv](https://img.shields.io/badge/Package%20Manager-uv-black?style=flat-square)

---

## Overview

Traffic congestion at urban intersections is a persistent challenge in cities worldwide, where peak-hour vehicle volume often exceeds intersection capacity. Conventional **fixed-time traffic lights** are unable to respond to real-time vehicle density fluctuations, causing unnecessary delays even when lanes are completely empty.

This simulator models an adaptive four-way intersection controlled by a custom **Time Extension algorithm** running on top of SUMO (Simulation of Urban MObility). A Python TraCI bridge reads live E2 detector camera data and dynamically adjusts green light durations, skips empty directions entirely, and handles dual-mode (opposites) intersection layouts without any manual configuration.

The project is built with a **clean modular architecture** that fully decouples the decision logic from the SUMO simulator bindings, making algorithm upgrades (e.g., transitioning to Reinforcement Learning) straightforward.

---

## Key Features

| Feature | Description |
| :--- | :--- |
| **Gap-Out Detection** | Green phase terminates early when sensor cameras detect zero active vehicles, eliminating wasted green time |
| **Max-Out Limit** | A configurable maximum green cap prevents traffic starvation on opposing red directions |
| **Phase Skipping** | Circular queue algorithm skips directions with no queued traffic, immediately serving the next waiting lane |
| **Dual Mode (Opposites)** | Dynamically detects N-S / E-W simultaneous green layout (4-phase program) without manual config |
| **Failsafe Sensor Fallback** | If a camera detector errors, the system automatically switches to fixed-time fallback without crashing |
| **Driver Behavior Modeling** | Simulate orderly (safe headway) or chaotic (aggressive, overtaking) driver behavior profiles |
| **Left-Hand Traffic** | All routes and connection geometries are configured for left-hand-drive road standards |
| **Slip Road Bypass** | Dedicated left-turn bypass lanes (slip roads) allow free-flow left turns without entering the intersection |

---

## Architecture Overview

The system is composed of five focused modules following a **Strategy Design Pattern**:

```
main.py (Orchestrator)
    │
    ├── src/cli.py          → Interactive terminal: congestion, mode, behavior
    ├── src/config.py       → Constants: routes, volumes, vehicle types
    ├── src/generator.py    → SUMO XML builder: network, routes, sensors, config
    │
    └── src/controller.py   → TraCI driver: reads cameras, commands SUMO phases
            │
            └── src/algorithm.py  → Pure math: Gap-Out, Max-Out, Phase Skipping
```

`TimeExtensionController` delegates all decision-making to `TimeExtensionAlgorithm`, which is **completely isolated from TraCI**. This decoupling allows algorithm unit testing without launching SUMO.

See [`docs/architecture.md`](docs/architecture.md) for detailed diagrams and design pattern explanations.

---

## Getting Started

### Prerequisites

1. **Python 3.12+** with [`uv`](https://github.com/astral-sh/uv) package manager.
2. **SUMO 1.20+** installed and configured. Download from [sumo.dlr.de](https://sumo.dlr.de/docs/Downloads.php).
3. **Set `SUMO_HOME`** environment variable to your SUMO installation directory:
   ```powershell
   # Windows (PowerShell) — add to your system environment variables for persistence
   $env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
   ```
   ```bash
   # macOS / Linux — add to ~/.bashrc or ~/.zshrc
   export SUMO_HOME="/usr/share/sumo"
   ```

### Installation

Clone the repository and install dependencies using `uv`:

```bash
git clone https://github.com/your-username/simulasi-perempatan.git
cd simulasi-perempatan
uv sync
```

### Running the Simulation

```bash
uv run python main.py
```

You will be guided through an interactive CLI to configure:
1. **Congestion** — Select which directions (N/S/W/E) to simulate heavy traffic.
2. **TLS Mode** — Single (one green at a time) or Dual (opposites green together).
3. **Driver Behavior** — Orderly (safe headway) or Chaotic (aggressive/overtaking).

The simulator will then:
- Build the road network via `netconvert`
- Generate randomized vehicle routes using Poisson-distributed flow rates
- Launch `sumo-gui` and begin adaptive control via TraCI

---

## Project Structure

```text
simulasi-perempatan/
├── map/                         # Static XML infrastructure files (manually designed)
│   ├── nodes.nod.xml            # Junction and node definitions
│   ├── edges.edg.xml            # Road edge geometry and lane count
│   ├── connections.con.xml      # Lane connection rules and turn restrictions
│   ├── view.view.xml            # SUMO GUI viewport and color settings
│   └── build/                   # Auto-generated compiled output files (gitignored)
│       ├── net.net.xml          # Compiled road network
│       ├── routes.rou.xml       # Dynamic vehicle routes
│       ├── sensors.add.xml      # E2 lane detector definitions
│       └── config.sumocfg       # SUMO simulation configuration
├── src/                         # Python source modules
│   ├── __init__.py
│   ├── config.py                # Constants, volumes, routes, vehicle types
│   ├── cli.py                   # Interactive CLI interface
│   ├── generator.py             # XML file builders and network compiler
│   ├── algorithm.py             # Pure adaptive decision logic (TraCI-free)
│   └── controller.py            # TraCI simulator driver and GUI bridge
├── output/                      # Simulation analytics output (gitignored)
│   ├── summary.xml
│   ├── tripinfo.xml
│   └── queue.xml
├── docs/                        # Technical documentation
│   ├── architecture.md
│   ├── algorithms.md
│   ├── simulation_guide.md
│   ├── analytics_and_evaluation.md
│   ├── troubleshooting_and_gotchas.md
│   └── future_works.md
├── main.py                      # Simulation entry point
└── pyproject.toml               # Dependency and tooling configuration (uv)
```

---

## Documentation

| Document | Description |
| :--- | :--- |
| [`docs/architecture.md`](docs/architecture.md) | Module structure, Strategy Pattern design, and Failsafe mechanism |
| [`docs/algorithms.md`](docs/algorithms.md) | Gap-Out, Max-Out, Phase Skipping, and wait estimation formulas |
| [`docs/simulation_guide.md`](docs/simulation_guide.md) | Vehicle profiles, driver orderliness, and Poisson flow configuration |
| [`docs/analytics_and_evaluation.md`](docs/analytics_and_evaluation.md) | Reading SUMO output data and comparing with fixed-time baselines |
| [`docs/troubleshooting_and_gotchas.md`](docs/troubleshooting_and_gotchas.md) | Common setup errors and known issues |
| [`docs/future_works.md`](docs/future_works.md) | Roadmap: RL agents, Green Wave, and V2X integration |

---

## License & Contribution Rules

This project is **dual-licensed** to protect our research while enabling commercial use:

1. **Open Source (AGPL v3)**: Free for personal, academic, and non-commercial open-source use. Any modifications hosted on a server (SaaS) or distributed must be open-sourced under the AGPL v3. See the [`LICENSE`](LICENSE) file for the full legal text.
2. **Proprietary Commercial License**: If you wish to use this software in a commercial, closed-source product, or run it as a paid cloud service without open-sourcing your code, you must purchase a Commercial License from the authors.

For commercial licensing inquiries, please contact us via our GitHub profile: [dxnz-id](https://github.com/dxnz-id).

### Contributing

We welcome community contributions! However, to protect our ability to dual-license and commercialize this project, all external contributors **must agree to our Contributor License Agreement (CLA)** before a Pull Request can be merged.

Please review and sign the [`CLA.md`](CLA.md) file when submitting contributions. This process is fully automated via `cla-assistant.io` upon opening a Pull Request.
