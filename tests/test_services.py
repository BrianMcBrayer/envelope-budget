from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool

import budget_app.services as services
from budget_app.app import Envelope, Transaction, create_app, db


@pytest.fixture()
def app():
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
    return app


def test_add_envelope_creates_record(app):
    with app.app_context():
        envelope = services.add_envelope(
            name="Groceries", base_amount=Decimal("120.00"), mode="reset"
        )

        assert envelope.id is not None
        assert envelope.base_amount == Decimal("120.00")
        assert envelope.balance == Decimal("120.00")
        assert Envelope.query.count() == 1


def test_add_envelope_rejects_invalid_mode(app):
    with app.app_context():
        with pytest.raises(ValueError):
            services.add_envelope(
                name="Groceries", base_amount=Decimal("120.00"), mode="other"
            )


def test_spend_updates_balance_and_logs_transaction(app):
    with app.app_context():
        envelope = Envelope(
            name="Dining",
            base_amount=Decimal("50.00"),
            balance=Decimal("50.00"),
            mode="reset",
        )
        db.session.add(envelope)
        db.session.commit()
        envelope_id = envelope.id

        updated = services.spend(envelope_id=envelope_id, amount=Decimal("20.00"))

        assert updated.balance == Decimal("30.00")
        transaction = Transaction.query.filter_by(
            envelope_id=envelope_id, type="spend"
        ).one()
        assert transaction.amount == Decimal("20.00")


def test_spend_rejects_unknown_envelope(app):
    with app.app_context():
        with pytest.raises(LookupError):
            services.spend(envelope_id=123, amount=Decimal("10.00"))


def test_deposit_updates_balance_and_logs_transaction(app):
    with app.app_context():
        envelope = Envelope(
            name="Dining",
            base_amount=Decimal("50.00"),
            balance=Decimal("50.00"),
            mode="reset",
        )
        db.session.add(envelope)
        db.session.commit()
        envelope_id = envelope.id

        updated = services.deposit(envelope_id=envelope_id, amount=Decimal("15.00"))

        assert updated.balance == Decimal("65.00")
        transaction = Transaction.query.filter_by(
            envelope_id=envelope_id, type="deposit"
        ).one()
        assert transaction.amount == Decimal("15.00")
