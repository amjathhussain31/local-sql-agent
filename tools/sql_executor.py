# tools/sql_executor.py
import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
from tools.dbhub_client import execute_sql as dbhub_execute
from guardrails.output_rails import classify_sql, SQLVerdict
from tools.dbhub_client import execute_sql as dbhub_execute, parse_result


def run_sql(sql: str, auto_approve: bool = False) -> dict:
    """
    Executes SQL through DBHub → Neon.
    Runs guardrail check first.
    Returns dict with success, df, row_count, verdict, error.
    """
    result = {
        "success":   False,
        "df":        None,
        "row_count": 0,
        "verdict":   "",
        "error":     None
    }

    # Guardrail check
    verdict, reason = classify_sql(sql)
    result["verdict"] = verdict.value

    if verdict == SQLVerdict.BLOCK:
        result["error"] = f"Blocked: {reason}"
        return result

    if verdict == SQLVerdict.HITL and not auto_approve:
        result["error"] = f"HITL_REQUIRED|||{sql}|||{reason}"
        return result

    # Execute via DBHub
    try:
        response = dbhub_execute(sql)

        # Parse DBHub response
        content = response.get("result", {}).get("content", [])
        if not content:
            result["error"] = "Empty response from DBHub"
            return result

        text = content[0].get("text", "")
        data = json.loads(text)

        if not data.get("success"):
            result["error"] = data.get("error", "Unknown DBHub error")
            return result

        rows = data.get("data", {}).get("rows", [])
        if rows:
            df = pd.DataFrame(rows)
            df = df.apply(pd.to_numeric, errors="ignore")
            result["success"]   = True
            result["df"]        = df
            result["row_count"] = len(df)
        else:
            result["success"]   = True
            result["row_count"] = 0

    except Exception as e:
        result["error"] = str(e)

    return result


def run_sql_as_string(sql: str, auto_approve: bool = False) -> str:
    """
    LangChain tool wrapper — returns string for agent observation.
    """
    result = run_sql(sql, auto_approve)

    if not result["success"]:
        error = result["error"]
        if error and error.startswith("HITL_REQUIRED"):
            return error
        return f"ERROR: {error}"

    df = result["df"]
    if df is None or df.empty:
        return "Query executed successfully but returned 0 rows."

    lines = [
        f"Rows returned: {result['row_count']}",
        f"Columns: {list(df.columns)}",
        df.to_string(index=False, max_rows=20)
    ]
    return "\n".join(lines)