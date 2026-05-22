import questionary
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

console = Console()

def get_congestion_from_cli():
    """Interactive command-line interface for configuring traffic simulation parameters."""
    console.print()
    console.print("[bold cyan]SUMO ADAPTIVE TRAFFIC LIGHT SIMULATOR[/bold cyan]")
    console.print("[dim]Intelligent Control System Based on Time Extension & Phase Skipping[/dim]")
    console.print()
    
    try:
        # 1. Congestion Checkbox via Questionary (Arrow & Space navigation)
        selected = questionary.checkbox(
            "Select directions to configure with heavy traffic (Jammed):",
            choices=[
                questionary.Choice("North (Utara)", value="north"),
                questionary.Choice("South (Selatan)", value="south"),
                questionary.Choice("West (Barat)", value="west"),
                questionary.Choice("East (Timur)", value="east"),
            ],
            instruction="(Use [Space] to select/deselect, [Enter] to confirm)"
        ).ask()
        
        if selected is None:
            selected = []
            
        # 2. Traffic Light Program Selection via Questionary
        tls_choice = questionary.select(
            "Select Traffic Light Program Mode:",
            choices=[
                questionary.Choice("Single (One direction green at a time)", value="1"),
                questionary.Choice("Dual (Opposite directions green together)", value="2"),
            ]
        ).ask()
        
        tls_layout = "incoming" if tls_choice != "2" else "opposites"
        
        # 3. Driver Behavior Selection via Questionary
        ord_choice = questionary.select(
            "Select Driver Orderliness Level:",
            choices=[
                questionary.Choice("Orderly (Safe safety distance, constant speed)", value="1"),
                questionary.Choice("Chaotic (Aggressive driving, frequent overtaking)", value="2"),
            ]
        ).ask()
        
        orderliness = "orderly" if ord_choice != "2" else "chaotic"
        
        # 4. Adaptive Algorithm Toggle via Questionary
        adaptive_choice = questionary.select(
            "Enable Adaptive Traffic Light Algorithm?",
            choices=[
                questionary.Choice("Yes (Time Extension & Phase Skipping)", value="1"),
                questionary.Choice("No (Use SUMO built-in fixed-time program)", value="2"),
            ]
        ).ask()
        
        use_adaptive = adaptive_choice != "2"
        
        # 5. Simulation Speed Toggle via Questionary
        speed_choice = questionary.select(
            "Run simulation as fast as possible (Maximum CPU speed)?",
            choices=[
                questionary.Choice("No (Real-time speed / 50ms delay per step)", value="2"),
                questionary.Choice("Yes (No delay / maximum speed)", value="1"),
            ]
        ).ask()
        
        run_fast = speed_choice == "1"
        
    except Exception:
        # FALLBACK: For non-interactive terminals, output panels, or IDE environments
        console.print("[dim]Note: Non-interactive terminal detected, switching to standard text inputs...[/dim]\n")
        
        # 1. Congestion selection table
        table = Table(show_header=False, box=None)
        table.add_row("[bold green][n][/bold green] [cyan]North[/cyan]", "[bold green][s][/bold green] [cyan]South[/cyan]")
        table.add_row("[bold green][w][/bold green] [cyan]West[/cyan]", "[bold green][e][/bold green] [cyan]East[/cyan]")
        
        console.print(Panel(
            table,
            title="TRAFFIC CONGESTION CONFIG (SELECT JAMMED DIRECTIONS)",
            subtitle="Type direction letters (e.g., 'n' or 's,e'). Leave empty for normal traffic flow."
        ))
        
        ans = Prompt.ask("Enter jammed directions", default="").lower().replace(" ", "")
        
        mapping = {'n': 'north', 's': 'south', 'w': 'west', 'e': 'east'}
        selected = []
        
        if ans:
            parts = ans.split(",")
            for p in parts:
                if p in mapping:
                    selected.append(mapping[p])
                elif p in mapping.values():
                    selected.append(p)

        # 2. Traffic Light Program Mode
        console.print("\nSelect Traffic Light Program Mode:")
        console.print(" [1] Single (One direction green at a time)")
        console.print(" [2] Dual (Opposite directions green together)")
        
        tls_choice = Prompt.ask("Select Mode", choices=["1", "2"], default="1")
        tls_layout = "incoming" if tls_choice != "2" else "opposites"
        
        # 3. Driver Orderliness Mode
        console.print("\nSelect Driver Orderliness Level:")
        console.print(" [1] Orderly (Safe safety distance, constant speed)")
        console.print(" [2] Chaotic (Aggressive driving, frequent overtaking)")
        
        ord_choice = Prompt.ask("Select Behavior", choices=["1", "2"], default="1")
        orderliness = "orderly" if ord_choice != "2" else "chaotic"
        
        # 4. Adaptive Algorithm Toggle
        console.print("\nEnable Adaptive Traffic Light Algorithm?")
        console.print(" [1] Yes (Time Extension & Phase Skipping)")
        console.print(" [2] No (Use SUMO built-in fixed-time program)")
        
        adaptive_choice = Prompt.ask("Select Mode", choices=["1", "2"], default="1")
        use_adaptive = adaptive_choice != "2"

        # 5. Simulation Speed Toggle
        console.print("\nRun simulation as fast as possible (Maximum CPU speed)?")
        console.print(" [1] Yes (No delay / maximum speed)")
        console.print(" [2] No (Real-time speed / 50ms delay per step)")
        
        speed_choice = Prompt.ask("Select Speed Mode", choices=["1", "2"], default="2")
        run_fast = speed_choice == "1"

    # Print Configuration Summary
    console.print()
    console.print("[bold green]SIMULATION CONFIGURATION:[/bold green]")
    console.print(f"  • Congestion Status    : [yellow]{'CONGESTED (' + ', '.join([s.capitalize() for s in selected]) + ')' if selected else 'NORMAL'}[/yellow]")
    console.print(f"  • TLS Cycle Mode       : [cyan]{'SINGLE' if tls_layout == 'incoming' else 'DUAL'}[/cyan]")
    console.print(f"  • Road Orderliness     : [green]{orderliness.upper()}[/green]")
    console.print(f"  • Adaptive Algorithm   : [{'green' if use_adaptive else 'red'}]{'ENABLED' if use_adaptive else 'DISABLED (Fixed-Time)'}[/{'green' if use_adaptive else 'red'}]")
    console.print(f"  • Simulation Speed     : [magenta]{'MAXIMUM SPEED (No Delay)' if run_fast else 'REAL-TIME SPEED (50ms delay)'}[/magenta]")
    console.print()
        
    return selected, tls_layout, orderliness, use_adaptive, run_fast
