import re
from typing import Any, Dict, List, Tuple
from enum import Enum


class QueryCategory(Enum):
    O2C_QUERY   = "o2c_query"
    BLOCKED     = "blocked"
    SUSPICIOUS  = "suspicious"
    GENERIC     = "generic"


class GuardrailsEngine:
    def __init__(self):
        self.o2c_keywords = {
            'sales order', 'delivery', 'billing document', 'invoice', 'payment',
            'customer', 'product', 'material', 'journal entry', 'accounting',
            'purchase order', 'order status', 'delivery status', 'billing status',
            'outstanding amount', 'shipped', 'delivered', 'billed', 'fulfilled',
            'accounts receivable', 'plant', 'warehouse', 'outbound delivery',
            'goods movement', 'billing block', 'delivery block', 'business partner',
            'company code', 'sales organization', 'fiscal year', 'net amount',
            'trace', 'flow', 'incomplete', 'cancelled', 'clearing', 'journal',
        }

        self.off_topic_patterns = [
            r'who is|who was|who are|biography of',
            r'what is the definition of|define ',
            r'what is the capital of|geography',
            r'write me a|write a (?:poem|story|song|script|essay)',
            r'what is your favorite|do you like',
            r'tell me a (?:joke|riddle|funny)',
            r'how to (?:install|download|configure|setup) ',
            r'python tutorial|javascript|react tutorial|programming guide',
            r'healthcare|medical|doctor|patient|disease',
            r'weather|climate|temperature today',
            r'(?:latest )?news|politics|sports score|entertainment',
            r'financial advice|stock price|investment|cryptocurrency',
            r'recipe|how to cook',
        ]

        self.blocked_patterns = [
            r'drop\s+table|delete\s+from|truncate\s+table|drop\s+database',
            r'update\s+\w+\s+set|insert\s+into',
            r'system\s*\(|exec\s*\(|eval\s*\(|__import__',
            r'union\s+select|;\s*drop|;\s*delete',
            r'<script|onclick=|javascript:',
            r'ignore\s+previous|disregard\s+instructions|you\s+are\s+now',
        ]

    def check_query(self, query: str) -> Tuple[bool, str, QueryCategory]:
        """
        Check if query is safe and domain-relevant.
        Returns: (is_safe, message, category)
        """
        q_lower = query.lower().strip()

        # 1. Hard block — SQL injection / prompt injection
        for pattern in self.blocked_patterns:
            if re.search(pattern, q_lower, re.IGNORECASE):
                return (
                    False,
                    "This query contains potentially harmful content and has been blocked.",
                    QueryCategory.BLOCKED
                )

        # 2. Off-topic check
        for pattern in self.off_topic_patterns:
            if re.search(pattern, q_lower, re.IGNORECASE):
                # Double-check: does it also contain O2C keywords?
                if not any(kw in q_lower for kw in self.o2c_keywords):
                    return (
                        False,
                        "This system is designed to answer questions related to the provided SAP Order-to-Cash dataset only.",
                        QueryCategory.GENERIC
                    )

        # 3. Domain relevance check
        has_o2c_keyword  = any(kw in q_lower for kw in self.o2c_keywords)
        has_numeric_id   = bool(re.search(r'\b\d{5,}\b', query))  # doc IDs are typically 5+ digits
        has_o2c_question = any(word in q_lower for word in [
            'how many', 'which', 'list', 'show', 'find', 'trace', 'what',
            'top', 'count', 'total', 'amount', 'status'
        ])

        if has_o2c_keyword or has_numeric_id:
            return True, "Valid O2C query.", QueryCategory.O2C_QUERY

        if has_o2c_question and len(query.split()) <= 15:
            # Short ambiguous question — allow with hint
            return True, "Proceeding with query.", QueryCategory.O2C_QUERY

        # 4. Suspicious — vague but not clearly off-topic
        if len(q_lower) < 5:
            return (
                False,
                "Query too short. Please ask a specific question about the O2C dataset.",
                QueryCategory.SUSPICIOUS
            )

        # Default: allow, let LLM handle
        return True, "Query accepted.", QueryCategory.O2C_QUERY

    def get_context_hint(self, query: str) -> str:
        """Return a helpful hint about what the system can answer."""
        q_lower = query.lower()
        hints = []

        if any(w in q_lower for w in ['product', 'material', 'billing']):
            hints.append("Try: 'Which products appear in the most billing documents?'")
        if any(w in q_lower for w in ['trace', 'flow', 'order']):
            hints.append("Try: 'Trace the full flow of billing document 91150187'")
        if any(w in q_lower for w in ['delivery', 'billed', 'incomplete']):
            hints.append("Try: 'Find sales orders that were delivered but not billed'")
        if any(w in q_lower for w in ['payment', 'customer', 'outstanding']):
            hints.append("Try: 'Which customers have pending payments?'")

        if not hints:
            hints = [
                "This system can answer questions about:",
                "• Sales Orders and their items",
                "• Delivery documents and status",
                "• Billing documents and invoices",
                "• Journal entries and payments",
                "• Customer and product data",
            ]

        return "\n".join(hints)

    def extract_entities(self, query: str) -> Dict[str, List[str]]:
        """Extract mentioned entity IDs from a query."""
        entities: Dict[str, List[str]] = {
            'billing_documents': [],
            'sales_orders':      [],
            'customers':         [],
            'materials':         [],
            'deliveries':        [],
            'accounting_docs':   [],
        }

        # Billing documents: typically 8-digit numbers starting with 9
        entities['billing_documents'] = re.findall(r'\b9\d{7}\b', query)

        # Sales orders: typically 8-digit numbers starting with 7 or 8
        entities['sales_orders'] = re.findall(r'\b[78]\d{7}\b', query)

        # Customers: typically starting with 3 (e.g. 320000082)
        entities['customers'] = re.findall(r'\b3\d{8}\b', query)

        # Accounting documents: 10-digit numbers starting with 94
        entities['accounting_docs'] = re.findall(r'\b94\d{8}\b', query)

        # Materials: alphanumeric codes like S8907367042006
        entities['materials'] = re.findall(r'\b[A-Z]\d{13}\b', query)

        return entities


# ── Singleton ──────────────────────────────────────────────────────
_guardrails_instance: GuardrailsEngine = None


def get_guardrails() -> GuardrailsEngine:
    global _guardrails_instance
    if _guardrails_instance is None:
        _guardrails_instance = GuardrailsEngine()
    return _guardrails_instance
