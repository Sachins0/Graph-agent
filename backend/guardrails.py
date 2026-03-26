import re
from typing import Dict, Any, List, Tuple
from enum import Enum


class QueryCategory(Enum):
    """Query categorization for guardrails."""
    O2C_QUERY = "o2c_query"  # Valid O2C domain query
    BLOCKED = "blocked"  # Explicitly blocked
    SUSPICIOUS = "suspicious"  # Might be harmful
    GENERIC = "generic"  # Generic knowledge (not dataset-specific)


class GuardrailsEngine:
    """
    Implements domain-based guardrails to restrict queries to O2C dataset.
    Prevents:
    - Off-topic/general knowledge questions
    - Attempts to access unrelated data
    - Potentially harmful prompts
    """

    def __init__(self):
        # O2C domain keywords - queries containing these are likely valid
        self.o2c_keywords = {
            'sales order', 'delivery', 'billing document', 'invoice', 'payment',
            'customer', 'product', 'material', 'journal entry', 'accounting',
            'purchase order', 'order status', 'delivery status', 'billing status',
            'outstanding amount', 'received invoice', 'shipped', 'delivered',
            'billed', 'fulfilled', 'accounts receivable', 'ar', 'plant', 'warehouse',
            'outbound delivery', 'inbound delivery', 'goods movement', 'picking',
            'billing block', 'delivery block', 'credit block', 'master data',
            'business partner', 'company code', 'sales organization'
        }

        # Phrases that indicate off-topic queries
        self.off_topic_patterns = {
            # General knowledge
            r'who is|who was|who are|biography of',
            r'what is the definition of|define ',
            r'how do i|how do you|how can i',
            r'what is the capital of|geography of',
            r'tell me about|what do you know about',
            # Creative/entertainment
            r'write me a|write a (poem|story|song|script)',
            r'what is your favorite|do you like',
            r'tell me a (joke|riddle|funny)',
            # Technical but unrelated
            r'how to (install|download|configure|setup) ',
            r'python (tutorial|guide|example)',
            r'javascript|react|angular|programming',
            r'sql injection|hack|exploit|vulnerability',
            # Other domains
            r'healthcare|medical|doctor|patient|disease',
            r'weather|climate|temperature',
            r'news|politics|sports|entertainment',
            r'legal|lawsuit|attorney|contract',
            r'financial advice|stock|investment|crypto'
        }

        # Absolutely blocked phrases
        self.blocked_patterns = {
            r'drop table|delete from|truncate|drop database',
            r'update .*set|insert into',
            r'system\(|exec\(|eval\(|__import__',
            r'union select|; drop|; delete',
            r'<script>|javascript:|onerror=',
            r'../|\.\.\/|etc/passwd'
        }

    def check_query(self, user_prompt: str) -> Tuple[bool, str, QueryCategory]:
        """
        Check if query is safe and domain-relevant.
        Returns: (is_safe, message, category)
        """
        prompt_lower = user_prompt.lower().strip()

        # Check for blocked patterns
        for pattern in self.blocked_patterns:
            if re.search(pattern, prompt_lower, re.IGNORECASE):
                return False, "❌ Query contains blocked keywords or syntax.", QueryCategory.BLOCKED

        # Check for off-topic patterns
        for pattern in self.off_topic_patterns:
            if re.search(pattern, prompt_lower, re.IGNORECASE):
                return False, "This system is designed to answer questions related to SAP Order-to-Cash data only. Please ask about sales orders, deliveries, billing, payments, or related business processes.", QueryCategory.GENERIC

        # Check for O2C relevance
        has_o2c_keyword = any(keyword in prompt_lower for keyword in self.o2c_keywords)

        if not has_o2c_keyword:
            # Give benefit of doubt for vague queries, but flag
            suspicious_score = self._calculate_suspicion_score(prompt_lower)
            if suspicious_score > 0.6:
                return False, "Query doesn't appear to be related to Order-to-Cash data. Please ask about sales orders, shipments, invoices, or payments.", QueryCategory.SUSPICIOUS

        return True, "✓ Query approved for processing", QueryCategory.O2C_QUERY

    def _calculate_suspicion_score(self, prompt: str) -> float:
        """Calculate how likely a query is off-topic (0.0 to 1.0)."""
        short_penalty = 0.2 if len(prompt) < 10 else 0  # Very short queries are suspicious
        generic_words = sum(1 for word in ['the', 'what', 'how', 'is', 'your', 'are'] if word in prompt.split())
        generic_score = min(generic_words / 6.0, 1.0)
        return (short_penalty + generic_score) / 2.0

    def get_context_hint(self, user_prompt: str) -> str:
        """Provide contextual hint for what this system can answer."""
        hints = []

        if any(word in user_prompt.lower() for word in ['order', 'purchase', 'sale']):
            hints.append("📦 I can help with sales order details, statuses, and history")
        if any(word in user_prompt.lower() for word in ['delivery', 'shipment', 'ship']):
            hints.append("🚚 I can help with delivery statuses, plant information, and tracking")
        if any(word in user_prompt.lower() for word in ['bill', 'invoice', 'amount', 'payment']):
            hints.append("💰 I can help with billing and payment information")
        if any(word in user_prompt.lower() for word in ['product', 'material', 'sku']):
            hints.append("📦 I can help with product and material master data")
        if any(word in user_prompt.lower() for word in ['customer', 'partner', 'company']):
            hints.append("👥 I can help with customer and business partner information")

        if not hints:
            hints.append("💡 This system contains SAP Order-to-Cash data, including sales orders, deliveries, billing documents, and payments")

        return "\n".join(hints)

    def extract_entities(self, user_prompt: str) -> Dict[str, List[str]]:
        """Extract potential business entities from query."""
        entities = {
            'sales_orders': [],
            'customers': [],
            'products': [],
            'delivery_ids': [],
            'invoice_ids': [],
        }

        # Extract numbers that might be IDs
        numbers = re.findall(r'\b\d{5,10}\b', user_prompt)

        if 'order' in user_prompt.lower():
            entities['sales_orders'] = numbers[:3]
        elif 'delivery' in user_prompt.lower():
            entities['delivery_ids'] = numbers[:3]
        elif 'invoice' in user_prompt.lower() or 'bill' in user_prompt.lower():
            entities['invoice_ids'] = numbers[:3]

        return entities


class EnforcedQuery:
    """Wrapper for queries that have passed guardrails."""

    def __init__(self, original_prompt: str, sql: str, category: QueryCategory, metadata: Dict[str, Any] = None):
        self.original_prompt = original_prompt
        self.sql = sql
        self.category = category
        self.metadata = metadata or {}
        self.executed = False
        self.results = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'original_prompt': self.original_prompt,
            'sql': self.sql,
            'category': self.category.value,
            'metadata': self.metadata,
            'results': self.results
        }


def get_guardrails() -> GuardrailsEngine:
    """Singleton guardrails engine."""
    if not hasattr(get_guardrails, '_instance'):
        get_guardrails._instance = GuardrailsEngine()
    return get_guardrails._instance
