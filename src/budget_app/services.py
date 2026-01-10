from decimal import Decimal

from budget_app.app import Envelope, db


def add_envelope(name: str, base_amount: Decimal, mode: str) -> Envelope:
    if not name or not name.strip():
        raise ValueError("Envelope name is required.")
    if mode not in {"reset", "rollover"}:
        raise ValueError("Envelope mode must be reset or rollover.")
    envelope = Envelope(
        name=name.strip(),
        balance=base_amount,
        base_amount=base_amount,
        mode=mode,
        is_active=True,
    )
    db.session.add(envelope)
    db.session.commit()
    return envelope


def spend(envelope_id: int, amount: Decimal, note: str | None = None) -> Envelope:
    envelope = db.session.get(Envelope, envelope_id)
    if envelope is None:
        raise LookupError("Envelope not found.")
    envelope.spend(amount, note=note)
    db.session.commit()
    return envelope


def deposit(envelope_id: int, amount: Decimal, note: str | None = None) -> Envelope:
    envelope = db.session.get(Envelope, envelope_id)
    if envelope is None:
        raise LookupError("Envelope not found.")
    envelope.deposit(amount, note=note)
    db.session.commit()
    return envelope
