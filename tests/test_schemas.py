from decimal import Decimal

import pytest
from pydantic import ValidationError

from budget_app.schemas import EnvelopeCreate, TransactionCreate


def test_envelope_create_accepts_valid_data():
    model = EnvelopeCreate.model_validate(
        {"name": "Groceries", "base_amount": "120.00", "mode": "reset"}
    )

    assert model.name == "Groceries"
    assert model.base_amount == Decimal("120.00")
    assert model.mode == "reset"


def test_envelope_create_rejects_invalid_mode():
    with pytest.raises(ValidationError):
        EnvelopeCreate.model_validate(
            {"name": "Groceries", "base_amount": "120.00", "mode": "other"}
        )


def test_transaction_create_rejects_non_positive_amount():
    with pytest.raises(ValidationError):
        TransactionCreate.model_validate({"amount": "0.00"})

    with pytest.raises(ValidationError):
        TransactionCreate.model_validate({"amount": "-1.00"})


def test_transaction_create_rejects_invalid_amount():
    with pytest.raises(ValidationError):
        TransactionCreate.model_validate({"amount": "nope"})
