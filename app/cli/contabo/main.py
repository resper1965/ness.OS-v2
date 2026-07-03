import typer
from rich.console import Console
from .auth import save_credentials, fetch_token
from .commands import compute, storage, tags

app = typer.Typer(help="Contabo CLI - Manage your Contabo Infrastructure.")
console = Console()

# Add sub-commands
app.add_typer(compute.app, name="compute")
app.add_typer(storage.app, name="storage")
app.add_typer(tags.app, name="tags")

@app.command("login")
def login(
    client_id: str = typer.Option(..., help="OAuth2 Client ID"),
    client_secret: str = typer.Option(..., help="OAuth2 Client Secret"),
    user: str = typer.Option(..., help="API User Email"),
    password: str = typer.Option(..., prompt=True, hide_input=True, help="API Password")
):
    """Save credentials and verify authentication."""
    try:
        save_credentials(client_id, client_secret, user, password)
        console.print("[yellow]Authenticating...[/yellow]")
        # Test auth
        fetch_token()
        console.print("[green]Authentication successful! Credentials saved.[/green]")
    except Exception as e:
        console.print(f"[red]Authentication failed: {e}[/red]")

if __name__ == "__main__":
    app()
