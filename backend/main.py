from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List
import sqlite3
from pathlib import Path

app = FastAPI(title='SAP O2C Graph System (Backend)')

DB_PATH = Path(__file__).resolve().parent / 'o2c.db'

def get_db_connection():
    return sqlite3.connect(DB_PATH)

@app.get('/')
def root():
    return {'status': 'ok', 'message': 'SAP O2C Graph System backend'}

@app.get('/healthz')
def healthz():
    return {'status': 'healthy'}

@app.get('/graph/tables')
def graph_tables() -> Dict[str, List[str]]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        return {'tables': tables}
    finally:
        conn.close()

@app.get('/graph/sample/{table_name}')
def graph_sample(table_name: str, limit: int = 20) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM '{table_name}' LIMIT ?", (limit,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        payload = [dict(zip(columns, row)) for row in rows]
        return {'table': table_name, 'rows': payload}
    except sqlite3.OperationalError:
        raise HTTPException(status_code=404, detail='Table not found')
    finally:
        conn.close()

class QueryRequest(BaseModel):
    prompt: str

@app.post('/query')
def query_graph(req: QueryRequest) -> Dict[str, Any]:
    text = req.prompt.strip()
    if not text:
        raise HTTPException(status_code=400, detail='Prompt is required')

    blocking = ['who is', 'define', 'philosophy', 'poem', 'movie']
    if any(b in text.lower() for b in blocking):
        return {'query': text, 'answer': 'This system only answers dataset-related O2C questions.'}

    if 'billing documents' in text.lower() and 'highest number' in text.lower():
        sql = "SELECT material, COUNT(*) AS billing_count FROM billing_document_items GROUP BY material ORDER BY billing_count DESC LIMIT 10"
    elif 'trace the full flow' in text.lower():
        sql = "SELECT * FROM sales_order_headers LIMIT 10"
    else:
        return {'query': text, 'answer': 'Query translation rule not implemented yet. Use a known supported template.'}

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        payload = [dict(zip(columns, row)) for row in rows]
        return {
            'query': text,
            'sql': sql,
            'rows': payload,
            'answer': 'Data-backed response returned. In production this would be converted to NL via LLM.'
        }
    finally:
        conn.close()
