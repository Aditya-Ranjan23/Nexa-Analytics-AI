# AI-Powered Analytics Assistant (Django + NVIDIA)

Current build includes:
- Full Django backend with analytics and AI chat APIs
- Modern dashboard frontend with KPI cards, trend chart, and assistant chat
- NVIDIA `build.nvidia.com` integration-ready service layer
- Role-aware dashboard views for CEO, Marketing Manager, and Team Member
- Session-based chat memory (conversation context persisted in DB)
- Pluggable analytics datasource layer (CSV now, DB connectors next)

## Quick Start

1. Install dependencies:
   - `python -m pip install -r requirements.txt`
2. Create environment file:
   - Copy `.env.example` to `.env`
   - Set `NVIDIA_API_KEY` from your `build.nvidia.com` account
3. Run migrations:
   - `python manage.py migrate`
4. Start server:
   - `python manage.py runserver`
5. Open:
   - `http://127.0.0.1:8000/`

## API Endpoints

- `GET /api/analytics/summary/`
  - Returns KPIs, trends, and channel performance (supports `?role=ceo|marketing_manager|team_member`)
- `GET /api/dashboard/role/`
  - Returns role-scoped widgets and KPI payload for dashboard personalization
- `POST /api/chat/`
  - Body: `{ "message": "...", "role": "marketing_manager", "session_id": 12 }`
  - Uses NVIDIA model when key is present, otherwise returns local fallback
  - Stores conversation history and reuses it as context memory
- `POST /api/data/upload/`
  - Multipart upload for `.csv/.xlsx/.xls` with auto schema detection (ads or generic)
  - Automatically calls NVIDIA to create a dashboard blueprint (KPI columns, trend metric, dimensions)
- `POST /api/data/upload-link/`
  - JSON body `{ "url": "https://..." }` to ingest a remote dataset file
  - Also generates and stores NVIDIA dashboard blueprint
- `POST /api/ingestion/run/`
  - Manual ingestion job trigger and status log record
- `GET/POST /api/dashboard/blueprint/`
  - Load effective blueprint for current user/session
  - Save blueprint override from Blueprint Editor
- `GET /health/`
  - Basic health check

## Project Structure

- `config/` Django project config
- `analytics_assistant/` backend app (views, analytics facade, engines, dataset pipeline, NVIDIA service)
- `templates/analytics_assistant/dashboard.html` frontend page
- `static/css/dashboard.css` dashboard styles
- `static/js/dashboard.js` dashboard interactivity
- `data/sales_data.csv` read-only seed dataset (used when no upload is active)
- `docs/` architecture, debt register, Phase 1 retrospective, Phase 2 roadmap

## Documentation

See [`docs/README.md`](docs/README.md) for the full documentation index.

## NVIDIA Integration Notes

- Keep API keys only in `.env`, never in frontend code.
- The backend endpoint `analytics_assistant/services.py` sends requests to:
  - `POST {NVIDIA_BASE_URL}/chat/completions`

## Role and Data Source Configuration

- Roles are resolved from authenticated user groups (if logged in) or request role parameter.
- Supported roles:
  - `ceo`
  - `marketing_manager`
  - `team_member`
- Set datasource in `.env`:
  - `ANALYTICS_SOURCE=csv` (default)
  - `ANALYTICS_SOURCE=postgres` to read from PostgreSQL table
- PostgreSQL mode:
  - Configure Django `DATABASES` to PostgreSQL
  - Set `ANALYTICS_TABLE=analytics_sales` (or your table name)
- Dataset support:
  - Ads schema (`date`, `channel`, `revenue`, `orders`, `ad_spend`, `conversion_rate`) gets ad-specific insights
  - Any other dataset with 2+ columns is accepted in generic analytics mode
- Dashboard persistence:
  - Current dataset and blueprint override are saved per logged-in user.
  - For anonymous visitors, state is saved by browser session key.
