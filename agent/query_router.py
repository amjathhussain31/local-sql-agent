# agent/query_router.py

DOC_PHRASES = [
    "return policy", "refund policy", "sales policy", "discount policy",
    "what is our", "what are our", "tell me about", "annual report",
    "q3 report", "q4 report", "company overview", "our company",
    "compliance", "guidelines", "portfolio", "founded", "headquarters",
    "according to", "based on the report", "warranty", "guarantee",
]

SQL_KEYWORDS = [
    "show", "list", "count", "total", "sum", "average", "avg",
    "how many", "how much", "top", "bottom", "highest", "lowest",
    "sales", "revenue", "orders", "order", "customers", "customer",
    "products", "product", "stock", "inventory", "returns by",
    "return rate", "region", "category", "segment", "spend",
    "last", "this", "year", "month", "quarter", "week",
    "trend", "monthly", "yearly", "compare", "rank",
    "which product", "which region", "which customer",
    "perform", "performance",
]

DOC_KEYWORDS = [
    "policy", "annual", "report", "overview", "target", "goal",
    "strategy", "plan", "history", "refund", "document", "q3", "q4",
]


def route_query(query: str) -> str:
    """Returns: 'sql', 'rag', or 'hybrid'"""
    query_lower = query.lower()

    matched_doc = any(phrase in query_lower for phrase in DOC_PHRASES)

    if matched_doc:
        has_sql = any(kw in query_lower for kw in SQL_KEYWORDS)
        return "hybrid" if has_sql else "rag"

    has_sql = any(kw in query_lower for kw in SQL_KEYWORDS)
    has_doc = any(kw in query_lower for kw in DOC_KEYWORDS)

    if has_sql and has_doc:
        return "hybrid"
    elif has_doc and not has_sql:
        return "rag"
    return "sql"