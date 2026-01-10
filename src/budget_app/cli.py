from __future__ import annotations

import os
from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Prompt
from werkzeug.security import check_password_hash, generate_password_hash


console = Console()


def write_env_var(path: Path, key: str, value: str) -> None:
    lines: list[str] = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    updated = False
    new_lines: list[str] = []
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"{key}={value}")
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def prompt_password(confirm: bool) -> str:
    if not confirm:
        return Prompt.ask("Password", password=True)
    while True:
        password_text = Prompt.ask("Password", password=True)
        confirm_text = Prompt.ask("Confirm password", password=True)
        if password_text == confirm_text:
            return password_text
        console.print("Passwords do not match. Try again.")


@click.group()
def cli() -> None:
    """Budget app administration commands."""


@cli.group()
def password() -> None:
    """Password hash utilities."""


@password.command("hash")
@click.option("--password", "password_value", help="Password to hash.")
@click.option(
    "--method",
    default="scrypt",
    show_default=True,
    help="Hashing method passed to werkzeug.security.generate_password_hash.",
)
@click.option(
    "--salt-length",
    default=16,
    show_default=True,
    type=int,
    help="Salt length for hash generation.",
)
@click.option(
    "--print-export/--no-print-export",
    default=False,
    show_default=True,
    help="Print an export line for APP_PASSWORD.",
)
def password_hash(
    password_value: str | None,
    method: str,
    salt_length: int,
    print_export: bool,
) -> None:
    """Generate a password hash for APP_PASSWORD."""
    password_text = password_value or prompt_password(confirm=True)
    hashed = generate_password_hash(password_text, method=method, salt_length=salt_length)
    if print_export:
        click.echo(f"export APP_PASSWORD='{hashed}'")
    else:
        click.echo(hashed)


@password.command("set")
@click.option("--password", "password_value", help="Password to hash.")
@click.option(
    "--env-file",
    "env_file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path(".env"),
    show_default=True,
    help="Env file to update with APP_PASSWORD.",
)
@click.option(
    "--method",
    default="scrypt",
    show_default=True,
    help="Hashing method passed to werkzeug.security.generate_password_hash.",
)
@click.option(
    "--salt-length",
    default=16,
    show_default=True,
    type=int,
    help="Salt length for hash generation.",
)
def password_set(
    password_value: str | None,
    env_file: Path,
    method: str,
    salt_length: int,
) -> None:
    """Generate a hash and write APP_PASSWORD to the env file."""
    password_text = password_value or prompt_password(confirm=True)
    hashed = generate_password_hash(password_text, method=method, salt_length=salt_length)
    write_env_var(env_file, "APP_PASSWORD", hashed)
    console.print(f"Updated {env_file} with APP_PASSWORD hash.")


@password.command("verify")
@click.option("--password", "password_value", help="Password to verify.")
@click.option(
    "--hash",
    "hash_value",
    help="Hash to verify against. Defaults to APP_PASSWORD env var.",
)
def password_verify(password_value: str | None, hash_value: str | None) -> None:
    """Verify a password against a hash."""
    password_text = password_value or prompt_password(confirm=False)
    hash_text = hash_value or os.environ.get("APP_PASSWORD")
    if not hash_text:
        console.print("APP_PASSWORD is not set.")
        raise SystemExit(2)
    if check_password_hash(hash_text, password_text):
        console.print("Password is valid.")
        raise SystemExit(0)
    console.print("Password is invalid.")
    raise SystemExit(1)


@cli.command("sync-funds")
def sync_funds() -> None:
    """Sync monthly envelope funding."""
    from budget_app.app import create_app, sync_funding
    from flask_migrate import upgrade

    app = create_app()
    with app.app_context():
        upgrade()
        sync_funding(app)
    console.print("Funding sync complete.")


if __name__ == "__main__":
    cli()
