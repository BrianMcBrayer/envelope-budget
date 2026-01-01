### Phase 1: Infrastructure & Persistence

[x] 1. **Add Dependencies:** Run `uv add flask-migrate flask-wtf`. Run `uv lock`.
[x] 2. **Docker Persistence:** Update `docker-compose.yml` to map a volume (e.g., `- ./data:/app/instance`) so the SQLite database survives container restarts. Update `Settings` in `app.py` to ensure the database path is absolute within that volume.
[x] 3. **Setup Flask-Migrate:** * Initialize `Flask-Migrate` in `app.py`.
* Delete the manual `ensure_schema` function.
* Generate the initial migration script using the CLI.



### Phase 2: Security & Architecture Refactor

[x] 4. **Enable CSRF Protection:** * Initialize `CSRFProtect` in `create_app`.
* **TDD:** Write a test in `tests/test_app.py` confirming that a `POST` request without a CSRF token now returns a `400/403` error.
* Update all templates to include `{{ csrf_token() }}` in forms and add the `X-CSRFToken` header to HTMX configurations in `base.html`.


[x] 5. **Model Logic Refactor:** * **TDD:** Write unit tests for the `Envelope` model methods before implementing them.
* Move logic for `spend()`, `deposit()`, and `apply_funding()` into the `Envelope` model class.
* Refactor routes in `app.py` to call these model methods instead of performing calculations in the view.



### Phase 3: Funding Logic & Concurrency

[x] 6. **Decouple Funding Sync:**
* **TDD:** Write a CLI test in `tests/test_cli.py` for a new command `budget-cli sync-funds`.
* Implement the `sync-funds` command in `cli.py`.
* Remove `sync_funding` from the `@app.before_request` hook in `app.py` to prevent race conditions and performance lag on page loads.


[x] 7. **Add Funding UI:**
* Update `partials/envelope_card.html` to include a "Deposit" form (calling the existing `/add` route).
* Use **Alpine.js** (`x-data`, `x-show`) to toggle between the "Spend" and "Deposit" inputs so the card remains compact.



### Phase 4: UX & Polishing

[x] 8. **HTMX Loading States:** * Add a CSS loading spinner or a "Processing..." state to the `spend-form`.
* Use HTMX `hx-indicator` to trigger the visibility of this state during requests.


[x] 9. **Progress Bar Logic:** * Update the `<progress>` bar in `envelope_card.html` to handle rollover scenarios where `balance > base_amount` (ensure it doesn't break visually).
* Add a CSS class to the progress bar to change its color if the balance is in "surplus."



---

### Exact commands for the Agent to run:

**To install new tools:**

```bash
uv add flask-migrate flask-wtf
uv lock

```

**To run the test suite (standard TDD loop):**

```bash
uv run pytest

```

**To initialize migrations:**

```bash
export FLASK_APP=src/budget_app/app.py
uv run flask db init
uv run flask db migrate -m "Initial migration"

```
