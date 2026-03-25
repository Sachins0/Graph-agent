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
2. `python -m venv .venv`
3. `source .venv/bin/activate`
4. `pip install -U pip`
5. `pip install -e .` (or `pip install fastapi uvicorn networkx sqlalchemy pydantic httpx python-dotenv`)
6. `uvicorn main:app --reload --port 8000`

### Frontend
1. `cd frontend`
2. `npm install`
3. `npm run dev`

## Next steps
- Implement ingestion pipeline in `backend/data_ingest.py`
- Build graph creation in `backend/graph_builder.py`
- Add LLM query translation and guardrails in `backend/llm.py`
- Expand endpoints in `backend/main.py` for `/graph/nodes`, `/graph/edges`, `/query`

## Notes
- We are using SQLite for zero-admin DB and NetworkX for in-memory graph operations.
- The 1st phase is complete: project structure + starter files.
