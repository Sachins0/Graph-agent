from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict, List

app = FastAPI(title='SAP O2C Graph System (Backend)')

@app.get('/')
def root():
    return {'status': 'ok', 'message': 'SAP O2C Graph System backend'}

# placeholder for future endpoints
@app.get('/healthz')
def healthz():
    return {'status': 'healthy'}

class QueryRequest(BaseModel):
    prompt: str

@app.post('/query')
def query_graph(req: QueryRequest) -> Dict[str, Any]:
    return {
        'query': req.prompt,
        'answer': 'System not yet implemented (NL query->graph/SQL pipeline pending).'
    }
