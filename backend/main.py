from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List
import sqlite3
from pathlib import Path
from graph_builder import get_graph_json

app = FastAPI(title='SAP O2C Graph System (Backend)')

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get('/graph/nodes')
def graph_nodes() -> Dict[str, Any]:
    """Return all graph nodes."""
    graph_data = get_graph_json()
    return {
        'nodes': graph_data['nodes'],
        'count': len(graph_data['nodes'])
    }

@app.get('/graph/edges')
def graph_edges() -> Dict[str, Any]:
    """Return all graph edges."""
    graph_data = get_graph_json()
    return {
        'edges': graph_data['edges'],
        'count': len(graph_data['edges'])
    }

@app.get('/graph/full')
def graph_full() -> Dict[str, Any]:
    """Return complete graph data (nodes + edges)."""
    return get_graph_json()

@app.get('/graph/entity/{entity_id}')
def graph_entity(entity_id: str) -> Dict[str, Any]:
    """Get details of a specific entity and its connections."""
    graph_data = get_graph_json()
    
    node = None
    for n in graph_data['nodes']:
        if n['id'] == entity_id:
            node = n
            break
    
    if not node:
        raise HTTPException(status_code=404, detail='Entity not found')
    
    related_edges = [e for e in graph_data['edges'] if e['source'] == entity_id or e['target'] == entity_id]
    
    return {
        'node': node,
        'connections': related_edges
    }

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
