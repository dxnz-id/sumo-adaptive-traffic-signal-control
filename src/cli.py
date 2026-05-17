import questionary
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

console = Console()

def get_crowded_from_cli():
    """Mengambil input kemacetan dari terminal dengan antarmuka interaktif minimalis."""
    console.print()
    console.print("[bold cyan]SUMO ADAPTIVE TRAFFIC LIGHT SIMULATOR[/bold cyan]")
    console.print("[dim]Sistem Kendali Lampu Lalu Lintas Cerdas Berbasis Time Extension & Phase Skipping[/dim]")
    console.print()
    
    try:
        # 1. Checkbox Kemacetan menggunakan Questionary (Bisa navigasi panah & spasi!)
        selected = questionary.checkbox(
            "Pilih arah yang ingin dibuat sangat ramai (Macet):",
            choices=[
                questionary.Choice("Utara (North)", value="north"),
                questionary.Choice("Selatan (South)", value="south"),
                questionary.Choice("Barat (West)", value="west"),
                questionary.Choice("Timur (East)", value="east"),
            ],
            instruction="(Gunakan [Spasi] untuk memilih/batal, [Enter] untuk konfirmasi)"
        ).ask()
        
        if selected is None:
            selected = []
            
        # 2. Opsi Mode Lampu Merah menggunakan Questionary (Radio input menu!)
        tls_choice = questionary.select(
            "Pilih Mode Program Lampu Lalu Lintas:",
            choices=[
                questionary.Choice("Tunggal (Satu per satu arah hijau)", value="1"),
                questionary.Choice("Ganda (Dua arah berlawanan hijau bareng)", value="2"),
            ]
        ).ask()
        
        tls_layout = "incoming" if tls_choice != "2" else "opposites"
        
        # 3. Opsi Ketertiban menggunakan Questionary
        ord_choice = questionary.select(
            "Pilih Tingkat Ketertiban Pengendara:",
            choices=[
                questionary.Choice("Tertib (Jaga jarak aman, kecepatan konstan)", value="1"),
                questionary.Choice("Semrawut (Ugal-ugalan, menyalip)", value="2"),
            ]
        ).ask()
        
        orderliness = "orderly" if ord_choice != "2" else "chaotic"
        
    except Exception:
        # FALLBACK: Jika dijalankan di terminal non-interaktif / IDE output panel yang tidak mendukung console screen buffer
        console.print("[dim]Note: Terminal non-interaktif terdeteksi, beralih ke input teks standar...[/dim]\n")
        
        # 1. Menu Pilihan Kemacetan
        table = Table(show_header=False, box=None)
        table.add_row("[bold green][n][/bold green] [cyan]North / Utara[/cyan]", "[bold green][s][/bold green] [cyan]South / Selatan[/cyan]")
        table.add_row("[bold green][w][/bold green] [cyan]West  / Barat[/cyan]", "[bold green][e][/bold green] [cyan]East  / Timur[/cyan]")
        
        console.print(Panel(
            table,
            title="PENGATURAN KEMACETAN (PILIH ARAH MACET)",
            subtitle="Ketik hurufnya saja (misal: 'n' atau 's,e'). Kosongkan jika normal."
        ))
        
        ans = Prompt.ask("Masukkan pilihan arah", default="").lower().replace(" ", "")
        
        mapping = {'n': 'north', 's': 'south', 'w': 'west', 'e': 'east'}
        selected = []
        
        if ans:
            parts = ans.split(",")
            for p in parts:
                if p in mapping:
                    selected.append(mapping[p])
                elif p in mapping.values():
                    selected.append(p)

        # 2. Opsi Mode Lampu Merah
        console.print("\nPilih Mode Program Lampu Lalu Lintas:")
        console.print(" [1] Tunggal (Satu per satu arah hijau bergantian)")
        console.print(" [2] Ganda   (Dua arah berlawanan hijau bersamaan)")
        
        tls_choice = Prompt.ask("Pilih Mode", choices=["1", "2"], default="1")
        tls_layout = "incoming" if tls_choice != "2" else "opposites"
        
        # 3. Opsi Ketertiban
        console.print("\nPilih Tingkat Ketertiban Pengendara:")
        console.print(" [1] Tertib   (Jaga jarak aman, kecepatan konstan)")
        console.print(" [2] Semrawut (Ugal-ugalan, menyalip)")
        
        ord_choice = Prompt.ask("Pilih Perilaku", choices=["1", "2"], default="1")
        orderliness = "orderly" if ord_choice != "2" else "chaotic"

    # Ringkasan Konfigurasi Sebelum Start
    console.print()
    console.print("[bold green]KONFIGURASI SIMULASI:[/bold green]")
    console.print(f"  • Status Kemacetan : [yellow]{'RAMAI (' + ', '.join([s.capitalize() for s in selected]) + ')' if selected else 'NORMAL'}[/yellow]")
    console.print(f"  • Mode Siklus TLS  : [cyan]{'TUNGGAL' if tls_layout == 'incoming' else 'GANDA'}[/cyan]")
    console.print(f"  • Ketertiban Jalan : [green]{orderliness.upper()}[/green]")
    console.print()
        
    return selected, tls_layout, orderliness
