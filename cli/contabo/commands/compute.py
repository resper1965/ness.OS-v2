import typer
from rich.console import Console
from rich.table import Table
from ..api_client import ContaboAPIClient
from ..schemas import InstanceResponse

app = typer.Typer(help="Manage Compute Instances (VPS/VDS).")
console = Console()

@app.command("list")
def list_instances():
    """List all compute instances."""
    client = ContaboAPIClient()
    try:
        data = client.get("/compute/instances")
        instances = [InstanceResponse(**item) for item in data.get("data", [])]
        
        table = Table(title="Contabo Instances")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("IP (v4)", style="blue")
        
        for inst in instances:
            ipv4 = inst.ipConfig.get("v4", {}).get("ip", "N/A")
            table.add_row(str(inst.instanceId), inst.name, inst.status, ipv4)
            
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error fetching instances: {e}[/red]")

@app.command("restart")
def restart_instance(instance_id: int = typer.Argument(..., help="The instance ID to restart")):
    """Restart a specific instance."""
    client = ContaboAPIClient()
    try:
        # According to Contabo API: POST /compute/instances/{instanceId}/actions/restart
        client.post(f"/compute/instances/{instance_id}/actions/restart")
        console.print(f"[green]Instance {instance_id} restarted successfully.[/green]")
    except Exception as e:
        console.print(f"[red]Error restarting instance: {e}[/red]")
