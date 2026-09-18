import glob
import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from titanrag.cli.config import get_active_client, get_active_workspace_id
from titanrag.exceptions import TitanRAGError

console = Console()
doc_app = typer.Typer(help="Manage documents and ingestion")


def _resolve_workspace_id(override_id: str | None) -> str:
    wid = get_active_workspace_id(override_id)
    if not wid:
        console.print(
            "[bold red]No active workspace selected. Use 'titan workspace switch <id>' or pass '--workspace-id'.[/bold red]"
        )
        raise typer.Exit(code=1)
    return wid


@doc_app.command("list")
def list_documents(
    workspace_id: Annotated[str | None, typer.Option("--workspace-id", "-w", help="Workspace ID")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Output raw JSON")] = False,
) -> None:
    """List documents in the specified workspace."""
    wid = _resolve_workspace_id(workspace_id)
    client = get_active_client()

    try:
        docs = client.documents.list(wid)
        if as_json:
            typer.echo(json.dumps([d.model_dump(mode="json") for d in docs], indent=2))
            return

        table = Table(title=f"Documents in Workspace {wid[:8]}...", show_lines=True)
        table.add_column("ID", style="cyan")
        table.add_column("Filename", style="bold white")
        table.add_column("Status", style="green")
        table.add_column("Chunks", justify="right")
        table.add_column("Size", justify="right")

        for d in docs:
            size_kb = f"{(d.file_size_bytes or 0) / 1024:.1f} KB" if d.file_size_bytes else "—"
            status_style = "green" if d.status == "READY" else "yellow"
            table.add_row(
                str(d.id),
                d.filename,
                f"[{status_style}]{d.status}[/{status_style}]",
                str(d.chunk_count),
                size_kb,
            )

        console.print(table)
    except TitanRAGError as e:
        console.print(f"[bold red]Error listing documents:[/bold red] {e}")
        raise typer.Exit(code=1) from None


@doc_app.command("upload")
def upload_documents(
    path_or_glob: Annotated[str, typer.Argument(help="File path, folder, or glob pattern (e.g. ./docs/*.pdf)")],
    workspace_id: Annotated[str | None, typer.Option("--workspace-id", "-w", help="Workspace ID")] = None,
    acl_groups: Annotated[str | None, typer.Option("--acl-groups", "-g", help="Comma-separated ACL groups")] = None,
) -> None:
    """Upload documents to the active workspace for processing."""
    wid = _resolve_workspace_id(workspace_id)
    client = get_active_client()

    # Collect matching files
    files_to_upload: list[Path] = []
    p = Path(path_or_glob)
    if p.is_file():
        files_to_upload.append(p)
    elif p.is_dir():
        for ext in ("*.pdf", "*.txt", "*.md", "*.docx"):
            files_to_upload.extend(p.glob(ext))
    else:
        # Glob expression
        matches = glob.glob(path_or_glob, recursive=True)
        for m in matches:
            mp = Path(m)
            if mp.is_file():
                files_to_upload.append(mp)

    if not files_to_upload:
        console.print(f"[yellow]No files matched pattern: '{path_or_glob}'[/yellow]")
        return

    group_list = [g.strip() for g in acl_groups.split(",")] if acl_groups else None

    console.print(f"[bold]Uploading {len(files_to_upload)} file(s) to workspace [cyan]{wid[:8]}...[/cyan][/bold]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Uploading files...", total=len(files_to_upload))

        for file_path in files_to_upload:
            progress.update(task, description=f"Uploading [white]{file_path.name}[/white]...")
            try:
                res = client.documents.upload(
                    workspace_id=wid,
                    file_path_or_bytes=file_path,
                    filename=file_path.name,
                    acl_groups=group_list,
                )
                progress.console.print(
                    f" [bold green]✓[/bold green] {file_path.name} -> queued ([cyan]{res.document_id}[/cyan])"
                )
            except Exception as e:
                progress.console.print(f" [bold red]✗[/bold red] {file_path.name} -> failed: {e}")
            progress.advance(task)

    console.print("[bold green]Upload batch completed.[/bold green]")


@doc_app.command("status")
def document_status(
    document_id: Annotated[str, typer.Argument(help="Document UUID")],
    workspace_id: Annotated[str | None, typer.Option("--workspace-id", "-w", help="Workspace ID")] = None,
) -> None:
    """Check ingestion status of a specific document."""
    wid = _resolve_workspace_id(workspace_id)
    client = get_active_client()
    try:
        doc = client.documents.get_status(workspace_id=wid, document_id=document_id)
        console.print(f"Document: [bold white]{doc.filename}[/bold white]")
        console.print(f"Status:   [bold green]{doc.status}[/bold green]")
        console.print(f"Chunks:   [cyan]{doc.chunk_count}[/cyan]")
    except TitanRAGError as e:
        console.print(f"[bold red]Error getting document status:[/bold red] {e}")
        raise typer.Exit(code=1) from None


@doc_app.command("reindex")
def reindex_document(
    document_id: Annotated[str, typer.Argument(help="Document UUID")],
    workspace_id: Annotated[str | None, typer.Option("--workspace-id", "-w", help="Workspace ID")] = None,
) -> None:
    """Trigger re-processing and re-indexing of a document."""
    wid = _resolve_workspace_id(workspace_id)
    client = get_active_client()
    try:
        client.documents.reindex(workspace_id=wid, document_id=document_id)
        console.print(f"[bold green]Reindexing triggered for document:[/bold green] [cyan]{document_id}[/cyan]")
    except TitanRAGError as e:
        console.print(f"[bold red]Error triggering reindex:[/bold red] {e}")
        raise typer.Exit(code=1) from None


@doc_app.command("delete")
def delete_document(
    document_id: Annotated[str, typer.Argument(help="Document UUID")],
    workspace_id: Annotated[str | None, typer.Option("--workspace-id", "-w", help="Workspace ID")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Bypass confirmation prompt")] = False,
) -> None:
    """Delete a document and purge all associated chunks and vectors."""
    wid = _resolve_workspace_id(workspace_id)
    client = get_active_client()

    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete document {document_id}?")
        if not confirm:
            console.print("[dim]Aborted.[/dim]")
            return

    try:
        client.documents.delete(workspace_id=wid, document_id=document_id)
        console.print(f"[bold green]Successfully deleted document:[/bold green] [cyan]{document_id}[/cyan]")
    except TitanRAGError as e:
        console.print(f"[bold red]Error deleting document:[/bold red] {e}")
        raise typer.Exit(code=1) from None
