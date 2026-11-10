# tools/schema_fetcher.py
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tools.dbhub_client import call_mcp, execute_sql

# Columns that are stored as TEXT but contain dates.
# Agent must use TO_DATE(col, 'YYYY-MM-DD') before any date arithmetic.
_DATE_TEXT_COLS = {"order_date", "return_date", "joined_date"}


def _extract_rows(response: dict) -> list:
    """
    Safely extracts rows from a DBHub execute_sql response dict.
    DBHub wraps results as:
    { "result": { "content": [{ "type": "text", "text": "{...json...}" }] } }
    """
    try:
        content = response.get("result", {}).get("content", [])
        if not content:
            return []
        text = content[0].get("text", "")
        data = json.loads(text)
        return data.get("data", {}).get("rows", [])
    except Exception:
        return []


def _extract_table_names(response: dict) -> list:
    """
    Extracts table names from a DBHub search_objects response dict.
    """
    try:
        content = response.get("result", {}).get("content", [])
        if not content:
            return []
        text = content[0].get("text", "")
        data = json.loads(text)
        return [r["name"] for r in data.get("data", {}).get("results", [])]
    except Exception:
        return []


def get_schema() -> str:
    """
    Fetches full database schema from Neon via DBHub.
    Returns formatted string ready for LLM prompt injection.

    DATE COLUMNS WARNING is injected here so the agent always knows
    order_date / return_date / joined_date are TEXT and need TO_DATE().
    """
    try:
        # ── Step 1: get table names ───────────────────────────
        response = call_mcp(
            "tools/call",
            {
                "name":      "search_objects",
                "arguments": {"object_type": "table"}
            }
        )
        tables = _extract_table_names(response)

        if not tables:
            return "Schema fetch error: no tables found in database"

        schema_lines = ["Database schema (PostgreSQL on Neon):\n"]

        # ── Step 2: get columns for each table ────────────────
        for table in tables:
            col_response = execute_sql(f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = '{table}'
                AND table_schema = 'public'
                ORDER BY ordinal_position
            """)
            rows = _extract_rows(col_response)

            col_parts = []
            for r in rows:
                col_name  = r["column_name"]
                data_type = r["data_type"]

                # Inject explicit warning for text date columns
                if col_name in _DATE_TEXT_COLS:
                    col_parts.append(
                        f"{col_name} ({data_type}) "
                        f"[DATE STORED AS TEXT — use TO_DATE({col_name},'YYYY-MM-DD') "
                        f"before EXTRACT/date functions]"
                    )
                else:
                    col_parts.append(f"{col_name} ({data_type})")

            schema_lines.append(f"  Table: {table}")
            schema_lines.append(f"    Columns: {', '.join(col_parts)}")

        # ── Step 3: get foreign keys ──────────────────────────
        fk_response = execute_sql("""
            SELECT
                tc.table_name,
                kcu.column_name,
                ccu.table_name  AS foreign_table,
                ccu.column_name AS foreign_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
        """)
        fk_rows = _extract_rows(fk_response)

        if fk_rows:
            schema_lines.append("\n  Foreign keys:")
            for fk in fk_rows:
                schema_lines.append(
                    f"    {fk['table_name']}.{fk['column_name']} "
                    f"→ {fk['foreign_table']}.{fk['foreign_column']}"
                )

        # ── Step 4: append global date reminder ───────────────
        schema_lines.append(
            "\n   DATE RULE: order_date, return_date, joined_date are TEXT columns."
            "\n   ALWAYS wrap with TO_DATE(column, 'YYYY-MM-DD') before any date operation."
            "\n   CORRECT:  EXTRACT(YEAR FROM TO_DATE(order_date, 'YYYY-MM-DD'))"
            "\n   WRONG:    EXTRACT(YEAR FROM order_date)  ← this will ERROR"
        )

        return "\n".join(schema_lines)

    except Exception as e:
        return f"Schema fetch error: {str(e)}"


def get_schema_as_tool_input(_: str = "") -> str:
    """LangChain tool wrapper — ignores input, returns schema."""
    return get_schema()