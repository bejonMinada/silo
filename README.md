# Silo

Local onboarding, training, and knowledge management prototype.

## Structure

- `/backend`: FastAPI + SQLAlchemy + SQLite API
- `/frontend`: React + Tailwind (Vite) UI

## Quickstart

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
export VITE_API_BASE_URL=http://localhost:8000/api
npm run dev
```

Backend defaults to `http://localhost:8000`.
Frontend defaults to `http://localhost:5173`.
