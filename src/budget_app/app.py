from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    session,
    url_for,
    has_app_context,
)
from flask_wtf import CSRFProtect
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Numeric, TypeDecorator
from pydantic_settings import BaseSettings, SettingsConfigDict
from werkzeug.security import check_password_hash
from pydantic import ValidationError


db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
TWOPLACES = Decimal("0.01")


class RoundedNumeric(TypeDecorator):
    impl = Numeric
    cache_ok = True

    def __init__(self, precision: int, scale: int, **kwargs):
        self.precision = precision
        self.scale = scale
        super().__init__(precision=precision, scale=scale, **kwargs)

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(
            Numeric(self.precision, self.scale, decimal_return_scale=self.scale + 4)
        )

    def process_bind_param(self, value: Decimal | None, dialect):
        if value is None:
            return None
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    def process_result_value(self, value: Decimal | None, dialect):
        if value is None:
            return None
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            if not isinstance(value, Decimal):
                value = Decimal(str(value))
            return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

        return process


class Envelope(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    balance = db.Column(RoundedNumeric(12, 2), nullable=False)
    base_amount = db.Column(RoundedNumeric(12, 2), nullable=False)
    mode = db.Column(db.String(16), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    archived_at = db.Column(db.DateTime, nullable=True)
    transactions = db.relationship(
        "Transaction", back_populates="envelope", cascade="all, delete-orphan"
    )

    def spend(self, amount: Decimal, note: str | None = None) -> None:
        if amount <= 0:
            raise ValueError("Spend amount must be positive.")
        self.balance = self.balance - amount
        self.transactions.append(
            Transaction(amount=amount, note=note, type="spend")
        )

    def deposit(self, amount: Decimal, note: str | None = None) -> None:
        if amount <= 0:
            raise ValueError("Deposit amount must be positive.")
        self.balance = self.balance + amount
        self.transactions.append(
            Transaction(amount=amount, note=note, type="deposit")
        )

    def apply_funding(self, months: int = 1) -> None:
        if months <= 0:
            raise ValueError("Funding months must be positive.")
        if self.mode == "reset":
            self.balance = self.base_amount
        else:
            self.balance = self.balance + (self.base_amount * months)

    def archive(self) -> None:
        if self.archived_at is None:
            self.archived_at = datetime.now(timezone.utc)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    envelope_id = db.Column(db.Integer, db.ForeignKey("envelope.id"), nullable=False)
    amount = db.Column(RoundedNumeric(12, 2), nullable=False)
    note = db.Column(db.String(255), nullable=True)
    type = db.Column(db.String(16), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    envelope = db.relationship("Envelope", back_populates="transactions")


class SystemState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    last_funded_month = db.Column(db.String(7), nullable=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_password: str | None = None
    secret_key: str = "dev-secret"
    database_url: str = "sqlite:////app/instance/budget.db"


def create_app(config: dict | None = None) -> Flask:
    settings = Settings()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_mapping(
        SECRET_KEY=settings.secret_key,
        SQLALCHEMY_DATABASE_URI=settings.database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    @app.template_filter("currency")
    def currency_filter(value: Decimal) -> str:
        return format_currency(value)

    def password_is_valid(password: str) -> bool:
        hashed = settings.app_password
        if not hashed:
            return False
        return check_password_hash(hashed, password)

    def auth_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("logged_in"):
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped

    @app.get("/login")
    def login():
        return render_template("login.html")

    @app.post("/login")
    def login_post():
        password = request.form.get("password", "")
        if password_is_valid(password):
            session["logged_in"] = True
            return redirect(url_for("index"))
        return render_template("login.html", error="Invalid password"), 401

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    @auth_required
    def index():
        envelopes = (
            Envelope.query.filter(Envelope.archived_at.is_(None))
            .order_by(Envelope.name.asc())
            .all()
        )
        total_available = sum((env.balance for env in envelopes), Decimal("0.00"))
        monthly_budgeted = sum((env.base_amount for env in envelopes), Decimal("0.00"))
        return render_template(
            "index.html",
            envelopes=envelopes,
            total_available=total_available,
            monthly_budgeted=monthly_budgeted,
        )

    @app.post("/envelopes")
    @auth_required
    def add_envelope():
        from budget_app import services
        from budget_app.schemas import EnvelopeCreate

        try:
            payload = EnvelopeCreate.model_validate(request.form.to_dict())
        except ValidationError:
            abort(400)
        services.add_envelope(
            name=payload.name, base_amount=payload.base_amount, mode=payload.mode
        )
        return redirect(url_for("index"))

    @app.post("/envelopes/<int:envelope_id>/spend")
    @auth_required
    def spend(envelope_id: int):
        from budget_app import services
        from budget_app.schemas import TransactionCreate

        try:
            payload = TransactionCreate.model_validate(request.form.to_dict())
            envelope = services.spend(
                envelope_id=envelope_id,
                amount=payload.amount,
                note=payload.note,
            )
        except LookupError:
            abort(404)
        except (ValueError, ValidationError) as exc:
            envelope = get_envelope_or_404(envelope_id)
            return render_envelope_with_error(envelope, validation_message(exc), 422)
        return render_envelope_or_redirect(envelope)

    @app.post("/envelopes/<int:envelope_id>/add")
    @auth_required
    def add_funds(envelope_id: int):
        from budget_app import services
        from budget_app.schemas import TransactionCreate

        try:
            payload = TransactionCreate.model_validate(request.form.to_dict())
            envelope = services.deposit(
                envelope_id=envelope_id,
                amount=payload.amount,
                note=payload.note,
            )
        except LookupError:
            abort(404)
        except (ValueError, ValidationError) as exc:
            envelope = get_envelope_or_404(envelope_id)
            return render_envelope_with_error(envelope, validation_message(exc), 422)
        return render_envelope_or_redirect(envelope)

    @app.post("/envelopes/<int:envelope_id>/archive")
    @auth_required
    def archive_envelope(envelope_id: int):
        envelope = get_envelope_or_404(envelope_id)
        envelope.archive()
        db.session.commit()
        return redirect(url_for("index"))

    return app


def parse_amount(raw: str) -> Decimal:
    try:
        return Decimal(raw).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    except Exception:
        abort(400)


def format_currency(value: Decimal) -> str:
    return f"${value:.2f}"


def render_envelope_or_redirect(envelope: Envelope):
    if request.headers.get("HX-Request") == "true":
        return render_template("partials/envelope_card.html", env=envelope)
    return redirect(url_for("index"))


def render_envelope_with_error(envelope: Envelope, message: str, status_code: int):
    if request.headers.get("HX-Request") == "true":
        return (
            render_template("partials/envelope_card.html", env=envelope, error=message),
            status_code,
        )
    abort(400)


def validation_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        errors = exc.errors()
        if errors:
            message = errors[0].get("msg")
            if message:
                return message
        return "Invalid input."
    message = str(exc).strip()
    return message or "Invalid input."


def get_envelope_or_404(envelope_id: int) -> Envelope:
    envelope = db.session.get(Envelope, envelope_id)
    if envelope is None:
        abort(404)
    return envelope


def get_current_month() -> str:
    return date.today().strftime("%Y-%m")


def _month_difference(start_month: str, end_month: str) -> int:
    start_year, start_month_num = map(int, start_month.split("-"))
    end_year, end_month_num = map(int, end_month.split("-"))
    return (end_year - start_year) * 12 + (end_month_num - start_month_num)


def sync_funding(app: Flask) -> None:
    def _sync() -> None:
        current_month = get_current_month()
        state = SystemState.query.order_by(SystemState.id.asc()).first()
        if state is None:
            db.session.add(SystemState(last_funded_month=current_month))
            db.session.commit()
            return

        month_gap = _month_difference(state.last_funded_month, current_month)
        if month_gap <= 0:
            return

        envelopes = Envelope.query.all()
        for env in envelopes:
            env.apply_funding(months=month_gap)
        state.last_funded_month = current_month
        db.session.commit()

    if has_app_context():
        _sync()
        return
    with app.app_context():
        _sync()


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
