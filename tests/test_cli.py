import os
import sqlite3

from click.testing import CliRunner

os.environ.setdefault("DATABASE_URL", "sqlite://")

from budget_app import cli


def test_prompt_password_retries_until_match(monkeypatch):
    responses = iter(["first", "second", "second", "second"])
    call_count = {"count": 0}

    def fake_ask(*args, **kwargs):
        call_count["count"] += 1
        return next(responses)

    class DummyConsole:
        def __init__(self):
            self.messages = []

        def print(self, message):
            self.messages.append(message)

    dummy_console = DummyConsole()
    monkeypatch.setattr(cli, "console", dummy_console)
    monkeypatch.setattr(cli.Prompt, "ask", staticmethod(fake_ask))

    result = cli.prompt_password(confirm=True)

    assert result == "second"
    assert call_count["count"] == 4
    assert any("Passwords do not match" in str(message) for message in dummy_console.messages)


def test_prompt_password_single_prompt(monkeypatch):
    calls = []

    def fake_ask(*args, **kwargs):
        calls.append((args, kwargs))
        return "secret"

    monkeypatch.setattr(cli.Prompt, "ask", staticmethod(fake_ask))

    assert cli.prompt_password(confirm=False) == "secret"
    assert len(calls) == 1


def test_password_set_cli_with_password_option_writes_env(tmp_path):
    env_file = tmp_path / ".env"
    runner = CliRunner()

    result = runner.invoke(
        cli.cli,
        ["password", "set", "--env-file", str(env_file), "--password", "secret"],
    )

    assert result.exit_code == 0
    assert "Updated" in result.output
    contents = env_file.read_text(encoding="utf-8")
    assert "APP_PASSWORD=" in contents


def test_password_hash_cli_with_password_option():
    runner = CliRunner()

    result = runner.invoke(
        cli.cli,
        ["password", "hash", "--password", "secret", "--print-export"],
    )

    assert result.exit_code == 0
    assert "export" in result.output
    assert "APP_PASSWORD='" in result.output


def test_sync_funds_command_creates_system_state(tmp_path, monkeypatch):
    db_path = tmp_path / "budget.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    runner = CliRunner()

    result = runner.invoke(cli.cli, ["sync-funds"])

    assert result.exit_code == 0
    assert "Funding sync complete" in result.output
    conn = sqlite3.connect(db_path)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "system_state" in tables
    rows = conn.execute("SELECT COUNT(*) FROM system_state").fetchone()[0]
    assert rows == 1
    conn.close()
