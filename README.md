# UnifyX

This repository contains a customer intelligence platform with a FastAPI backend and a React client.

## Structure

- `backend/` — API, data layer, models, scripts, and tests
- `client/` — frontend application
- `docs/` — architecture and methodology documentation

## Quick start

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn src.main:app --reload
```

### Frontend

```bash
cd client
npm install
npm run dev
```
