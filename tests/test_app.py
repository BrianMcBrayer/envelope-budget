from decimal import Decimal
import os
import re

import pytest
from sqlalchemy.pool import StaticPool
from werkzeug.security import generate_password_hash

os.environ.setdefault("DATABASE_URL", "sqlite://")

from budget_app.app import Envelope, SystemState, create_app, db, sync_funding


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", generate_password_hash("secret"))
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            },
        }
    )
    with app.app_context():
        db.drop_all()
        db.create_all()
    with app.test_client() as client:
        yield client


def login(client, password="secret"):
    token = get_csrf_token(client, "/login")
    return client.post("/login", data={"password": password, "csrf_token": token})


def get_csrf_token(client, path="/"):
    response = client.get(path)
    assert response.status_code == 200
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.data.decode())
    assert match, "CSRF token not found in response"
    return match.group(1)


def test_login_accepts_correct_password(client):
    response = login(client, "secret")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_login_rejects_incorrect_password(client):
    response = login(client, "wrong")
    assert response.status_code == 401
    assert b"Invalid password" in response.data


def test_add_envelope(client):
    login(client)
    token = get_csrf_token(client)
    response = client.post(
        "/envelopes",
        data={
            "name": "Groceries",
            "base_amount": "120.00",
            "mode": "reset",
            "csrf_token": token,
        },
    )
    assert response.status_code == 302
    with client.application.app_context():
        envelope = Envelope.query.one()
        assert envelope.name == "Groceries"
        assert envelope.base_amount == Decimal("120.00")
        assert envelope.balance == Decimal("120.00")
        assert envelope.mode == "reset"


def test_envelope_spend_decrements_balance():
    envelope = Envelope(
        name="Dining",
        base_amount=Decimal("50.00"),
        balance=Decimal("50.00"),
        mode="reset",
    )

    envelope.spend(Decimal("12.34"))

    assert envelope.balance == Decimal("37.66")


def test_envelope_spend_rejects_non_positive_amount():
    envelope = Envelope(
        name="Dining",
        base_amount=Decimal("50.00"),
        balance=Decimal("50.00"),
        mode="reset",
    )

    with pytest.raises(ValueError):
        envelope.spend(Decimal("0.00"))

    with pytest.raises(ValueError):
        envelope.spend(Decimal("-1.00"))


def test_envelope_deposit_increments_balance():
    envelope = Envelope(
        name="Dining",
        base_amount=Decimal("50.00"),
        balance=Decimal("50.00"),
        mode="reset",
    )

    envelope.deposit(Decimal("8.50"))

    assert envelope.balance == Decimal("58.50")


def test_envelope_deposit_rejects_non_positive_amount():
    envelope = Envelope(
        name="Dining",
        base_amount=Decimal("50.00"),
        balance=Decimal("50.00"),
        mode="reset",
    )

    with pytest.raises(ValueError):
        envelope.deposit(Decimal("0.00"))

    with pytest.raises(ValueError):
        envelope.deposit(Decimal("-5.00"))


def test_envelope_apply_funding_reset_sets_balance():
    envelope = Envelope(
        name="Rent",
        base_amount=Decimal("1000.00"),
        balance=Decimal("200.00"),
        mode="reset",
    )

    envelope.apply_funding(months=2)

    assert envelope.balance == Decimal("1000.00")


def test_envelope_apply_funding_rollover_adds_each_month():
    envelope = Envelope(
        name="Travel",
        base_amount=Decimal("200.00"),
        balance=Decimal("50.00"),
        mode="rollover",
    )

    envelope.apply_funding(months=3)

    assert envelope.balance == Decimal("650.00")


def test_envelope_apply_funding_rejects_non_positive_months():
    envelope = Envelope(
        name="Travel",
        base_amount=Decimal("200.00"),
        balance=Decimal("50.00"),
        mode="rollover",
    )

    with pytest.raises(ValueError):
        envelope.apply_funding(months=0)

    with pytest.raises(ValueError):
        envelope.apply_funding(months=-1)


def test_spend_money(client):
    login(client)
    with client.application.app_context():
        envelope = Envelope(
            name="Dining",
            base_amount=Decimal("50.00"),
            balance=Decimal("50.00"),
            mode="reset",
        )
        db.session.add(envelope)
        db.session.commit()
        envelope_id = envelope.id
    response = client.post(
        f"/envelopes/{envelope_id}/spend",
        data={"amount": "20.00", "csrf_token": get_csrf_token(client)},
    )
    assert response.status_code == 302
    with client.application.app_context():
        refreshed = db.session.get(Envelope, envelope_id)
        assert refreshed.balance == Decimal("30.00")


def test_auto_funding_catchup(client, monkeypatch):
    with client.application.app_context():
        reset_env = Envelope(
            name="Rent",
            base_amount=Decimal("1000.00"),
            balance=Decimal("300.00"),
            mode="reset",
        )
        rollover_env = Envelope(
            name="Travel",
            base_amount=Decimal("200.00"),
            balance=Decimal("0.00"),
            mode="rollover",
        )
        db.session.add_all([reset_env, rollover_env])
        db.session.add(SystemState(last_funded_month="2025-01"))
        db.session.commit()
        reset_id = reset_env.id
        rollover_id = rollover_env.id

    monkeypatch.setattr("budget_app.app.get_current_month", lambda: "2025-03")
    sync_funding(client.application)

    with client.application.app_context():
        reset_refreshed = db.session.get(Envelope, reset_id)
        rollover_refreshed = db.session.get(Envelope, rollover_id)
        assert reset_refreshed.balance == Decimal("1000.00")
        assert rollover_refreshed.balance == Decimal("400.00")


def test_idempotency(client, monkeypatch):
    with client.application.app_context():
        envelope = Envelope(
            name="Dining",
            base_amount=Decimal("100.00"),
            balance=Decimal("100.00"),
            mode="rollover",
        )
        db.session.add(envelope)
        db.session.add(SystemState(last_funded_month="2025-05"))
        db.session.commit()
        envelope_id = envelope.id

    monkeypatch.setattr("budget_app.app.get_current_month", lambda: "2025-05")
    sync_funding(client.application)
    sync_funding(client.application)

    with client.application.app_context():
        refreshed = db.session.get(Envelope, envelope_id)
        assert refreshed.balance == Decimal("100.00")


def test_spend_updates_ui(client):
    login(client)
    with client.application.app_context():
        envelope = Envelope(
            name="Dining",
            base_amount=Decimal("50.00"),
            balance=Decimal("50.00"),
            mode="reset",
        )
        db.session.add(envelope)
        db.session.commit()
        envelope_id = envelope.id

    response = client.post(
        f"/envelopes/{envelope_id}/spend",
        data={"amount": "20.00", "csrf_token": get_csrf_token(client)},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert b'envelope-card' in response.data
    assert b'id="env-' in response.data
    assert b"$30.00" in response.data
    assert b'value="30.00"' in response.data
    assert b'max="50.00"' in response.data


def test_progress_bar_handles_rollover_surplus(client):
    login(client)
    with client.application.app_context():
        envelope = Envelope(
            name="Bonus",
            base_amount=Decimal("50.00"),
            balance=Decimal("75.00"),
            mode="rollover",
        )
        db.session.add(envelope)
        db.session.commit()
        envelope_id = envelope.id

    response = client.get("/")

    assert response.status_code == 200
    assert f'id="progress-{envelope_id}"'.encode() in response.data
    assert b"class=\"surplus\"" in response.data
    assert b'max="75.00"' in response.data


def test_progress_bar_flags_low_balance(client):
    login(client)
    with client.application.app_context():
        envelope = Envelope(
            name="Groceries",
            base_amount=Decimal("100.00"),
            balance=Decimal("5.00"),
            mode="reset",
        )
        db.session.add(envelope)
        db.session.commit()
        envelope_id = envelope.id

    response = client.get("/")

    assert response.status_code == 200
    assert f'id="progress-{envelope_id}"'.encode() in response.data
    assert b"low-balance" in response.data


def test_ui_contains_modern_slate_vars(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"--pico-background-color: #0f172a" in response.data
    assert b"backdrop-filter" in response.data


def test_ui_has_refined_elements(client):
    login(client)
    response = client.get("/")
    assert response.status_code == 200
    assert b"btn-archive" in response.data
    assert b"backdrop-filter: blur" in response.data
    assert b'header class="app-header"' in response.data
    assert b'div class="container"' in response.data


def test_envelope_card_has_deposit_toggle(client):
    login(client)
    with client.application.app_context():
        envelope = Envelope(
            name="Savings",
            base_amount=Decimal("75.00"),
            balance=Decimal("75.00"),
            mode="reset",
        )
        db.session.add(envelope)
        db.session.commit()
        envelope_id = envelope.id

    response = client.get("/")

    assert response.status_code == 200
    assert b"x-data" in response.data
    assert b">Deposit<" in response.data
    assert f'hx-post="/envelopes/{envelope_id}/add"'.encode() in response.data


def test_envelope_card_forms_have_transitions(client):
    login(client)
    with client.application.app_context():
        envelope = Envelope(
            name="Savings",
            base_amount=Decimal("75.00"),
            balance=Decimal("75.00"),
            mode="reset",
        )
        db.session.add(envelope)
        db.session.commit()

    response = client.get("/")

    assert response.status_code == 200
    assert b'x-transition:enter="transition-smooth"' in response.data
    assert b'x-transition:enter-start="opacity-0 transform -translate-y-2"' in response.data
    assert b'x-transition:enter-end="opacity-100 transform translate-y-0"' in response.data


def test_spend_form_has_loading_indicator(client):
    login(client)
    with client.application.app_context():
        envelope = Envelope(
            name="Utilities",
            base_amount=Decimal("90.00"),
            balance=Decimal("90.00"),
            mode="reset",
        )
        db.session.add(envelope)
        db.session.commit()

    response = client.get("/")

    assert response.status_code == 200
    assert b'hx-indicator="#spend-indicator-' in response.data
    assert b"Processing..." in response.data


def test_spend_rejects_non_positive_amount(client):
    login(client)
    with client.application.app_context():
        envelope = Envelope(
            name="Dining",
            base_amount=Decimal("50.00"),
            balance=Decimal("50.00"),
            mode="reset",
        )
        db.session.add(envelope)
        db.session.commit()
        envelope_id = envelope.id

    response = client.post(
        f"/envelopes/{envelope_id}/spend",
        data={"amount": "0.00", "csrf_token": get_csrf_token(client)},
    )

    assert response.status_code == 400


def test_deposit_rejects_non_positive_amount(client):
    login(client)
    with client.application.app_context():
        envelope = Envelope(
            name="Dining",
            base_amount=Decimal("50.00"),
            balance=Decimal("50.00"),
            mode="reset",
        )
        db.session.add(envelope)
        db.session.commit()
        envelope_id = envelope.id

    response = client.post(
        f"/envelopes/{envelope_id}/add",
        data={"amount": "0.00", "csrf_token": get_csrf_token(client)},
    )

    assert response.status_code == 400


def test_csrf_extension_initialized(client):
    assert client.application.extensions.get("csrf") is not None


def test_post_without_csrf_token_is_rejected(client):
    response = client.post("/login", data={"password": "secret"})
    assert response.status_code in {400, 403}
