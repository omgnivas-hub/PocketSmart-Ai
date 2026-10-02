# PocketSmart AI: Budget & Recommendation Assistant

FastAPI + Gemini app with three planners (Home interior, Party, Jewelry), user accounts,
saved history, and shopping links for Amazon, Flipkart, IKEA, Swiggy, Zomato, OYO and more.

## Quick start (VS Code)

1. **Install** Python 3.10+ (https://python.org) and VS Code with the *Python* extension.
2. **Open the project:** *File > Open Workspace from File...* and pick `PocketSmart-AI.code-workspace`
   (or *File > Open Folder...* and pick this folder). Accept the "install recommended extensions" prompt.
3. **Open a terminal:** *Terminal > New Terminal*, then create and activate a virtual environment:

   | OS | Commands |
   |----|----------|
   | Windows (PowerShell) | `python -m venv .venv` then `.venv\Scripts\Activate.ps1` |
   | macOS / Linux | `python3 -m venv .venv` then `source .venv/bin/activate` |

   If PowerShell blocks the script, run `Set-ExecutionPolicy -Scope Process RemoteSigned` once and retry.
   If VS Code asks to use the new environment, click **Yes**.
4. **Install dependencies:** `pip install -r requirements.txt`
5. **Configure:** copy `.env.example` to `.env` (`copy .env.example .env` on Windows, `cp .env.example .env` elsewhere), then:
   * paste your Gemini key into `GOOGLE_API_KEY` (free: https://aistudio.google.com/apikey), and
   * set `SECRET_KEY` to a long random string:
     `python -c "import secrets; print(secrets.token_urlsafe(48))"`

   No key? Skip it. The app runs in **demo mode** with built-in rule-based suggestions.
6. **Run:** `python main.py`, or press **F5** and choose *PocketSmart: run server (debug)*.
7. **Open** http://127.0.0.1:8000, click **Get started**, create an account, and try each planner.

## Testing

```
pip install -r requirements-dev.txt
pytest -v
```

The tests never call Gemini (demo mode is forced and the AI path is stubbed). You can also run them from the
VS Code Testing panel (flask icon).

Manual checklist: register, log in, run each planner, upload an outfit photo in the Jewelry planner, open
*History > View full details*, log out. A badge on each result says **Gemini AI** or **Demo mode**.

## Project structure

```
main.py             FastAPI app, routes, uploads, sessions
gemini_utils.py     Prompts, Gemini calls, JSON parsing, validation, shopping links
fallback.py         Rule-based plans (used with no API key, on AI errors, or if the AI overspends)
auth.py             bcrypt password hashing, JWT cookie auth
database.py         SQLite: users and history
models.py           Pydantic request validation
config.py           Environment/.env settings
templates/          Jinja2 pages (base, index, login, register, dashboard, 3 planners, history)
static/css|js       Styles and frontend logic
tests/test_app.py   End-to-end tests
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/`, `/login`, `/register` | Public pages |
| POST | `/register` | Create account (JSON) |
| POST | `/token` | Log in (form data), sets HttpOnly cookie |
| GET/POST | `/logout` | Log out |
| GET | `/dashboard`, `/home-planner`, `/party-planner`, `/jewelry-planner`, `/history` | Protected pages |
| POST | `/home-budget` (alias `/generate-home`) | Home plan (JSON) |
| POST | `/party-budget` (alias `/generate-party`) | Party plan (JSON) |
| POST | `/jewelry-budget` (alias `/generate-jewelry`) | Jewelry plan (multipart, optional `image`) |
| GET | `/recommendation-history`, `/recommendation-details/{id}` | Saved plans |
| GET / POST | `/session-info`, `/session-data` | Session metadata |
| GET | `/health` | Status and whether Gemini is enabled |

Interactive API docs: http://127.0.0.1:8000/docs

## How the AI part works

Gemini returns item names, **unit prices**, quantities and search terms as JSON. The server recomputes every total,
allocation and the remaining budget itself. If a plan is over budget, Gemini gets one retry with a correction
note; if it is still over, or Gemini fails, `fallback.py` builds the plan. Prices are estimates, and shopping links
are search links, not verified product pages.

## Troubleshooting

* **Badge says "Demo mode":** the key is missing or still the placeholder. Set `GOOGLE_API_KEY` in `.env` and restart.
* **"Gemini was unavailable (...)" notice:** check the key, your network, and the model name. Model names change:
  see https://ai.google.dev/gemini-api/docs/models and update `GEMINI_MODEL`. The terminal shows the full error.
* **Logged out after every restart:** set a fixed `SECRET_KEY` in `.env`.
* **`ModuleNotFoundError`:** the virtual environment is not active or step 4 was skipped.
* **Port 8000 busy:** set `PORT=8001` in `.env`, or run `python main.py` after stopping the other process.
* **Reset all data:** stop the server and delete `pocketsmart.db`.

## Security notes

* Never commit `.env`; rotate any API key that has appeared in a screenshot or document.
* For deployment: HTTPS, `COOKIE_SECURE=true`, a strong `SECRET_KEY`, and a shared session store if you run more than one worker.
* Outfit photos are re-encoded, size-limited, and deleted after analysis unless `KEEP_UPLOADS=true`.
