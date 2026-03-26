from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import sqlite3
from pathlib import Path
import json
from graph_builder import get_graph_json
from llm import get_llm_service
from guardrails import get_guardrails, QueryCategory

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
    include_sql: bool = True
    streaming: bool = False

class ConversationMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str

@app.post('/query')
def query_graph(req: QueryRequest) -> Dict[str, Any]:
    """Query with LLM translation and guardrails."""
    text = req.prompt.strip()
    if not text:
        raise HTTPException(status_code=400, detail='Prompt is required')

    # Apply guardrails
    guardrails = get_guardrails()
    is_safe, message, category = guardrails.check_query(text)

    if not is_safe:
        return {
            'query': text,
            'error': message,
            'category': category.value,
            'blocked': True,
            'hint': guardrails.get_context_hint(text)
        }

    # Get LLM service and translate to SQL
    llm = get_llm_service()
    sql, is_valid = llm.translate_nl_to_sql(text)

    if not is_valid:
        return {
            'query': text,
            'error': 'Failed to translate query to SQL. Please rephrase your question.',
            'hint': guardrails.get_context_hint(text)
        }

    # Execute query
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        payload = [dict(zip(columns, row)) for row in rows]

        # Synthesize answer using LLM
        answer = llm.synthesize_answer(text, sql, payload)

        # Add to conversation history
        llm.add_to_history(text, answer)

        result = {
            'query': text,
            'answer': answer,
            'rows': payload,
            'row_count': len(payload),
            'category': category.value
        }

        if req.include_sql:
            result['sql'] = sql

        return result
    except sqlite3.Error as e:
        return {
            'query': text,
            'error': f'Database error: {str(e)}',
            'hint': guardrails.get_context_hint(text)
        }
    finally:
        conn.close()

@app.post('/query/streaming')
def query_graph_streaming(req: QueryRequest) -> StreamingResponse:
    """Query with streaming response (optional feature)."""
    text = req.prompt.strip()
    if not text:
        raise HTTPException(status_code=400, detail='Prompt is required')

    async def event_generator():
        # Check guardrails
        guardrails = get_guardrails()
        is_safe, message, category = guardrails.check_query(text)

        if not is_safe:
            yield json.dumps({
                'type': 'error',
                'message': message,
                'blocked': True
            }).encode() + b'\n'
            return

        yield json.dumps({'type': 'status', 'message': 'Translating query...'}).encode() + b'\n'

        # Translate to SQL
        llm = get_llm_service()
        sql, is_valid = llm.translate_nl_to_sql(text)

        if not is_valid:
            yield json.dumps({'type': 'error', 'message': 'Failed to translate query'}).encode() + b'\n'
            return

        yield json.dumps({'type': 'status', 'message': 'Executing query...', 'sql': sql}).encode() + b'\n'

        # Execute
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            payload = [dict(zip(columns, row)) for row in rows]

            yield json.dumps({
                'type': 'results',
                'rows': payload,
                'row_count': len(payload)
            }).encode() + b'\n'

            yield json.dumps({'type': 'status', 'message': 'Synthesizing answer...'}).encode() + b'\n'

            # Synthesize answer
            answer = llm.synthesize_answer(text, sql, payload)
            yield json.dumps({'type': 'answer', 'text': answer}).encode() + b'\n'

            llm.add_to_history(text, answer)
            yield json.dumps({'type': 'done'}).encode() + b'\n'
        except sqlite3.Error as e:
            yield json.dumps({'type': 'error', 'message': str(e)}).encode() + b'\n'
        finally:
            conn.close()

    return StreamingResponse(event_generator(), media_type='application/x-ndjson')

@app.get('/conversation/history')
def get_conversation_history() -> Dict[str, Any]:
    """Get conversation history (optional feature)."""
    llm = get_llm_service()
    history = llm.get_history()
    return {
        'messages': history,
        'message_count': len(history)
    }

@app.post('/conversation/clear')
def clear_conversation_history() -> Dict[str, str]:
    """Clear conversation history (optional feature)."""
    llm = get_llm_service()
    llm.clear_history()
    return {'status': 'cleared', 'message': 'Conversation history cleared'}

@app.post('/query/explain')
def explain_query(req: QueryRequest) -> Dict[str, Any]:
    """Explain what a natural language query means (optional feature)."""
    text = req.prompt.strip()
    if not text:
        raise HTTPException(status_code=400, detail='Prompt is required')

    guardrails = get_guardrails()
    is_safe, message, category = guardrails.check_query(text)

    explanation = f"Query intent: {text}\n\n"

    if not is_safe:
        explanation += f"Status: ❌ Blocked\n{message}"
    else:
        explanation += f"Status: ✓ Valid O2C query\n"

    # Extract potential entities
    entities = guardrails.extract_entities(text)
    if any(entities.values()):
        explanation += "\nPotential entities mentioned:\n"
        for entity_type, values in entities.items():
            if values:
                explanation += f"  - {entity_type}: {', '.join(values)}\n"

    explanation += "\nWhat you're asking about:\n"
    explanation += guardrails.get_context_hint(text)

    return {
        'query': text,
        'explanation': explanation,
        'category': category.value,
        'safe': is_safe
    }
