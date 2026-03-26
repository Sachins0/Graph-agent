from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import sqlite3, json, asyncio
from pathlib import Path
from datetime import datetime

from graph_builder import get_graph_json, get_graph_stats, trace_billing_flow
from llm import get_llm_service
from guardrails import get_guardrails, QueryCategory

app = FastAPI(title='SAP O2C Graph System')

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = Path(__file__).resolve().parent / 'o2c.db'


@app.on_event("startup")
async def startup_event():
    """Pre-build graph and warm up LLM singleton at startup."""
    print("🚀 Starting SAP O2C Graph System...")
    get_graph_json()        # builds + caches graph
    get_llm_service()       # initialises Groq client
    get_guardrails()        # initialises guardrails
    print("✅ All systems ready.")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Basic ──────────────────────────────────────────────────────────

@app.get('/')
def root():
    return {'status': 'ok', 'message': 'SAP O2C Graph System backend'}

@app.get('/healthz')
def healthz():
    data = get_graph_json()
    return {
        'status': 'healthy',
        'graph_nodes': len(data['nodes']),
        'graph_edges': len(data['edges']),
    }


# ── Graph endpoints ────────────────────────────────────────────────

@app.get('/graph/tables')
def graph_tables():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return {'tables': [r[0] for r in rows]}
    finally:
        conn.close()

@app.get('/graph/sample/{table_name}')
def graph_sample(table_name: str, limit: int = 20):
    conn = get_db()
    try:
        cursor = conn.execute(f'SELECT * FROM "{table_name}" LIMIT ?', (limit,))
        cols = [d[0] for d in cursor.description]
        return {'table': table_name, 'rows': [dict(zip(cols, r)) for r in cursor.fetchall()]}
    except sqlite3.OperationalError:
        raise HTTPException(status_code=404, detail='Table not found')
    finally:
        conn.close()

@app.get('/graph/nodes')
def graph_nodes():
    data = get_graph_json()
    return {'nodes': data['nodes'], 'count': len(data['nodes'])}

@app.get('/graph/edges')
def graph_edges():
    data = get_graph_json()
    return {'edges': data['edges'], 'count': len(data['edges'])}

@app.get('/graph/full')
def graph_full():
    return get_graph_json()

@app.get('/graph/stats')
def graph_stats():
    """Return node/edge type breakdown — used by UI stats panel."""
    return get_graph_stats()

@app.get('/graph/entity/{entity_id:path}')
def graph_entity(entity_id: str):
    data = get_graph_json()
    node = next((n for n in data['nodes'] if n['id'] == entity_id), None)
    if not node:
        raise HTTPException(status_code=404, detail='Entity not found')
    connections = [
        e for e in data['edges']
        if e['source'] == entity_id or e['target'] == entity_id
    ]
    return {**node['properties'], **{'id': node['id'], 'type': node['type'],
                                      'label': node['label'], 'connections': connections}}

@app.get('/graph/trace/{billing_document}')
def graph_trace(billing_document: str):
    """Trace full O2C flow for a billing document: SO→Delivery→Billing→JE→Payment."""
    result = trace_billing_flow(billing_document)
    if 'error' in result:
        raise HTTPException(status_code=404, detail=result['error'])
    return result

@app.post('/graph/refresh')
def graph_refresh():
    """Force rebuild the graph cache."""
    data = get_graph_json(force_rebuild=True)
    return {'status': 'refreshed', 'nodes': len(data['nodes']), 'edges': len(data['edges'])}


# ── Query endpoint ─────────────────────────────────────────────────

class QueryRequest(BaseModel):
    prompt:      str
    include_sql: bool = True
    streaming:   bool = False

@app.post('/query')
def query_graph(req: QueryRequest):
    text = req.prompt.strip()
    if not text:
        raise HTTPException(status_code=400, detail='Prompt is required')

    guardrails = get_guardrails()
    is_safe, message, category = guardrails.check_query(text)

    if not is_safe:
        return {
            'query':    text,
            'answer':   message,
            'category': category.value,
            'blocked':  True,
            'hint':     guardrails.get_context_hint(text),
        }

    llm = get_llm_service()
    sql, is_valid = llm.translate_nl_to_sql(text)

    if not is_valid or not sql:
        return {
            'query':  text,
            'answer': 'I could not generate a valid query. Please rephrase your question.',
            'hint':   guardrails.get_context_hint(text),
        }

    conn = get_db()
    try:
        cursor = conn.execute(sql)
        cols    = [d[0] for d in cursor.description]
        payload = [dict(zip(cols, row)) for row in cursor.fetchall()]

        answer = llm.synthesize_answer(text, sql, payload)
        llm.add_to_history(text, answer)

        # Extract entity IDs from results for frontend highlight
        highlight_ids = _extract_highlight_ids(payload)

        result: Dict[str, Any] = {
            'query':         text,
            'answer':        answer,
            'rows':          payload,
            'row_count':     len(payload),
            'category':      category.value,
            'highlight_ids': highlight_ids,
        }
        if req.include_sql:
            result['sql'] = sql
        return result

    except sqlite3.Error as e:
        return {
            'query':  text,
            'answer': f'Database error: {str(e)}. Please try rephrasing.',
            'hint':   guardrails.get_context_hint(text),
        }
    finally:
        conn.close()


def _extract_highlight_ids(rows: List[Dict]) -> List[str]:
    """Try to map result rows to graph node IDs for frontend highlighting."""
    ids = []
    for row in rows[:20]:
        if 'billingDocument' in row:
            ids.append(f"BH:{row['billingDocument']}")
        if 'salesOrder' in row:
            ids.append(f"SO:{row['salesOrder']}")
        if 'deliveryDocument' in row:
            ids.append(f"DH:{row['deliveryDocument']}")
        if 'accountingDocument' in row:
            ids.append(f"JE:{row['accountingDocument']}")
        if 'customer' in row or 'soldToParty' in row:
            cid = row.get('customer') or row.get('soldToParty')
            ids.append(f"CUST:{cid}")
    return list(set(ids))


# ── Streaming endpoint ─────────────────────────────────────────────

@app.post('/query/streaming')
async def query_streaming(req: QueryRequest):
    """Streaming NDJSON endpoint — each line is a JSON event."""
    text = req.prompt.strip()
    if not text:
        raise HTTPException(status_code=400, detail='Prompt is required')

    async def event_stream():
        guardrails = get_guardrails()
        is_safe, message, category = guardrails.check_query(text)

        if not is_safe:
            yield json.dumps({'type': 'error', 'message': message, 'blocked': True}) + '\n'
            return

        yield json.dumps({'type': 'status', 'message': 'Translating to SQL...'}) + '\n'
        await asyncio.sleep(0)

        llm = get_llm_service()
        sql, is_valid = llm.translate_nl_to_sql(text)

        if not is_valid:
            yield json.dumps({'type': 'error', 'message': 'Could not generate SQL'}) + '\n'
            return

        yield json.dumps({'type': 'sql', 'sql': sql}) + '\n'
        yield json.dumps({'type': 'status', 'message': 'Executing query...'}) + '\n'
        await asyncio.sleep(0)

        conn = get_db()
        try:
            cursor = conn.execute(sql)
            cols    = [d[0] for d in cursor.description]
            payload = [dict(zip(cols, row)) for row in cursor.fetchall()]
            yield json.dumps({'type': 'results', 'rows': payload, 'row_count': len(payload)}) + '\n'

            yield json.dumps({'type': 'status', 'message': 'Synthesising answer...'}) + '\n'
            await asyncio.sleep(0)

            answer = llm.synthesize_answer(text, sql, payload)
            llm.add_to_history(text, answer)
            yield json.dumps({'type': 'answer', 'text': answer}) + '\n'
            yield json.dumps({'type': 'done'}) + '\n'

        except sqlite3.Error as e:
            yield json.dumps({'type': 'error', 'message': str(e)}) + '\n'
        finally:
            conn.close()

    return StreamingResponse(event_stream(), media_type='application/x-ndjson')


# ── Conversation ───────────────────────────────────────────────────

@app.get('/conversation/history')
def get_conversation_history():
    """Return history in frontend-compatible format {query, answer, timestamp}."""
    llm = get_llm_service()
    raw = llm.get_history()   # [{role, content, timestamp}]

    # Pair up user/assistant turns
    messages = []
    for i in range(0, len(raw) - 1, 2):
        if raw[i]['role'] == 'user' and raw[i+1]['role'] == 'assistant':
            messages.append({
                'query':     raw[i]['content'],
                'answer':    raw[i+1]['content'],
                'timestamp': raw[i].get('timestamp', ''),
            })
    return {'messages': messages, 'message_count': len(messages)}

@app.post('/conversation/clear')
def clear_conversation_history():
    get_llm_service().clear_history()
    return {'status': 'cleared'}


# ── Query explain ──────────────────────────────────────────────────

@app.post('/query/explain')
def explain_query(req: QueryRequest):
    text = req.prompt.strip()
    if not text:
        raise HTTPException(status_code=400, detail='Prompt is required')

    guardrails = get_guardrails()
    is_safe, message, category = guardrails.check_query(text)
    entities = guardrails.extract_entities(text)

    return {
        'query':    text,
        'safe':     is_safe,
        'category': category.value,
        'message':  message,
        'entities': entities,
        'hint':     guardrails.get_context_hint(text),
    }
