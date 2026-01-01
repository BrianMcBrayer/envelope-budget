from __future__ import annotations

from datetime import date
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
from pydantic_settings import BaseSettings, SettingsConfigDict
from werkzeug.security import check_password_hash


db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
TWOPLACES = Decimal("0.01")


class Envelope(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    balance = db.Column(db.Numeric(12, 2), nullable=False)
    base_amount = db.Column(db.Numeric(12, 2), nullable=False)
    mode = db.Column(db.String(16), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def spend(self, amount: Decimal) -> None:
        if amount <= 0:
            raise ValueError("Spend amount must be positive.")
        self.balance = self.balance - amount

    def deposit(self, amount: Decimal) -> None:
        if amount <= 0:
            raise ValueError("Deposit amount must be positive.")
        self.balance = self.balance + amount

    def apply_funding(self, months: int = 1) -> None:
        if months <= 0:
            raise ValueError("Funding months must be positive.")
        if self.mode == "reset":
            self.balance = self.base_amount
        else:
            self.balance = self.balance + (self.base_amount * months)


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

    with app.app_context():
        db.create_all()
        sync_funding(app)

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
        envelopes = Envelope.query.filter_by(is_active=True).order_by(Envelope.name.asc()).all()
        return render_template("index.html", envelopes=envelopes)

    @app.post("/envelopes")
    @auth_required
    def add_envelope():
        name = request.form.get("name", "").strip()
        base_amount = parse_amount(request.form.get("base_amount", "0"))
        mode = request.form.get("mode", "reset")
        if not name:
            abort(400)
        if mode not in {"reset", "rollover"}:
            abort(400)
        envelope = Envelope(
            name=name,
            balance=base_amount,
            base_amount=base_amount,
            mode=mode,
            is_active=True,
        )
        db.session.add(envelope)
        db.session.commit()
        return redirect(url_for("index"))

    @app.post("/envelopes/<int:envelope_id>/spend")
    @auth_required
    def spend(envelope_id: int):
        envelope = get_envelope_or_404(envelope_id)
        amount = parse_amount(request.form.get("amount", "0"))
        try:
            envelope.spend(amount)
        except ValueError:
            abort(400)
        db.session.commit()
        return render_envelope_or_redirect(envelope)

    @app.post("/envelopes/<int:envelope_id>/add")
    @auth_required
    def add_funds(envelope_id: int):
        envelope = get_envelope_or_404(envelope_id)
        amount = parse_amount(request.form.get("amount", "0"))
        try:
            envelope.deposit(amount)
        except ValueError:
            abort(400)
        db.session.commit()
        return render_envelope_or_redirect(envelope)

    @app.post("/envelopes/<int:envelope_id>/archive")
    @auth_required
    def archive_envelope(envelope_id: int):
        envelope = get_envelope_or_404(envelope_id)
        envelope.is_active = False
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
