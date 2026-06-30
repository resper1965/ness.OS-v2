import typer
from rich.console import Console
from rich.table import Table
from ..api_client import ContaboAPIClient
from ..schemas import ObjectStorageResponse

app = typer.Typer(help="Manage Object Storage.")
console = Console()

@app.command("list")
def list_storage():
    """List all Object Storages."""
    client = ContaboAPIClient()
    try:
        data = client.get("/object-storages")
        storages = [ObjectStorageResponse(**item) for item in data.get("data", [])]
        
        table = Table(title="Contabo Object Storage")
        table.add_column("ID", style="cyan")
        table.add_column("Region", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Purchased Space (TB)", style="blue")
        
        for st in storages:
            table.add_row(st.objectStorageId, st.region, st.status, str(st.totalPurchasedSpaceTB))
            
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error fetching object storages: {e}[/red]")
