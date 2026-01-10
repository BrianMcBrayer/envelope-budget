from decimal import Decimal, ROUND_HALF_UP

from pydantic import BaseModel, Field, field_validator


TWOPLACES = Decimal("0.01")


def _parse_amount(raw: Decimal | str) -> Decimal:
    if isinstance(raw, Decimal):
        value = raw
    else:
        try:
            value = Decimal(str(raw))
        except Exception as exc:
            raise ValueError("Amount must be a number.") from exc
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


class EnvelopeCreate(BaseModel):
    name: str
    base_amount: Decimal
    mode: str

    @field_validator("name")
    @classmethod
    def name_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Envelope name is required.")
        return cleaned

    @field_validator("base_amount", mode="before")
    @classmethod
    def base_amount_decimal(cls, value: Decimal | str) -> Decimal:
        return _parse_amount(value)

    @field_validator("mode")
    @classmethod
    def mode_valid(cls, value: str) -> str:
        if value not in {"reset", "rollover"}:
            raise ValueError("Envelope mode must be reset or rollover.")
        return value


class TransactionCreate(BaseModel):
    amount: Decimal
    note: str | None = Field(default=None)

    @field_validator("amount", mode="before")
    @classmethod
    def amount_decimal(cls, value: Decimal | str) -> Decimal:
        amount = _parse_amount(value)
        if amount <= 0:
            raise ValueError("Amount must be positive.")
        return amount

    @field_validator("note")
    @classmethod
    def note_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None
