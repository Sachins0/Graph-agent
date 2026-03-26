# Deployment & Documentation - Step 8

This guide covers containerization, deployment options, and complete API documentation.

---

## Table of Contents
1. [Docker Setup](#docker-setup)
2. [Deployment Options](#deployment-options)
3. [API Endpoints Reference](#api-endpoints-reference)
4. [Configuration Guide](#configuration-guide)
5. [Usage Examples](#usage-examples)
6. [Troubleshooting](#troubleshooting)

---

## Docker Setup

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum
- 2GB free disk space

### Building and Running with Docker

#### Option 1: Using Docker Compose (Recommended)

```bash
# Navigate to project root
cd sap-o2c-graph-system

# Copy environment template
cp backend/.env.example backend/.env
# Edit with your Gemini API key (optional)
nano backend/.env

# Build and start all services
docker-compose up --build

# Or run in background
docker-compose up -d --build
```

**Services Started**:
- Backend API: http://localhost:8000
- Frontend: http://localhost:5173
- Data initialization (one-time)

#### Option 2: Building Individual Images

**Backend**:
```bash
cd backend
docker build -t sap-o2c-backend:latest .
docker run -p 8000:8000 \
  -e GEMINI_API_KEY=your_key_here \
  -v $(pwd)/o2c.db:/app/backend/o2c.db \
  sap-o2c-backend:latest
```

**Frontend**:
```bash
cd frontend
docker build -t sap-o2c-frontend:latest .
docker run -p 5173:5173 \
  -e VITE_API_URL=http://localhost:8000 \
  sap-o2c-frontend:latest
```

### Docker Compose Commands

```bash
# Start services
docker-compose up

# Start in background
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop services
docker-compose down

# Rebuild images
docker-compose build --no-cache

# Remove everything (including volumes)
docker-compose down -v
```

### Health Checks

```bash
# Check backend health
curl http://localhost:8000/healthz

# Check frontend health
curl -I http://localhost:5173

# Check with Docker
docker-compose ps
```

---

## Deployment Options

### Option 1: Local Development
```bash
# Terminal 1: Backend
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

**Access**: 
- Frontend: http://localhost:5174
- Backend: http://localhost:8000

### Option 2: Docker Compose (Recommended)
```bash
docker-compose up
```

**Access**:
- Frontend: http://localhost:5173
- Backend: http://localhost:8000

### Option 3: Cloud Deployment (AWS ECS)

**Prerequisites**: AWS Account, AWS CLI installed

```bash
# 1. Push images to ECR
aws ecr create-repository --repository-name sap-o2c-backend
aws ecr create-repository --repository-name sap-o2c-frontend

# 2. Tag and push
docker tag sap-o2c-backend:latest [AWS_ACCOUNT].dkr.ecr.us-east-1.amazonaws.com/sap-o2c-backend:latest
docker push [AWS_ACCOUNT].dkr.ecr.us-east-1.amazonaws.com/sap-o2c-backend:latest

docker tag sap-o2c-frontend:latest [AWS_ACCOUNT].dkr.ecr.us-east-1.amazonaws.com/sap-o2c-frontend:latest
docker push [AWS_ACCOUNT].dkr.ecr.us-east-1.amazonaws.com/sap-o2c-frontend:latest

# 3. Create ECS cluster and tasks
# (Use AWS Console or CLI with task definitions)
```

### Option 4: Kubernetes Deployment

**Prerequisites**: kubectl, Kubernetes cluster

```bash
# Create namespace
kubectl create namespace sap-o2c

# Create deployment manifests
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sap-o2c-backend
  namespace: sap-o2c
spec:
  replicas: 2
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend
        image: sap-o2c-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: GEMINI_API_KEY
          valueFrom:
            secretKeyRef:
              name: sap-o2c-secrets
              key: gemini-key
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
EOF
```

### Option 5: Heroku Deployment

```bash
# 1. Install Heroku CLI
# 2. Login to Heroku
heroku login

# 3. Create Heroku app
heroku create sap-o2c-graph-system

# 4. Set environment variables
heroku config:set GEMINI_API_KEY=your_key
heroku config:set DATABASE_URL=sqlite:///o2c.db

# 5. Deploy
git push heroku main

# 6. Open app
heroku open
```

---

## API Endpoints Reference

### Health & Status

#### GET /healthz
Check if API is running.

**Response**:
```json
{
  "status": "healthy"
}
```

**Example**:
```bash
curl http://localhost:8000/healthz
```

---

### Graph Endpoints

#### GET /graph/full
Get complete graph with all nodes and edges.

**Response**:
```json
{
  "nodes": [
    {
      "id": "SO:740506",
      "label": "SO 740506",
      "type": "SalesOrderHeader",
      "properties": {
        "salesOrder": "740506",
        "customer": "310000108",
        "netAmount": "17108.25",
        "creationDate": "2025-03-31T00:00:00.000Z"
      }
    }
  ],
  "edges": [
    {
      "source": "SO:740506",
      "target": "SOI:740506:10",
      "relationship": "contains_item"
    }
  ]
}
```

**Example**:
```bash
curl http://localhost:8000/graph/full | jq '.' | head -50
```

---

#### GET /graph/nodes
Get only nodes from the graph.

**Response**:
```json
{
  "nodes": [...]
}
```

**Example**:
```bash
curl http://localhost:8000/graph/nodes | jq '.nodes | length'
```

---

#### GET /graph/edges
Get only edges from the graph.

**Response**:
```json
{
  "edges": [...]
}
```

**Example**:
```bash
curl http://localhost:8000/graph/edges | jq '.edges | length'
```

---

#### GET /graph/entity/{entity_id}
Get detailed information about a specific node.

**Parameters**:
- `entity_id` (path): Entity ID (e.g., "SO:740506", "DH:800001")

**Response**:
```json
{
  "salesOrder": "740506",
  "customer": "310000108",
  "netAmount": "17108.25",
  "creationDate": "2025-03-31T00:00:00.000Z"
}
```

**Example**:
```bash
curl http://localhost:8000/graph/entity/SO:740506 | jq '.'
```

---

### Query Endpoints

#### POST /query
Execute natural language query against O2C data.

**Request**:
```json
{
  "prompt": "Which products have the highest billing count?",
  "include_sql": false,
  "streaming": false
}
```

**Response** (Success):
```json
{
  "query": "Which products have the highest billing count?",
  "answer": "Product BULK-001 has the highest billing count with 23 occurrences...",
  "rows": [
    {"product_id": "BULK-001", "count": 23}
  ],
  "row_count": 1,
  "category": "o2c_query"
}
```

**Response** (Blocked):
```json
{
  "query": "Tell me a joke",
  "error": "This system is designed to answer questions...",
  "category": "generic",
  "blocked": true,
  "hint": "💡 This system contains SAP Order-to-Cash data..."
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "Which customers placed the most orders?",
    "include_sql": true
  }' | jq '.'
```

---

#### POST /query/streaming
Stream query results in NDJSON format.

**Request**:
```json
{
  "prompt": "Show top 5 products"
}
```

**Response** (NDJSON - newline delimited):
```
{"type": "status", "message": "Translating query..."}
{"type": "status", "message": "Executing query...", "sql": "SELECT * FROM..."}
{"type": "results", "rows": [...], "row_count": 5}
{"type": "answer", "text": "The top 5 products are..."}
{"type": "done"}
```

**Example**:
```bash
curl -X POST http://localhost:8000/query/streaming \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Top products by sales"}' | jq -s '.'
```

---

#### POST /query/explain
Get explanation of query without executing it.

**Request**:
```json
{
  "prompt": "Show me undelivered orders"
}
```

**Response**:
```json
{
  "query": "Show me undelivered orders",
  "safe": true,
  "category": "o2c_query",
  "explanation": "Query intent: Show me undelivered orders\n\nStatus: ✓ Valid O2C query\n\nWhat you're asking about:\n🚚 I can help with delivery information...",
  "entities_detected": ["delivery", "order"],
  "context_hints": [
    "🚚 I can help with delivery information",
    "📋 I can help with sales order details"
  ]
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/query/explain \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Show me all pending paymentsh"}' | jq '.'
```

---

### Conversation Endpoints

#### GET /conversation/history
Get conversation history.

**Response**:
```json
{
  "messages": [
    {
      "query": "Which products have highest billing count?",
      "timestamp": "2025-03-26T10:30:00",
      "category": "o2c_query"
    }
  ],
  "message_count": 1
}
```

**Example**:
```bash
curl http://localhost:8000/conversation/history | jq '.'
```

---

#### POST /conversation/clear
Clear conversation history.

**Response**:
```json
{
  "status": "history_cleared"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/conversation/clear
```

---

## Configuration Guide

### Environment Variables

**Backend** (.env):
```bash
# Database configuration
DATABASE_URL=sqlite:///o2c.db

# LLM configuration (optional)
GEMINI_API_KEY=your_gemini_api_key_here

# API configuration (optional)
API_HOST=0.0.0.0
API_PORT=8000

# Logging (optional)
LOG_LEVEL=INFO
```

**Frontend** (vite.config.js):
```javascript
// API endpoint configuration
const VITE_API_URL = process.env.VITE_API_URL || 'http://localhost:8000'
```

### Database Configuration

**SQLite** (Default, no config needed):
```bash
# Database file location
backend/o2c.db

# Size: ~1MB
# Capacity: ~100K records
```

### API Keys

**Google Gemini API**:
1. Visit https://ai.google.dev
2. Click "Get API Key"
3. Copy key to `backend/.env`:
   ```bash
   GEMINI_API_KEY=your_key_here
   ```

---

## Usage Examples

### Example 1: Basic Query
```bash
curl -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "How many sales orders were created in March 2025?"
  }' | jq '.answer'
```

### Example 2: Complex O2C Flow
```bash
curl -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "Trace the complete order-to-cash flow for customer 310000108",
    "include_sql": true
  }' | jq '.'
```

### Example 3: Graph Exploration
```bash
# Get all customers
curl http://localhost:8000/graph/full | jq '.nodes[] | select(.type=="Customer")'

# Get all relationships
curl http://localhost:8000/graph/full | jq '.edges | group_by(.relationship)'
```

### Example 4: Query with SQL
```bash
curl -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "Which products generated the most revenue?",
    "include_sql": true
  }' | jq '{query, answer, sql}'
```

### Example 5: Streaming Results
```bash
# Stream large result sets
curl -X POST http://localhost:8000/query/streaming \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "List all pending deliveries"}' | while read line; do
    echo "Received: $(echo $line | jq '.type')"
done
```

### Example 6: Batch Queries
```bash
# Test multiple queries
queries=(
  "How many sales orders exist?"
  "What is the average billing amount?"
  "List top 5 products by quantity"
)

for query in "${queries[@]}"; do
  echo "Query: $query"
  curl -s -X POST http://localhost:8000/query \
    -H 'Content-Type: application/json' \
    -d "{\"prompt\": \"$query\"}" | jq '.answer'
  echo "---"
done
```

### Example 7: Frontend Integration
```javascript
// JavaScript/React HTTP client
const query = async (prompt) => {
  const response = await fetch('http://localhost:8000/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt })
  });
  return response.json();
};

// Usage
query('Which customers purchased the most?')
  .then(result => console.log(result.answer));
```

---

## Troubleshooting

### Issue: Docker build fails
**Solution**:
```bash
# Clean up
docker-compose down -v
docker system prune -f

# Rebuild
docker-compose build --no-cache
```

### Issue: Database not found
**Solution**:
```bash
# Reset database
cd backend
python data_ingest.py
```

### Issue: Port already in use
**Solution**:
```bash
# Find and kill process on port 8000
lsof -i :8000 | grep LISTEN | awk '{print $2}' | xargs kill -9

# Or use different port
docker-compose down
docker-compose up -p 8001:8000
```

### Issue: CORS errors in frontend
**Solution**: Edit `backend/main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Issue: Gemini API not working
**Solution**:
```bash
# Test API key
curl -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Test query"}' | jq '.error'

# Falls back to keyword-based translation if key is missing
```

### Issue: Slow performance
**Solution**:
```bash
# Reduce graph complexity
# In App.jsx, add filtering:
const filteredNodes = graphData.nodes.slice(0, 500)

# Or use database indexing in backend:
# sqlite3 o2c.db "CREATE INDEX idx_so_customer ON sales_order_headers(customer);"
```

---

## Performance Optimization

### Backend Optimizations

1. **Database Indexing**:
```bash
sqlite3 backend/o2c.db << EOF
CREATE INDEX IF NOT EXISTS idx_so_customer ON sales_order_headers(customer);
CREATE INDEX IF NOT EXISTS idx_di_soi ON delivery_items(sales_order_item);
CREATE INDEX IF NOT EXISTS idx_bi_soi ON billing_items(sales_order_item);
CREATE INDEX IF NOT EXISTS idx_je_inv ON journal_entry_items_accounts_receivable(invoice_number);
EOF
```

2. **Query Caching** (add to llm.py):
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def cached_query(prompt):
    return translate_nl_to_sql(prompt)
```

3. **Connection Pooling**:
```python
from sqlite3 import connect
from contextlib import contextmanager

class ConnectionPool:
    def __init__(self, size=5):
        self.pool = [connect(DATABASE_URL) for _ in range(size)]
```

### Frontend Optimizations

1. **Lazy Load Graph**:
```javascript
const [graphData, setGraphData] = useState(null);

useEffect(() => {
  // Load graph chunks
  fetchGraphPaginated(0, 500);
}, []);
```

2. **Memoize Components**:
```javascript
const MemoizedNode = React.memo(NodeComponent);
```

3. **Virtual Scrolling** (for large lists):
```bash
npm install react-window
```

---

## Security Considerations

1. **API Authentication** (optional):
```python
from fastapi.security import HTTPBearer, HTTPAuthCredentials

security = HTTPBearer()

@app.post("/query")
async def secure_query(credentials: HTTPAuthCredentials = Depends(security)):
    token = credentials.credentials
    # Verify token...
```

2. **Rate Limiting**:
```bash
pip install slowapi
```

3. **HTTPS in Production**:
```bash
# Use reverse proxy (nginx)
# Configure SSL certificates
```

4. **Input Validation** (already implemented via guardrails):
```python
# Blocks SQL injection, harmful requests
# Validates domain relevance
```

---

## Monitoring & Logging

### Application Logs
```bash
# Backend logs
docker-compose logs -f backend

# Frontend logs
docker-compose logs -f frontend
```

### Health Monitoring
```bash
# Monitor all services
watch 'docker-compose ps'

# Check service health
docker-compose ps --services
```

### Metrics Collection (optional)
```python
from prometheus_client import Counter, Histogram

query_counter = Counter('queries_total', 'Total queries')
query_duration = Histogram('query_duration_seconds', 'Query duration')
```

---

## Maintenance

### Backup Database
```bash
cp backend/o2c.db backend/o2c.db.backup
```

### Update Dependencies
```bash
# Backend
pip install --upgrade -r requirements.txt

# Frontend
npm update
npm audit fix
```

### Clean Docker
```bash
# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Remove unused networks
docker network prune
```

---

## Support & Documentation

- **API Questions**: Check `/query/explain` endpoint
- **Integration Issues**: See INTEGRATION_TESTS.md
- **Deployment**: See this file's deployment sections
- **Database**: Check backend/data_ingest.py for data schema

---

**Next Steps**: Your system is now ready for production deployment! 🚀
