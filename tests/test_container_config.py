from pathlib import Path


def test_cron_root_has_hourly_sync_job():
    cron_path = Path("docker/cron/root")

    assert cron_path.exists()
    contents = cron_path.read_text(encoding="utf-8")
    assert "0 * * * *" in contents
    assert "budget-cli sync-funds" in contents


def test_supervisord_config_runs_gunicorn_and_cron():
    supervisor_path = Path("docker/supervisord.conf")

    assert supervisor_path.exists()
    contents = supervisor_path.read_text(encoding="utf-8")
    assert "[program:gunicorn]" in contents
    assert "gunicorn -b 0.0.0.0:5000 budget_app.app:app" in contents
    assert "[program:crond]" in contents
    assert "/usr/sbin/crond -f" in contents
