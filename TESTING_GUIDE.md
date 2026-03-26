# Step 3: Graph Engine & Visualization Testing Guide

This document provides comprehensive testing procedures for the graph engine implementation.

## Quick Start (Backend + Frontend)

### Terminal 1: Start Backend Server
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

Expected output:
```
Uvicorn running on http://127.0.0.1:8000
```

### Terminal 2: Start Frontend Dev Server
```bash
cd frontend
npm run dev
```

Expected output:
```
  VITE v4.5.0  ready in XXX ms

  ➜  Local:   http://localhost:5173/
```

Open browser: `http://localhost:5173`

---

## Backend API Testing

### 1. Health Check
```bash
curl http://localhost:8000/healthz
```
Expected response:
```json
{"status":"healthy"}
```

### 2. Graph Nodes Endpoint
```bash
curl http://localhost:8000/graph/nodes | jq .count
```
Expected response (sample):
```json
{"nodes": [...], "count": 1218}
```

### 3. Graph Edges Endpoint
```bash
curl http://localhost:8000/graph/edges | jq .count
```
Expected response (sample):
```json
{"edges": [...], "count": 939}
```

### 4. Full Graph Data
```bash
curl http://localhost:8000/graph/full | jq 'keys'
```
Expected response:
```json
["nodes", "edges"]
```

### 5. Entity Details Endpoint
```bash
# Get a specific sales order
curl http://localhost:8000/graph/entity/SO:740506 | jq .
```
Expected response:
```json
{
  "node": {
    "id": "SO:740506",
    "label": "SO 740506",
    "type": "SalesOrderHeader",
    "properties": {...}
  },
  "connections": [
    {
      "source": "SO:740506",
      "target": "SOI:740506:10",
      "relationship": "contains_item"
    }
  ]
}
```

### 6. Sample Query (Data-backed Response)
```bash
curl -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Which products are associated with the highest number of billing documents?"}'
```

Expected response:
```json
{
  "query": "Which products...",
  "sql": "SELECT material, COUNT(*) AS billing_count...",
  "rows": [
    {"material": "S8907367039280", "billing_count": 22},
    ...
  ],
  "answer": "Data-backed response returned..."
}
```

### 7. Guardrail Test (Off-topic Query)
```bash
curl -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Who is Leonardo da Vinci?"}'
```

Expected response:
```json
{
  "query": "Who is Leonardo da Vinci?",
  "answer": "This system only answers dataset-related O2C questions."
}
```

---

## Frontend Testing (Browser)

### Visual Verification
1. **Graph Visualization**
   - Should show an interactive force-directed graph
   - Nodes colored by type (SalesOrderHeader, DeliveryHeader, etc.)
   - Arrows showing relationship direction
   - Pan/zoom/drag interaction supported

2. **Refresh Graph Button**
   - Click "Refresh Graph"
   - Verify nodes reappear
   - Should show count: "Nodes: 1218 | Links: 939"

3. **Node Selection**
   - Click on a node in the graph
   - Right panel should show node details
   - Selected node indicator below query box

4. **Query Interface**
   - Type in the textarea
   - Press Enter or click "Ask" button
   - Answer appears in the result pane

### Functional Test Queries
```
1. "Which products are associated with the highest number of billing documents?"
   Expected: SQL query returning top products by billing count

2. "trace the full flow"
   Expected: Sample sales orders shown

3. "What is AI?"
   Expected: Guardrail response (dataset-only)
```

---

## Graph Structure Verification

### Python Script to Inspect Graph
```python
from graph_builder import get_graph_json
import json

data = get_graph_json()

print(f"Total Nodes: {len(data['nodes'])}")
print(f"Total Edges: {len(data['edges'])}")

# Group by type
by_type = {}
for node in data['nodes']:
    t = node['type']
    by_type[t] = by_type.get(t, 0) + 1

print("\nNodes by Type:")
for t, count in sorted(by_type.items()):
    print(f"  {t}: {count}")

# Group relationships by type
by_relationship = {}
for edge in data['edges']:
    r = edge['relationship']
    by_relationship[r] = by_relationship.get(r, 0) + 1

print("\nEdges by Relationship:")
for r, count in sorted(by_relationship.items()):
    print(f"  {r}: {count}")
```

Run:
```bash
cd backend
source venv/bin/activate
python3 << 'EOF'
# paste script above
EOF
```

Expected output:
```
Total Nodes: 1218
Total Edges: 939

Nodes by Type:
  BillingHeader: ~45
  BillingItem: ~100
  Customer: ~30
  DeliveryHeader: ~30
  DeliveryItem: ~100
  JournalEntry: ~30
  Payment: ~30
  Product: ~200
  SalesOrderHeader: ~30
  SalesOrderItem: ~100

Edges by Relationship:
  billed_from: ~90
  contains_item: ~200
  fulfilled_by: ~80
  includes_product: ~100
  places_order: ~30
  recorded_in_je: ~30
```

---

## Troubleshooting

### Issue: Frontend not connecting to backend
- **Cause**: CORS or port mismatch
- **Fix**: Check backend URL in App.jsx is `http://localhost:8000`
- **Check**: Backend logs should show CORS headers

### Issue: Graph appears empty
- **Cause**: Data fetch failed
- **Fix**: Check browser console for errors
- **Debug**: Run `curl http://localhost:8000/graph/full` manually

### Issue: Slow graph rendering
- **Cause**: Too many nodes/edges
- **Fix**: Frontend is pre-loaded with full graph; consider pagination in future

### Issue: Query returns empty
- **Cause**: Query rule not matching
- **Fix**: Use one of the known templates or add new rule in main.py

---

## Next Steps

1. **Gemini Integration**: Implement NL→SQL translation in `backend/llm.py`
2. **Query Rules**: Add more template matching rules for common queries
3. **Graph Analysis**: Add endpoints for graph traversal, shortest paths, clustering
4. **UI Enhancements**: Add filtering, search, details panel, timeline view
