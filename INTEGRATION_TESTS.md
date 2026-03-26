# Integration & Testing Guide - Step 7

This guide covers comprehensive testing of the SAP O2C Graph System with sample data and example queries.

## Prerequisites

- Backend running on `http://localhost:8000`
- Frontend running on `http://localhost:5174`
- Gemini API key configured in `backend/.env` (optional, system has fallbacks)

---

## Phase 1: Graph Visualization Testing

### 1.1 Load Graph Data
**Endpoint**: `GET /graph/full`

```bash
curl -s http://localhost:8000/graph/full | jq '.nodes | length'
# Expected: ~2000 nodes
```

**Frontend Test**:
1. Open http://localhost:5174
2. Click "Refresh Graph" button
3. **Verify**:
   - ✅ Graph loads with nodes and links
   - ✅ Nodes are colored by type (blue=SalesOrder, green=Delivery, orange=Billing, etc.)
   - ✅ Node count displayed matches actual count
   - ✅ Graph animates smoothly with force-directed layout

### 1.2 Node Interaction Testing
**Frontend Test**:
1. **Click a node** (e.g., a sales order)
2. **Verify**:
   - ✅ Node metadata dialog opens
   - ✅ Shows all node properties (ID, type, related fields)
   - ✅ Dialog closes when clicking "Close" button

### 1.3 Filtering Test
**Frontend Test**:
1. Click "Node Types" accordion
2. Uncheck "SalesOrderHeader" chip
3. **Verify**:
   - ✅ Sales order nodes disappear
   - ✅ Connected edges are removed
   - ✅ Node count updates
4. Re-check the chip
5. **Verify**:
   - ✅ Nodes reappear

### 1.4 Search Test
**Frontend Test**:
1. Type "740506" in search box (sample sales order ID)
2. **Verify**:
   - ✅ Only nodes matching ID remain visible
   - ✅ Connected nodes and edges are shown
3. Clear search box
4. **Verify**:
   - ✅ All nodes reappear

### 1.5 Zoom Controls Test
**Frontend Test**:
1. Click "Zoom In" button multiple times
2. **Verify**: ✅ Graph enlarges
3. Click "Zoom Out"
4. **Verify**: ✅ Graph shrinks
5. Click "Center" button
6. **Verify**: ✅ Graph recenters and resets zoom

### 1.6 Highlight Mode Test
**Frontend Test**:
1. Toggle "Highlight Mode" button
2. Hover over a node
3. **Verify**:
   - ✅ Connected nodes are highlighted
   - ✅ Other nodes fade
   - ✅ Connected edges are prominent
4. Toggle off
5. **Verify**: ✅ Highlight effect disappears

---

## Phase 2: Query Interface Testing

### 2.1 Valid O2C Queries (with Gemini API Key)

#### Query 1: Product Billing Count
**Input**: "Which products are associated with the highest number of billing documents?"

**Expected Behavior**:
- ✅ Query accepted (guardrails pass)
- ✅ SQL translated correctly
- ✅ Results show top products with billing counts
- ✅ Answer synthesized in natural language

**Example Result**:
```json
{
  "query": "Which products are associated with the highest number of billing documents?",
  "answer": "Product BULK-001 has the highest number of billing documents with 23 occurrences. Product STANDARD-045 follows with 18 documents.",
  "rows": [
    {"product_id": "BULK-001", "count": 23},
    {"product_id": "STANDARD-045", "count": 18}
  ],
  "row_count": 2
}
```

#### Query 2: Customer Orders
**Input**: "Show me all sales orders for customer 310000108"

**Expected Behavior**:
- ✅ Query passes guardrails check
- ✅ Returns sales orders for specified customer
- ✅ Natural language answer provided

#### Query 3: Delivery Status
**Input**: "How many deliveries are still in transit?"

**Expected Behavior**:
- ✅ Valid O2C query identified
- ✅ SQL generated and executed
- ✅ Results returned with count

#### Query 4: Order-to-Cash Flow
**Input**: "Trace the complete order-to-cash flow for sales order 740506"

**Expected Behavior**:
- ✅ Complex query accepted
- ✅ Shows full path: SalesOrder → DeliveryItem → BillingItem → Payment
- ✅ Comprehensive answer with all steps

### 2.2 Guardrails Validation Testing

#### Test 1: Off-Topic Query
**Input**: "Tell me a joke"

**Expected**:
```json
{
  "query": "Tell me a joke",
  "error": "This system is designed to answer questions related to SAP Order-to-Cash data only...",
  "category": "generic",
  "blocked": true,
  "hint": "💡 This system contains SAP Order-to-Cash data..."
}
```

**Verify**:
- ✅ Query blocked with 403 status
- ✅ Helpful error message shown
- ✅ Domain-specific hint provided

#### Test 2: Harmful Query
**Input**: "DROP TABLE sales_order_headers; --"

**Expected**:
- ✅ Query blocked (SQL injection detected)
- ✅ Error message shown
- ✅ No database modification

#### Test 3: Creative Writing Request
**Input**: "Write me a poem about SAP billing"

**Expected**:
- ✅ Blocked as off-topic
- ✅ User redirected to valid O2C queries

#### Test 4: General Knowledge
**Input**: "What is the capital of France?"

**Expected**:
- ✅ Blocked as generic/off-topic
- ✅ Suggestion to ask about O2C data

### 2.3 Query Explanation Endpoint Test

**Endpoint**: `POST /query/explain`

```bash
curl -X POST http://localhost:8000/query/explain \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Show me undelivered orders"}'
```

**Expected Response**:
```json
{
  "query": "Show me undelivered orders",
  "safe": true,
  "category": "o2c_query",
  "explanation": "Query intent: Show me undelivered orders\n\nStatus: ✓ Valid O2C query\n\nWhat you're asking about:\n🚚 I can help with delivery...",
  "entities_detected": ["delivery", "order"],
  "context_hints": ["🚚 I can help with delivery information", "📋 I can help with sales order details"]
}
```

**Verify**:
- ✅ Query correctly classified
- ✅ Explanation provided
- ✅ Context hints shown

---

## Phase 3: Error Handling & Loading States

### 3.1 Loading States Test
**Frontend Test**:
1. Click "Ask" button with a query
2. **Verify During Processing**:
   - ✅ Button shows "Processing..." text
   - ✅ Button is disabled
   - ✅ No multiple submissions possible
3. **Verify After Response**:
   - ✅ Button returns to "Ask" state
   - ✅ Results displayed in panel

### 3.2 Error Handling Test
**Endpoint Down Scenario**:
1. Stop backend server
2. Try querying in frontend
3. **Verify**:
   - ✅ Error message displayed
   - ✅ User-friendly error text shown
   - ✅ No console errors

**Invalid Query Scenario**:
1. Submit empty query
2. **Verify**: ✅ Ask button remains disabled

### 3.3 Network Error Handling
**Frontend Test**:
1. Open DevTools (F12)
2. Go to Network tab
3. Make a query
4. **Verify**:
   - ✅ Request shows HTTP status code
   - ✅ Response structure is valid
   - ✅ No CORS errors

---

## Phase 4: Conversation History Testing

### 4.1 History Endpoint Test
```bash
# Submit a query first
curl -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Which customers placed the most orders?"}'

# Check history
curl http://localhost:8000/conversation/history | jq '.messages'
```

**Expected**:
- ✅ Message added to history
- ✅ Contains query, timestamp, category
- ✅ History persists in memory

### 4.2 History UI Test
**Frontend Test**:
1. Submit multiple queries
2. Expand "Conversation History" accordion
3. **Verify**:
   - ✅ Previous queries listed
   - ✅ Up to 5 most recent shown
   - ✅ Timestamps displayed correctly

### 4.3 Clear History Test
```bash
curl -X POST http://localhost:8000/conversation/clear
curl http://localhost:8000/conversation/history
# Expected: empty messages array
```

---

## Phase 5: API Endpoint Coverage Testing

### 5.1 Graph Endpoints

| Endpoint | Method | Expected Response |
|----------|--------|-------------------|
| `/graph/full` | GET | `{nodes: [...], edges: [...]}` |
| `/graph/nodes` | GET | `{nodes: [...]}` |
| `/graph/edges` | GET | `{edges: [...]}` |
| `/graph/entity/SO:740506` | GET | `{salesOrder, customer, netAmount, ...}` |
| `/healthz` | GET | `{status: "healthy"}` |

**Test All**:
```bash
for endpoint in "/graph/full" "/graph/nodes" "/graph/edges" "/graph/entity/SO:740506" "/healthz"; do
  echo "Testing: $endpoint"
  curl -s http://localhost:8000$endpoint | jq '.' | head -5
  echo "---"
done
```

### 5.2 Query Endpoints

| Endpoint | Method | Expected Response |
|----------|--------|-------------------|
| `/query` | POST | `{query, answer, category, (rows)}` |
| `/query/explain` | POST | `{safe, category, explanation}` |
| `/query/streaming` | POST | NDJSON stream |
| `/conversation/history` | GET | `{messages: [...], message_count}` |
| `/conversation/clear` | POST | `{status: "cleared"}` |

---

## Phase 6: Performance Testing

### 6.1 Graph Load Time
```bash
time curl -s http://localhost:8000/graph/full > /dev/null
# Expected: < 1 second
```

### 6.2 Query Response Time
```bash
time curl -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Show top 5 products"}' > /dev/null
# Expected: < 5 seconds (with LLM), < 1 second (fallback)
```

### 6.3 Frontend Rendering
**Frontend Test**:
1. Open DevTools → Performance tab
2. Start recording
3. Click "Refresh Graph"
4. Stop recording
5. **Verify**:
   - ✅ First paint < 500ms
   - ✅ Interactive < 2s
   - ✅ No jank in animations

---

## Phase 7: Cross-Browser Testing

Test on:
- ✅ Chrome/Chromium
- ✅ Firefox
- ✅ Safari
- ✅ Edge
- ✅ Mobile browsers

**Verify**:
- ✅ Graph renders correctly
- ✅ All controls work
- ✅ No visual glitches
- ✅ Responsive layout functions

---

## Test Summary Checklist

- [ ] Graph visualization loads and renders correctly
- [ ] Node clicking shows metadata
- [ ] Filters work for nodes and relationships
- [ ] Search filters nodes correctly
- [ ] Zoom controls function properly
- [ ] Highlight mode highlights connections
- [ ] Valid O2C queries are accepted
- [ ] Off-topic queries are blocked
- [ ] Guardrails provide helpful hints
- [ ] Query explanation endpoint works
- [ ] Loading states display correctly
- [ ] Error handling shows user-friendly messages
- [ ] Conversation history tracks queries
- [ ] All API endpoints respond correctly
- [ ] Response times are acceptable
- [ ] Frontend works on all major browsers

---

## Example Test Commands

```bash
# Start fresh
pkill -f "uvicorn\|npm run dev" 2>/dev/null
sleep 2

# Terminal 1: Backend
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000 &
sleep 3

# Terminal 2: Frontend
cd frontend
npm run dev &
sleep 3

# Terminal 3: Run tests
# Test graph
curl -s http://localhost:8000/graph/full | jq '.nodes | length'

# Test valid query
curl -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Show top products by sales"}' | jq '.answer'

# Test guardrails
curl -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Tell me a joke"}' | jq '.blocked'

# Clean up
pkill -f "uvicorn\|npm run dev"
```

---

## Troubleshooting

### Frontend Not Connecting to Backend
- **Issue**: CORS error or connection refused
- **Solution**: 
  1. Verify backend is running: `curl http://localhost:8000/healthz`
  2. Check API_URL in `frontend/src/App.jsx` matches backend URL
  3. Restart both servers

### Graph Not Loading
- **Issue**: Empty graph or nodes not showing
- **Solution**:
  1. Check database exists: `ls -la backend/o2c.db`
  2. Verify data was ingested: `sqlite3 backend/o2c.db "SELECT COUNT(*) FROM sales_order_headers"`
  3. Check backend logs for errors

### Query Returning No Results
- **Issue**: Query executes but no data returned
- **Solution**:
  1. Try simpler query first
  2. Verify sample data with direct SQL: `sqlite3 backend/o2c.db "SELECT * FROM sales_order_headers LIMIT 5"`
  3. Check Gemini API key if available

### High Latency
- **Issue**: Slow response times
- **Solution**:
  1. Reduce graph filtering to show fewer nodes
  2. Check system resources: `top` or `htop`
  3. Reduce graph animation updates in App.jsx

---

## Next Steps

After completing all tests:
1. ✅ Mark passing tests
2. Document any failures with error messages
3. Proceed to Step 8: Deployment & Documentation
4. Create Docker containers for production
5. Deploy to cloud platform (AWS, GCP, Azure, etc.)
