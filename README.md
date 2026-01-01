# 💹 Envelope Budget

**Keep spending intentional and month-to-month momentum visible.**

Envelope Budget is a self-hosted, lightweight personal finance tool designed for the modern web. Unlike complex accounting software, this app focuses on the **Envelope Method**: allocating specific amounts to categories and seeing exactly what you have left to spend.

---

## ✨ Features

* **Dual Funding Modes:** Choose between "Reset" (for fixed monthly bills) and "Rollover" (for accumulating savings or sinking funds).
* **Automatic Monthly Sync:** The system detects month-over-month gaps and automatically applies funding based on your envelope settings.
* **Modern Interactive UI:** Built with **HTMX** and **Alpine.js** for a reactive, "Single Page App" feel without the complexity of a heavy JavaScript framework.
* **Developer-Centric:** Secure CLI for password management and full TDD (Test-Driven Development) support.
* **Self-Hosted Privacy:** Your data stays in your own SQLite database.

---

## 🛠 The Tech Stack

| Layer | Technology |
| --- | --- |
| **Backend** | Python 3.12+, Flask, SQLAlchemy (ORM) |
| **Frontend** | HTMX (Live updates), Alpine.js (State), Pico CSS (Theming) |
| **Settings** | Pydantic-Settings (Env-based config) |
| **Tooling** | `uv` (Package management), Rich (CLI formatting) |
| **Deployment** | Docker, Gunicorn |

---

## 🚀 Quickstart

### 1. Prerequisites

Ensure you have `uv` installed (the fastest Python package manager).

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

```

### 2. Installation & Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd budget-app

# Install dependencies and create a virtual environment
uv sync

# Generate your secure app password
uv run budget-cli password set

```

### 3. Run the App

```bash
uv run python src/budget_app/app.py

```

Visit `http://127.0.0.1:5000` and log in with the password you just created.

---

## 📦 Docker Deployment

The simplest way to stay up and running 24/7 is via Docker Compose.

1. Create a `.env` file:
```env
APP_PASSWORD='your-scrypt-hashed-password'
SECRET_KEY='your-random-secret-key'
DATABASE_URL='sqlite:////app/instance/budget.db'

```


2. Launch the stack:
```bash
docker-compose up -d

```



---

## 💡 Core Concepts: Reset vs. Rollover

| Mode | Behavior | Best Used For... |
| --- | --- | --- |
| **Reset** | At the start of a new month, the balance is set exactly to the Base Amount. | Rent, Netflix, Internet Bill. |
| **Rollover** | New funds are *added* to whatever was left over from last month. | Groceries, Hobbies, Vacation Fund. |

---

## 🛠 Administration CLI

The `budget-cli` tool manages your installation's security and state.

* **Set Password:** `uv run budget-cli password set`
* **Verify Hash:** `uv run budget-cli password verify --password <text>`
* **Manual Fund Sync:** `uv run budget-cli sync-funds` (Useful if you've been offline for months)

---

## 🧪 Development & Testing

This project follows strict **Test-Driven Development (TDD)**. Before contributing, please review `AGENTS.md`.

**Run the test suite:**

```bash
uv run pytest

```

The suite includes:

* **Logic Tests:** Validating Decimal rounding and funding math.
* **Integration Tests:** Testing Flask routes and CSRF protection.
* **CLI Tests:** Ensuring password hashing remains robust.

---

## 🔐 Security

* **Hashed Passwords:** Uses `scrypt` hashing via Werkzeug.
* **CSRF Protection:** Every state-changing request is protected by `Flask-WTF`.
* **Secure Cookies:** Session cookies are set to `HttpOnly` and `SameSite=Lax` by default.
