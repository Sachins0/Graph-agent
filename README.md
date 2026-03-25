# SAP O2C Graph System

## Overview
This project implements a graph-based data modeling and query system for SAP Order-to-Cash data stored in `sap-o2c-data`.

## Structure
- `backend/`: FastAPI server, data ingestion, graph engine
- `frontend/`: React + Vite UI, force-directed graph and chat interface
- `sap-o2c-data/`: raw JSONL dataset (already present in this repository)

## Step 1: Setup

### Backend
1. `cd backend`
2. `python -m venv venv`
3. `source venv/bin/activate` (Windows: `venv\Scripts\activate`)
4. `pip install -U pip`
5. `pip install -r requirements.txt`
6. Create `.env` in backend and add:
   - `GEMINI_API_KEY=your_gemini_api_key_here`
   - `DATABASE_URL=./o2c.db`
7. Run ingestion:
   - `python data_ingest.py`
8. Start server:
   - `uvicorn main:app --reload --port 8000`

### Frontend
1. `cd frontend`
2. `npm install`
3. `npm run dev`

## Step 2: Data Ingestion (JSONL → SQLite)

### What intake does
- Reads every folder under `sap-o2c-data` with `*.jsonl`
- Infers table columns from first row in each file
- Creates typed SQLite tables (best-effort: INT/FLOAT/BOOL/STRING)
- Data inserted with `OR IGNORE` idempotency

### Run it
1. `cd backend`
2. `source venv/bin/activate`
3. `python data_ingest.py`
4. Verify DB file created: `ls -l o2c.db`

### Quick DB validation
- `sqlite3 o2c.db` then:
  - `SELECT name FROM sqlite_master WHERE type='table';`
  - `SELECT COUNT(*) FROM sales_order_headers;`

## Step 3: API tests

### Manual API test 1 (server is up)
- `curl http://localhost:8000/healthz`
- `curl http://localhost:8000/graph/tables`
- `curl http://localhost:8000/graph/sample/sales_order_headers?limit=5`

### Manual API test 2 (query)
- `curl -X POST http://localhost:8000/query -H 'Content-Type: application/json' -d '{"prompt": "Which products are associated with the highest number of billing documents?"}'`

## Step 4: Frontend test

- Start frontend with `npm run dev`
- Open `http://localhost:5173`
- Type a query and click Ask

## Notes
- `main.py` includes guardrail stub rejecting unrelated questions.
- Next step: implement full NL→SQL translation with Google Gemini and graph traversal endpoints.

## Current Status (✅ Fixed)

### Backend ✅
- Dependencies installed
- Data ingestion working (19 tables loaded)
- API endpoints functional:
  - `/healthz` ✅
  - `/graph/tables` ✅ (returns all table names)
  - `/graph/sample/{table}` ✅ (returns sample rows)
  - `/query` ✅ (executes SQL, returns data)

### Frontend ✅
- npm install fixed with `--legacy-peer-deps`
- React + Vite setup ready

### Database ✅
- SQLite DB created with all SAP O2C tables
- Sample query working: products with highest billing document counts

## Next steps
- Implement link analysis & graph engine:
  - `backend/graph_builder.py` (NetworkX graph from SQLite)
  - `/graph/nodes`, `/graph/edges` endpoints
  - connect `frontend` graph visualization to backend data
- Implement LLM query translation:
  - `backend/llm.py`
  - integrate Google Gemini (or other free API) for prompt→SQL and NL reponse
  - better guardrails + one-shot example set

