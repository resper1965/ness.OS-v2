import typer
from rich.console import Console
from rich.table import Table
from ..api_client import ContaboAPIClient
from ..schemas import TagResponse

app = typer.Typer(help="Manage Tags.")
console = Console()

@app.command("list")
def list_tags():
    """List all Tags."""
    client = ContaboAPIClient()
    try:
        data = client.get("/tags")
        tags = [TagResponse(**item) for item in data.get("data", [])]
        
        table = Table(title="Contabo Tags")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Color", style="green")
        
        for t in tags:
            table.add_row(str(t.tagId), t.name, f"[{t.color}]{t.color}[/{t.color}]")
            
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error fetching tags: {e}[/red]")

@app.command("create")
def create_tag(name: str = typer.Argument(..., help="Name of the tag"), color: str = typer.Option("#000000", help="Hex color code")):
    """Create a new tag."""
    client = ContaboAPIClient()
    try:
        payload = {"name": name, "color": color}
        data = client.post("/tags", json_data=payload)
        console.print(f"[green]Tag '{name}' created successfully![/green]")
    except Exception as e:
        console.print(f"[red]Error creating tag: {e}[/red]")
