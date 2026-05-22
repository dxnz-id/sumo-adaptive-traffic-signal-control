"""
SIMULATION PERFORMANCE ANALYZER
Parses SUMO's output/tripinfo.xml after the simulation ends and generates:
  - output/summary/report_<timestamp>.md   (human-readable Markdown report)
  - output/summary/report_<timestamp>.json (machine-readable JSON summary)
"""

import os
import json
import statistics
import xml.etree.ElementTree as ET
from datetime import datetime
from collections import defaultdict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from src.config import SIM_DURATION

# -------------------------------------------------------------------------
#  PATHS
# -------------------------------------------------------------------------
OUTPUT_DIR  = "output"
SUMMARY_DIR = os.path.join(OUTPUT_DIR, "summary")
TRIPINFO_PATH = os.path.join(OUTPUT_DIR, "tripinfo.xml")

console = Console()


# -------------------------------------------------------------------------
#  PARSING
# -------------------------------------------------------------------------
def _parse_tripinfo(path: str) -> list[dict]:
    """Parse every <tripinfo> element into a list of dicts."""
    if not os.path.exists(path):
        console.print(f"  [red][ERROR][/red] tripinfo.xml not found at: {path}")
        return []

    tree = ET.parse(path)
    root = tree.getroot()
    vehicles = []
    for elem in root.iter("tripinfo"):
        try:
            vehicles.append({
                "id":           elem.get("id", ""),
                "vType":        elem.get("vType", "unknown"),
                "duration":     float(elem.get("duration",    0)),
                "waitingTime":  float(elem.get("waitingTime", 0)),
                "timeLoss":     float(elem.get("timeLoss",    0)),
                "waitingCount": int(float(elem.get("waitingCount", 0))),
                "stopTime":     float(elem.get("stopTime",    0)),
                "routeLength":  float(elem.get("routeLength", 0)),
                "departDelay":  float(elem.get("departDelay", 0)),
                "arrival":      float(elem.get("arrival",     0)),
                # Emission attributes (only present when SUMO emission model is active)
                "fuel_abs":     float(elem.get("fuel_abs",  0)),   # ml
                "CO2_abs":      float(elem.get("CO2_abs",   0)),   # mg
                "CO_abs":       float(elem.get("CO_abs",    0)),   # mg
                "NOx_abs":      float(elem.get("NOx_abs",   0)),   # mg
                "PMx_abs":      float(elem.get("PMx_abs",   0)),   # mg
            })
        except (ValueError, TypeError):
            continue
    return vehicles


# -------------------------------------------------------------------------
#  KPI COMPUTATION
# -------------------------------------------------------------------------
def _compute_global(vehicles: list[dict]) -> dict:
    """Compute overall KPIs across all vehicles."""
    if not vehicles:
        return {}

    def _avg(key):
        vals = [v[key] for v in vehicles]
        return round(statistics.mean(vals), 2) if vals else 0.0

    def _total(key):
        return round(sum(v[key] for v in vehicles), 2)

    stopped = [v for v in vehicles if v["waitingCount"] > 0]
    sim_duration = max([v["arrival"] for v in vehicles]) if vehicles else 0.0

    return {
        "configured_duration_s": float(SIM_DURATION),
        "actual_duration_s":     round(sim_duration, 2),
        "total_vehicles":        len(vehicles),
        "vehicles_stopped":      len(stopped),
        "pct_vehicles_stopped":  round(len(stopped) / len(vehicles) * 100, 1),
        "avg_travel_time_s":     _avg("duration"),
        "avg_waiting_time_s":    _avg("waitingTime"),
        "avg_time_loss_s":       _avg("timeLoss"),
        "avg_stops_per_vehicle": _avg("waitingCount"),
        "avg_depart_delay_s":    _avg("departDelay"),
        "total_fuel_ml":         _total("fuel_abs"),
        "total_fuel_L":          round(_total("fuel_abs") / 1000, 3),
        "total_CO2_mg":          _total("CO2_abs"),
        "total_CO2_kg":          round(_total("CO2_abs") / 1_000_000, 3),
        "total_CO_mg":           _total("CO_abs"),
        "total_NOx_mg":          _total("NOx_abs"),
        "total_PMx_mg":          _total("PMx_abs"),
    }


def _compute_by_vtype(vehicles: list[dict]) -> dict:
    """Compute KPIs grouped by vehicle type."""
    grouped: dict[str, list] = defaultdict(list)
    for v in vehicles:
        grouped[v["vType"]].append(v)

    result = {}
    for vtype, group in sorted(grouped.items()):
        def _avg(key):
            vals = [v[key] for v in group]
            return round(statistics.mean(vals), 2) if vals else 0.0

        result[vtype] = {
            "count":             len(group),
            "avg_travel_time_s": _avg("duration"),
            "avg_waiting_time_s": _avg("waitingTime"),
            "avg_time_loss_s":   _avg("timeLoss"),
            "avg_stops":         _avg("waitingCount"),
            "total_fuel_L":      round(sum(v["fuel_abs"] for v in group) / 1000, 3),
        }
    return result


def _build_report_data(mode_label: str, congested: list[str]) -> dict:
    """Parse XML and assemble the full report data structure."""
    vehicles = _parse_tripinfo(TRIPINFO_PATH)
    return {
        "timestamp":       datetime.now().isoformat(timespec="seconds"),
        "simulation_mode": mode_label,
        "congested_directions": congested,
        "global":          _compute_global(vehicles),
        "by_vehicle_type": _compute_by_vtype(vehicles),
    }


# -------------------------------------------------------------------------
#  OUTPUT WRITERS
# -------------------------------------------------------------------------
def _write_json(data: dict, path: str) -> None:
    """Serialize report data to a JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _write_markdown(data: dict, path: str) -> None:
    """Render report data into a human-readable Markdown file."""
    g    = data.get("global", {})
    mode = data["simulation_mode"]
    ts   = data["timestamp"]
    cong = ", ".join(data.get("congested_directions", [])) or "none"

    lines = [
        f"# 📊 Simulation Performance Report",
        f"",
        f"| Field | Value |",
        f"|:------|:------|",
        f"| Generated | `{ts}` |",
        f"| Mode | **{mode}** |",
        f"| Congested Directions | `{cong}` |",
        f"| Configured Duration | `{g.get('configured_duration_s', 0):.2f} s` |",
        f"| Actual Completion Time | `{g.get('actual_duration_s', 0):.2f} s` |",
        f"",
        f"---",
        f"",
        f"## 1. Global Traffic Metrics",
        f"",
        f"| Metric | Value |",
        f"|:-------|:------|",
        f"| Configured Flow Duration    | {g.get('configured_duration_s', 0):.2f} s |",
        f"| Actual Completion Time      | {g.get('actual_duration_s', 0):.2f} s |",
        f"| Total Vehicles Served       | **{g.get('total_vehicles', 0):,}** veh |",
        f"| Vehicles That Stopped       | {g.get('vehicles_stopped', 0):,} veh ({g.get('pct_vehicles_stopped', 0)}%) |",
        f"| Avg. Travel Time            | {g.get('avg_travel_time_s', 0):.2f} s |",
        f"| Avg. Waiting Time           | {g.get('avg_waiting_time_s', 0):.2f} s |",
        f"| Avg. Time Loss              | {g.get('avg_time_loss_s', 0):.2f} s |",
        f"| Avg. Stops / Vehicle        | {g.get('avg_stops_per_vehicle', 0):.2f} stops |",
        f"| Avg. Departure Delay        | {g.get('avg_depart_delay_s', 0):.2f} s |",
        f"",
        f"---",
        f"",
        f"## 2. Environmental Impact",
        f"",
        f"| Metric | Value |",
        f"|:-------|:------|",
        f"| Total Fuel Consumed | {g.get('total_fuel_L', 0):.3f} L |",
        f"| Total CO₂ Emitted   | {g.get('total_CO2_kg', 0):.3f} kg |",
        f"| Total CO Emitted    | {g.get('total_CO_mg', 0):.1f} mg |",
        f"| Total NOₓ Emitted   | {g.get('total_NOx_mg', 0):.1f} mg |",
        f"| Total PMₓ Emitted   | {g.get('total_PMx_mg', 0):.1f} mg |",
        f"",
        f"---",
        f"",
        f"## 3. Performance by Vehicle Type",
        f"",
        f"| Type | Count | Avg Wait (s) | Avg Delay (s) | Avg Stops | Fuel (L) |",
        f"|:-----|------:|-------------:|--------------:|----------:|---------:|",
    ]

    for vtype, stats in data.get("by_vehicle_type", {}).items():
        lines.append(
            f"| {vtype:<12} "
            f"| {stats['count']:>5} "
            f"| {stats['avg_waiting_time_s']:>12.2f} "
            f"| {stats['avg_time_loss_s']:>13.2f} "
            f"| {stats['avg_stops']:>9.2f} "
            f"| {stats['total_fuel_L']:>8.3f} |"
        )

    lines += [
        f"",
        f"---",
        f"",
        f"*Report auto-generated by SUMO Adaptive Traffic Light Simulator.*",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# -------------------------------------------------------------------------
#  RICH TERMINAL DISPLAY
# -------------------------------------------------------------------------
def _print_to_console(data: dict) -> None:
    """Print a formatted summary to the terminal using Rich."""
    g    = data.get("global", {})
    mode = data["simulation_mode"]

    console.print()
    console.rule(f"[bold cyan]SIMULATION REPORT — {mode}[/bold cyan]")
    console.print()

    # --- Global metrics table ---
    t = Table(title="Global Traffic Metrics", box=box.ROUNDED, show_header=True, header_style="bold magenta")
    t.add_column("Metric", style="dim")
    t.add_column("Value", justify="right")

    t.add_row("Configured Duration",     f"{g.get('configured_duration_s', 0):.2f} s")
    t.add_row("Actual Completion Time",   f"{g.get('actual_duration_s', 0):.2f} s")
    t.add_row("Total Vehicles Served",   f"[bold]{g.get('total_vehicles', 0):,}[/bold] veh")
    t.add_row("Vehicles That Stopped",   f"{g.get('vehicles_stopped', 0):,} veh ({g.get('pct_vehicles_stopped', 0)}%)")
    t.add_row("Avg. Travel Time",        f"{g.get('avg_travel_time_s', 0):.2f} s")
    t.add_row("Avg. Waiting Time",       f"[yellow]{g.get('avg_waiting_time_s', 0):.2f}[/yellow] s")
    t.add_row("Avg. Time Loss",          f"[yellow]{g.get('avg_time_loss_s', 0):.2f}[/yellow] s")
    t.add_row("Avg. Stops / Vehicle",    f"{g.get('avg_stops_per_vehicle', 0):.2f}")
    t.add_row("Avg. Departure Delay",    f"{g.get('avg_depart_delay_s', 0):.2f} s")
    console.print(t)
    console.print()

    # --- Environmental table ---
    e = Table(title="Environmental Impact", box=box.ROUNDED, show_header=True, header_style="bold green")
    e.add_column("Metric", style="dim")
    e.add_column("Value", justify="right")

    e.add_row("Total Fuel Consumed", f"{g.get('total_fuel_L', 0):.3f} L")
    e.add_row("Total CO₂ Emitted",   f"[red]{g.get('total_CO2_kg', 0):.3f}[/red] kg")
    e.add_row("Total CO Emitted",    f"{g.get('total_CO_mg', 0):.1f} mg")
    e.add_row("Total NOₓ Emitted",   f"{g.get('total_NOx_mg', 0):.1f} mg")
    e.add_row("Total PMₓ Emitted",   f"{g.get('total_PMx_mg', 0):.1f} mg")
    console.print(e)
    console.print()

    # --- By vehicle type table ---
    vt = Table(title="Performance by Vehicle Type", box=box.ROUNDED, show_header=True, header_style="bold blue")
    vt.add_column("Type")
    vt.add_column("Count",       justify="right")
    vt.add_column("Avg Wait (s)", justify="right")
    vt.add_column("Avg Delay (s)", justify="right")
    vt.add_column("Avg Stops",   justify="right")
    vt.add_column("Fuel (L)",    justify="right")

    for vtype, stats in data.get("by_vehicle_type", {}).items():
        vt.add_row(
            vtype,
            str(stats["count"]),
            f"{stats['avg_waiting_time_s']:.2f}",
            f"{stats['avg_time_loss_s']:.2f}",
            f"{stats['avg_stops']:.2f}",
            f"{stats['total_fuel_L']:.3f}",
        )
    console.print(vt)
    console.print()


# -------------------------------------------------------------------------
#  PUBLIC ENTRY POINT
# -------------------------------------------------------------------------
def print_simulation_report(mode_label: str = "Unknown", congested: list[str] | None = None) -> None:
    """
    Main function called from main.py after the simulation finishes.
    - Parses tripinfo.xml
    - Prints a Rich table summary to the terminal
    - Writes Markdown and JSON reports to output/summary/
    """
    if congested is None:
        congested = []

    # Ensure the summary subfolder exists
    os.makedirs(SUMMARY_DIR, exist_ok=True)

    console.print("\n  [bold cyan][ANALYSIS][/bold cyan] Processing simulation results...")

    data = _build_report_data(mode_label, congested)

    if not data.get("global"):
        console.print("  [red][WARN][/red] No vehicle data found — report skipped.")
        return

    # Print to terminal
    _print_to_console(data)

    # Write files with timestamp so multiple runs are preserved
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mode_slug  = mode_label.lower().replace(" ", "_").replace("-", "_")
    base_name  = f"report_{mode_slug}_{timestamp}"

    json_path = os.path.join(SUMMARY_DIR, base_name + ".json")
    md_path   = os.path.join(SUMMARY_DIR, base_name + ".md")

    _write_json(data, json_path)
    _write_markdown(data, md_path)

    console.print(Panel(
        f"[green]✔[/green] Markdown : [dim]{md_path}[/dim]\n"
        f"[green]✔[/green] JSON     : [dim]{json_path}[/dim]",
        title="[bold]Report Saved[/bold]",
        border_style="green",
    ))
