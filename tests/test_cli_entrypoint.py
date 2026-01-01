import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    base_env = os.environ.copy()
    pythonpath = base_env.get("PYTHONPATH", "")
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    base_env["PYTHONPATH"] = f"{src_path}{os.pathsep}{pythonpath}" if pythonpath else src_path
    if env:
        base_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "budget_app.cli", *args],
        check=False,
        capture_output=True,
        text=True,
        env=base_env,
    )


def test_importing_cli_module_does_not_load_app_module():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import budget_app.cli, sys; assert 'budget_app.app' not in sys.modules",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_cli_help_runs_without_error():
    result = run_cli("--help")

    assert result.returncode == 0, result.stderr
    assert "Budget app administration commands." in result.stdout


def test_password_hash_output_can_be_verified_via_cli():
    hash_result = run_cli("password", "hash", "--password", "secret")

    assert hash_result.returncode == 0, hash_result.stderr
    hashed = hash_result.stdout.strip()
    assert hashed

    verify_result = run_cli("password", "verify", "--password", "secret", "--hash", hashed)

    assert verify_result.returncode == 0, verify_result.stderr
    assert "Password is valid." in verify_result.stdout


def test_sync_funds_cli_entrypoint_creates_system_state(tmp_path):
    db_path = tmp_path / "budget.db"
    result = run_cli("sync-funds", env={"DATABASE_URL": f"sqlite:///{db_path}"})

    assert result.returncode == 0, result.stderr
    assert "Funding sync complete" in result.stdout
    conn = sqlite3.connect(db_path)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "system_state" in tables
    rows = conn.execute("SELECT COUNT(*) FROM system_state").fetchone()[0]
    assert rows == 1
    conn.close()
