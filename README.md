# Garmin Dashboard

A local health dashboard that pulls daily/activity data from Garmin Connect and
serves it at `http://localhost:5557` — steps, resting HR, stress, Body Battery,
sleep, VO2max/fitness trends, and a per-activity training report, plus an
optional AI-generated daily analysis via the Gemini API.

## How it works

- **`app.py`** — a Flask app that logs into Garmin Connect via
  [`garminconnect`](https://github.com/cyberjunky/python-garminconnect)
  (session token cached under `~/.garminconnect`), fetches daily snapshots,
  activities, and fitness stats, and caches responses to `cache/*.json` for
  15 minutes (`CACHE_TTL`) to avoid hammering Garmin's API. It computes
  trends, streaks, goal progress, and rule-based training insights, and (if
  `GEMINI_API_KEY` is set) can ask Gemini for a free-text daily analysis,
  cached separately for 3 hours.
- **`web/`** — a React + TypeScript + Vite SPA (Chart.js, HeroUI, Tailwind)
  served by Flask from `web/dist` at `/`. It talks to the JSON API under
  `/api/*` (`/api/state`, `/api/data`, `/api/report`, `/api/activity/<id>`,
  `/api/goals`, `/api/analysis`).
- **`daily_fetch.sh`** — run once a day via `launchd`/cron: clears the cache
  and re-fetches 60 days of daily data + 20 recent activities + fitness
  stats, records success/failure to a sync-status file, and fires a macOS
  notification on failure.
- **`launch.sh`** — starts the Flask server in the background if it isn't
  already listening on port 5557, then opens it in the browser. Used by a
  Dock app and by the `/garmin-dash` Claude Code skill.
- **`run.sh`** — simplest way to start the server in the foreground for
  development.

## Setup

1. Python 3.11 (see `.python-version`), a virtualenv at `.venv/`, with
   `flask`, `garminconnect`, `requests`, and `python-dotenv` installed.
2. Create a `.env` file in the repo root:
   ```
   GARMIN_EMAIL=you@example.com
   GARMIN_PASSWORD=your-garmin-password
   GEMINI_API_KEY=your-gemini-key   # optional, enables the AI analysis panel
   ```
3. Build the frontend once (or after changing `web/src`):
   ```
   cd web && npm install && npm run build
   ```
4. Run it:
   ```
   ./run.sh          # foreground, for development
   ./launch.sh        # background + opens the browser
   ```

First login may prompt for an MFA code in the terminal; after that, Garmin
Connect's session token is cached under `~/.garminconnect` so subsequent runs
don't need it again.

## Scheduling the daily fetch

Point a `launchd` job (or cron) at `daily_fetch.sh` to pre-warm the cache each
morning — the dashboard itself only re-fetches from Garmin when the 15-minute
cache expires, so a stale cache otherwise means the first visit of the day is
slow.
