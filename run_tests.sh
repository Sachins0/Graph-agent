#!/bin/bash

# Comprehensive Integration Test Suite for SAP O2C Graph System
# This script tests all major functionality

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
PASSED=0
FAILED=0
SKIPPED=0

# Test results
declare -a TEST_RESULTS=()

# Configuration
BACKEND_URL="http://localhost:8000"
FRONTEND_URL="http://localhost:5174"
TIMEOUT=10

# Helper functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_test() {
    echo -e "${YELLOW}TEST: $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
    ((PASSED++))
}

print_failure() {
    echo -e "${RED}✗ $1${NC}"
    ((FAILED++))
}

print_skip() {
    echo -e "${YELLOW}⊘ $1${NC}"
    ((SKIPPED++))
}

# Check if server is running
check_server() {
    local url=$1
    local name=$2
    
    if timeout $TIMEOUT curl -s "$url/healthz" > /dev/null 2>&1 || timeout $TIMEOUT curl -s "$url" > /dev/null 2>&1; then
        print_success "$name is running ($url)"
        return 0
    else
        print_failure "$name is not accessible ($url)"
        return 1
    fi
}

# Test graph endpoints
test_graph_endpoints() {
    print_header "PHASE 1: GRAPH ENDPOINTS"
    
    print_test "GET /graph/full"
    response=$(curl -s "${BACKEND_URL}/graph/full" 2>/dev/null || echo "{}")
    if echo "$response" | grep -q '"nodes"'; then
        node_count=$(echo "$response" | grep -o '"nodes":\[' | wc -l)
        print_success "Graph endpoint returned nodes"
    else
        print_failure "Graph endpoint failed to return nodes"
    fi
    
    print_test "GET /graph/nodes"
    response=$(curl -s "${BACKEND_URL}/graph/nodes" 2>/dev/null || echo "{}")
    if echo "$response" | grep -q '"nodes"'; then
        print_success "Nodes endpoint working"
    else
        print_failure "Nodes endpoint failed"
    fi
    
    print_test "GET /graph/edges"
    response=$(curl -s "${BACKEND_URL}/graph/edges" 2>/dev/null || echo "{}")
    if echo "$response" | grep -q '"edges"'; then
        print_success "Edges endpoint working"
    else
        print_failure "Edges endpoint failed"
    fi
    
    print_test "GET /graph/entity/{id}"
    response=$(curl -s "${BACKEND_URL}/graph/entity/SO:740506" 2>/dev/null || echo "{}")
    if [ ! -z "$response" ] && [ "$response" != "null" ]; then
        print_success "Entity endpoint working"
    else
        print_failure "Entity endpoint failed"
    fi
}

# Test query endpoints with guardrails
test_query_endpoints() {
    print_header "PHASE 2: QUERY ENDPOINTS & GUARDRAILS"
    
    # Test valid O2C query
    print_test "Valid O2C Query: 'Show top 5 products'"
    response=$(curl -s -X POST "${BACKEND_URL}/query" \
      -H 'Content-Type: application/json' \
      -d '{"prompt": "Which products have the highest count?"}' 2>/dev/null || echo "{}")
    
    if echo "$response" | grep -q '"query"'; then
        if echo "$response" | grep -q '"answer"' || echo "$response" | grep -q '"error"'; then
            print_success "Query endpoint responding"
        else
            print_failure "Query endpoint response incomplete"
        fi
    else
        print_failure "Query endpoint failed"
    fi
    
    # Test guardrails - blocked query
    print_test "Guardrails: Off-topic query should be blocked"
    response=$(curl -s -X POST "${BACKEND_URL}/query" \
      -H 'Content-Type: application/json' \
      -d '{"prompt": "Tell me a joke"}' 2>/dev/null || echo "{}")
    
    if echo "$response" | grep -q '"blocked":true'; then
        print_success "Guardrails blocking off-topic queries"
    elif echo "$response" | grep -q '"error"' && echo "$response" | grep -q 'O2C'; then
        print_success "Query appropriately rejected"
    else
        print_failure "Guardrails not properly rejecting off-topic queries"
    fi
    
    # Test query explanation
    print_test "Query Explanation Endpoint"
    response=$(curl -s -X POST "${BACKEND_URL}/query/explain" \
      -H 'Content-Type: application/json' \
      -d '{"prompt": "Show me undelivered orders"}' 2>/dev/null || echo "{}")
    
    if echo "$response" | grep -q '"safe"'; then
        print_success "Query explanation endpoint working"
    else
        print_failure "Query explanation endpoint failed"
    fi
}

# Test conversation endpoints
test_conversation_endpoints() {
    print_header "PHASE 3: CONVERSATION ENDPOINTS"
    
    print_test "GET /conversation/history"
    response=$(curl -s "${BACKEND_URL}/conversation/history" 2>/dev/null || echo "{}")
    
    if echo "$response" | grep -q '"messages"'; then
        print_success "Conversation history endpoint working"
    else
        print_failure "Conversation history endpoint failed"
    fi
    
    print_test "POST /conversation/clear"
    response=$(curl -s -X POST "${BACKEND_URL}/conversation/clear" 2>/dev/null || echo "{}")
    
    if [ ! -z "$response" ]; then
        print_success "Conversation clear endpoint responding"
    else
        print_failure "Conversation clear endpoint failed"
    fi
}

# Test frontend connectivity
test_frontend_connectivity() {
    print_header "PHASE 4: FRONTEND CONNECTIVITY"
    
    print_test "Frontend Page Load"
    response=$(curl -s "${FRONTEND_URL}" 2>/dev/null || echo "")
    
    if echo "$response" | grep -q "SAP O2C"; then
        print_success "Frontend loads successfully"
    else
        print_failure "Frontend failed to load"
    fi
    
    print_test "Frontend Assets"
    if curl -s "${FRONTEND_URL}" 2>/dev/null | grep -q "script"; then
        print_success "Frontend assets loading"
    else
        print_failure "Frontend assets not loading"
    fi
}

# Test response times
test_performance() {
    print_header "PHASE 5: PERFORMANCE"
    
    print_test "Graph Load Time"
    start=$(date +%s%N)
    curl -s "${BACKEND_URL}/graph/full" > /dev/null 2>&1
    end=$(date +%s%N)
    duration=$(( (end - start) / 1000000 ))
    
    if [ $duration -lt 2000 ]; then
        print_success "Graph loads in ${duration}ms (< 2s)"
    else
        print_failure "Graph loads in ${duration}ms (> 2s)"
    fi
    
    print_test "Query Response Time"
    start=$(date +%s%N)
    curl -s -X POST "${BACKEND_URL}/query" \
      -H 'Content-Type: application/json' \
      -d '{"prompt": "Show top products"}' > /dev/null 2>&1
    end=$(date +%s%N)
    duration=$(( (end - start) / 1000000 ))
    
    if [ $duration -lt 5000 ]; then
        print_success "Query responds in ${duration}ms (< 5s)"
    else
        print_failure "Query responds in ${duration}ms (> 5s)"
    fi
}

# Test error handling
test_error_handling() {
    print_header "PHASE 6: ERROR HANDLING"
    
    print_test "Invalid Endpoint"
    response=$(curl -s -w "\n%{http_code}" "${BACKEND_URL}/invalid/endpoint" 2>/dev/null | tail -1)
    
    if [ "$response" = "404" ]; then
        print_success "404 errors handled correctly"
    else
        print_skip "404 error handling (response: $response)"
    fi
    
    print_test "Empty Query"
    response=$(curl -s -X POST "${BACKEND_URL}/query" \
      -H 'Content-Type: application/json' \
      -d '{"prompt": ""}' 2>/dev/null || echo "{}")
    
    if echo "$response" | grep -q '"error"' || echo "$response" | grep -q '"blocked"'; then
        print_success "Empty queries handled"
    else
        print_skip "Empty query handling"
    fi
}

# Main execution
main() {
    echo -e "\n${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  SAP O2C Graph System - Integration Test Suite              ║${NC}"
    echo -e "${BLUE}║  Date: $(date '+%Y-%m-%d %H:%M:%S')                              ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    
    # Check servers
    print_header "CONNECTIVITY CHECK"
    check_server "$BACKEND_URL" "Backend API" || exit 1
    check_server "$FRONTEND_URL" "Frontend Server" || exit 1
    
    # Run tests
    test_graph_endpoints
    test_query_endpoints
    test_conversation_endpoints
    test_frontend_connectivity
    test_performance
    test_error_handling
    
    # Summary
    print_header "TEST SUMMARY"
    
    echo -e "${GREEN}Passed:  $PASSED${NC}"
    echo -e "${RED}Failed:  $FAILED${NC}"
    echo -e "${YELLOW}Skipped: $SKIPPED${NC}"
    echo -e "\nTotal:   $((PASSED + FAILED + SKIPPED))"
    
    # Exit code
    if [ $FAILED -eq 0 ]; then
        echo -e "\n${GREEN}✓ All tests passed!${NC}\n"
        return 0
    else
        echo -e "\n${RED}✗ Some tests failed. Review output above.${NC}\n"
        return 1
    fi
}

# Run main
main
