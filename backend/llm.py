import os
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dotenv import load_dotenv
from groq import Groq
from datetime import datetime

load_dotenv()

# ── Groq client setup ─────────────────────────────────────────────
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL  = "llama-3.3-70b-versatile"

DB_PATH = Path(__file__).resolve().parent / 'o2c.db'

# ── Few-shot examples for NL→SQL ─────────────────────────────────
SQL_GENERATION_EXAMPLES = """
# Example 1: Products with highest billing count
User: "Which products are associated with the highest number of billing documents?"
SQL: SELECT material, COUNT(*) as billing_count FROM billing_document_items GROUP BY material ORDER BY billing_count DESC LIMIT 10

# Example 2: Customer orders
User: "Show me sales orders for customer 310000108"
SQL: SELECT salesOrder, creationDate, totalNetAmount FROM sales_order_headers WHERE soldToParty = '310000108' LIMIT 20

# Example 3: Order to delivery flow
User: "Trace the full flow of sales order 740506"
SQL:
  SELECT 'SalesOrder' as stage, salesOrder as id, creationDate as date FROM sales_order_headers WHERE salesOrder = '740506'
  UNION ALL
  SELECT 'Delivery', deliveryDocument, creationDate FROM outbound_delivery_headers WHERE deliveryDocument IN (
    SELECT DISTINCT dh.deliveryDocument FROM outbound_delivery_items oi
    JOIN outbound_delivery_headers dh ON oi.deliveryDocument = dh.deliveryDocument
    WHERE CAST(oi.referenceSdDocument AS INTEGER) = 740506
  )
  UNION ALL
  SELECT 'Billing', billingDocument, creationDate FROM billing_document_headers WHERE billingDocument IN (
    SELECT DISTINCT bi.billingDocument FROM billing_document_items bi
    WHERE bi.referenceSdDocument IN (SELECT deliveryDocument FROM outbound_delivery_headers LIMIT 1)
  )

# Example 4: Incomplete flows
User: "Find orders that were delivered but not billed"
SQL:
  SELECT DISTINCT so.salesOrder FROM sales_order_headers so
  JOIN outbound_delivery_items oi ON CAST(so.salesOrder AS INTEGER) = CAST(oi.referenceSdDocument AS INTEGER)
  WHERE oi.deliveryDocument NOT IN (
    SELECT DISTINCT referenceSdDocument FROM billing_document_items WHERE referenceSdDocument IS NOT NULL
  )
  LIMIT 20

# Example 5: Payment status
User: "Which customers have pending payments?"
SQL:
  SELECT DISTINCT p.customer FROM payments_accounts_receivable p
  WHERE p.accountingDocument NOT IN (
    SELECT DISTINCT clearingAccountingDocument FROM payments_accounts_receivable WHERE clearingAccountingDocument IS NOT NULL
  )
  LIMIT 20
"""

SYSTEM_PROMPT = """You are an SAP Order-to-Cash (O2C) data analyst assistant.
You ONLY answer questions about the SAP O2C dataset which includes:
- Sales Orders, Outbound Deliveries, Billing Documents
- Journal Entries, Payments, Customers, Products, Plants

If the question is NOT related to this dataset, respond ONLY with:
"This system is designed to answer questions related to the provided SAP Order-to-Cash dataset only."
"""

ANSWER_SYNTHESIS_SYSTEM = """You are a SAP Order-to-Cash data analyst. Based on the SQL query results provided, generate a natural language summary that:
1. Answers the user's question directly
2. Provides key metrics or insights from the data
3. Highlights patterns or anomalies if relevant
4. Is concise but informative

Always ground your answer in the actual data provided, not assumptions.
Format INR currency values with ₹ symbol."""

SQL_SYSTEM_PROMPT = """You are a SQL expert for SAP Order-to-Cash data.

Database tables available:
- sales_order_headers (salesOrder, soldToParty, creationDate, totalNetAmount, overallDeliveryStatus, overallBillingStatus)
- sales_order_items (salesOrder, salesOrderItem, material, requestedQuantity, netAmount, plant)
- outbound_delivery_headers (deliveryDocument, creationDate, shippingPoint, soldToParty)
- outbound_delivery_items (deliveryDocument, deliveryDocumentItem, referenceSdDocument, material, actualDeliveryQuantity)
- billing_document_headers (billingDocument, soldToParty, totalNetAmount, billingDocumentDate, billingDocumentIsCancelled, accountingDocument, fiscalYear)
- billing_document_items (billingDocument, billingDocumentItem, material, netAmount, referenceSdDocument, referenceSdDocumentItem)
- journal_entry_items_accounts_receivable (accountingDocument, referenceDocument, customer, amountInTransactionCurrency, postingDate)
- payments_accounts_receivable (accountingDocument, customer, amountInTransactionCurrency, clearingAccountingDocument, clearingDate)
- business_partners (businessPartner, businessPartnerName, country, cityName)
- products (material, materialType, baseUnit, productGroup)
- plants (plant, plantName, country, cityName)

Generate ONLY a valid SQLite SELECT query. No explanations, no markdown, no code blocks. Return just the raw SQL."""


def _extract_sql(text: str) -> str:
    """Robustly extract SQL from LLM response — handles markdown, JSON, bare SQL."""
    text = text.strip()

    # Try JSON object {"sql": "..."}
    try:
        data = json.loads(text)
        if "sql" in data:
            return data["sql"].strip()
    except Exception:
        pass

    # Strip ```sql ... ``` or ``` ... ``` blocks
    match = re.search(r"```(?:sql)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Bare SELECT statement
    match = re.search(r"(SELECT[\s\S]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip().rstrip(";")

    return ""


class LLMService:
    def __init__(self):
        self.conversation_history: List[Dict[str, str]] = []
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key or api_key == "your_groq_api_key_here":
            self._enabled = False
            print("⚠️  Warning: GROQ_API_KEY not configured. LLM features disabled.")
        else:
            self._enabled = True
            print(f"✅ LLM ready: Groq / {MODEL}")

    def translate_nl_to_sql(self, user_prompt: str, context: Optional[str] = None) -> Tuple[str, bool]:
        """
        Translate natural language query to SQL.
        Returns: (sql_query, is_valid)
        """
        if not self._enabled:
            return self._fallback_sql_translation(user_prompt), False

        full_prompt = f"{SQL_GENERATION_EXAMPLES}\n\nUser query: {user_prompt}"
        if context:
            full_prompt += f"\nContext: {context}"

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SQL_SYSTEM_PROMPT},
                    {"role": "user",   "content": full_prompt}
                ],
                temperature=0.1,
                max_tokens=600,
            )
            raw = response.choices[0].message.content or ""
            sql = _extract_sql(raw)
            is_valid = self._validate_sql(sql)
            return sql, is_valid

        except Exception as e:
            print(f"LLM error: {e}")
            return self._fallback_sql_translation(user_prompt), False

    def synthesize_answer(
        self,
        user_prompt: str,
        sql_query: str,
        query_results: List[Dict[str, Any]]
    ) -> str:
        """Generate natural language answer from query results."""
        if not self._enabled:
            return self._fallback_answer(user_prompt, query_results)

        try:
            results_str = json.dumps(query_results[:20], indent=2, default=str)
            user_message = f"""User Question: {user_prompt}

SQL Query Executed:
{sql_query}

Query Results ({len(query_results)} rows total):
{results_str}

Generate a natural language answer based on these results."""

            # Build messages with conversation memory (last 6 turns)
            messages = [{"role": "system", "content": ANSWER_SYNTHESIS_SYSTEM}]
            for msg in self.conversation_history[-6:]:
                messages.append({"role": msg["role"], "content": msg["content"]})
            messages.append({"role": "user", "content": user_message})

            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=800,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Answer synthesis error: {e}")
            return self._fallback_answer(user_prompt, query_results)

    def add_to_history(self, user: str, assistant: str):
        """Add exchange to conversation history with timestamps."""
        ts = datetime.now().strftime('%Y-%m-%d %H:%M')
        self.conversation_history.append({
            "role": "user", "content": user, "timestamp": ts
        })
        self.conversation_history.append({
            "role": "assistant", "content": assistant, "timestamp": ts
        })
    def get_history(self) -> List[Dict[str, str]]:
        return self.conversation_history

    def clear_history(self):
        self.conversation_history = []

    # ── Fallback methods (no LLM needed) ─────────────────────────

    @staticmethod
    def _fallback_sql_translation(prompt: str) -> str:
        p = prompt.lower()
        if 'highest number' in p and 'billing' in p and 'product' in p:
            return "SELECT material, COUNT(*) as billing_count FROM billing_document_items GROUP BY material ORDER BY billing_count DESC LIMIT 10"
        if 'sales order' in p and 'customer' in p:
            return "SELECT salesOrder, creationDate, totalNetAmount FROM sales_order_headers LIMIT 20"
        if 'trace' in p or 'full flow' in p:
            return "SELECT * FROM sales_order_headers LIMIT 10"
        if 'delivery' in p and 'not billed' in p:
            return "SELECT DISTINCT so.salesOrder FROM sales_order_headers so LIMIT 20"
        if 'product' in p or 'material' in p:
            return "SELECT * FROM products LIMIT 20"
        return "SELECT * FROM sales_order_headers LIMIT 10"

    @staticmethod
    def _validate_sql(sql: str) -> bool:
        if not sql:
            return False
        upper = sql.upper().strip()
        if not upper.startswith("SELECT"):
            return False
        for dangerous in ("DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"):
            if dangerous in upper:
                return False
        return True

    @staticmethod
    def _fallback_answer(prompt: str, results: List[Dict[str, Any]]) -> str:
        if not results:
            return "No data found matching your query."
        answer = f"Found {len(results)} result(s):\n"
        for i, row in enumerate(results[:5], 1):
            answer += f"{i}. " + ", ".join(f"{k}={v}" for k, v in row.items()) + "\n"
        if len(results) > 5:
            answer += f"... and {len(results) - 5} more rows."
        return answer


# ── Singleton ─────────────────────────────────────────────────────
_llm_service: Optional[LLMService] = None

def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
