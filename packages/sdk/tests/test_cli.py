import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

from titanrag.cli.main import app
from titanrag.models import ChatResponse, Citation, Workspace
from typer.testing import CliRunner

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "TitanRAG CLI" in result.stdout
    assert "0.1.0" in result.stdout


def test_cli_whoami_not_logged_in(tmp_path, monkeypatch):
    monkeypatch.setattr("titanrag.cli.config.CONFIG_FILE", tmp_path / "config.json")
    result = runner.invoke(app, ["whoami"])
    assert result.exit_code == 1
    assert "Not logged in" in result.stdout


def test_cli_login_and_whoami(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr("titanrag.cli.config.CONFIG_FILE", cfg_file)
    monkeypatch.setattr("titanrag.cli.config.CONFIG_DIR", tmp_path)

    mock_client = MagicMock()
    mock_ws = Workspace(
        id=uuid4(),
        tenant_id=uuid4(),
        name="Test WS",
        slug="test-ws",
    )
    mock_client.workspaces.list.return_value = [mock_ws]

    with patch("titanrag.cli.auth.get_active_client", return_value=mock_client):
        result = runner.invoke(
            app, ["login", "--api-key", "tr_secret_test_123456", "--base-url", "http://localhost:8000"]
        )
        assert result.exit_code == 0
        assert "Authentication Successful" in result.stdout

    # Now verify whoami works
    result_whoami = runner.invoke(app, ["whoami"])
    assert result_whoami.exit_code == 0
    assert "tr_sec...3456" in result_whoami.stdout


def test_cli_workspace_list_json(tmp_path, monkeypatch):
    mock_client = MagicMock()
    mock_ws = Workspace(
        id=uuid4(),
        tenant_id=uuid4(),
        name="Engineering Docs",
        slug="eng-docs",
    )
    mock_client.workspaces.list.return_value = [mock_ws]

    with patch("titanrag.cli.workspaces.get_active_client", return_value=mock_client):
        result = runner.invoke(app, ["workspace", "list", "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert len(parsed) == 1
        assert parsed[0]["name"] == "Engineering Docs"


def test_cli_query_json(tmp_path, monkeypatch):
    ws_id = str(uuid4())
    monkeypatch.setattr("titanrag.cli.chat.get_active_workspace_id", lambda _: ws_id)

    mock_client = MagicMock()
    mock_client.query.return_value = ChatResponse(
        answer="TitanRAG uses reciprocal rank fusion.",
        citations=[Citation(citation_id="c1", document_id="d1", snippet="RRF formula", page=2)],
    )

    with patch("titanrag.cli.chat.get_active_client", return_value=mock_client):
        result = runner.invoke(app, ["query", "Explain retrieval", "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert "reciprocal rank fusion" in parsed["answer"]
        assert len(parsed["citations"]) == 1


def test_cli_query_quiet(monkeypatch):
    ws_id = str(uuid4())
    monkeypatch.setattr("titanrag.cli.chat.get_active_workspace_id", lambda _: ws_id)

    mock_client = MagicMock()
    mock_client.query.return_value = ChatResponse(
        answer="TitanRAG uses reciprocal rank fusion.",
        citations=[],
    )

    with patch("titanrag.cli.chat.get_active_client", return_value=mock_client):
        result = runner.invoke(app, ["query", "Explain retrieval", "--quiet"])
        assert result.exit_code == 0
        assert result.stdout.strip() == "TitanRAG uses reciprocal rank fusion."


def test_cli_query_stdin(monkeypatch):
    ws_id = str(uuid4())
    monkeypatch.setattr("titanrag.cli.chat.get_active_workspace_id", lambda _: ws_id)

    mock_client = MagicMock()
    mock_client.query.return_value = ChatResponse(
        answer="Piped query answered.",
        citations=[],
    )

    with patch("titanrag.cli.chat.get_active_client", return_value=mock_client):
        result = runner.invoke(app, ["query", "--quiet"], input="Piped prompt question")
        assert result.exit_code == 0
        assert result.stdout.strip() == "Piped query answered."
        mock_client.query.assert_called_once()
        assert mock_client.query.call_args.kwargs["query"] == "Piped prompt question"
