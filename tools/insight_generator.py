# tools/insight_generator.py
import os
import sys
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
from langchain_groq import ChatGroq
from config import GROQ_API_KEY, GROQ_MODEL

INSIGHT_PROMPT = """You are a data analyst. A user asked a business question and a SQL query ran.
Summarize the results in 2-3 clear sentences.

User question: {query}

Query results:
{results_text}

Instructions:
- Start with the most important finding
- Include specific numbers from the results
- Keep it under 3 sentences
- Do not mention SQL or technical details
- Write for a non-technical business user"""


def generate_insight(query: str, df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "The query returned no results."
    try:
        results_text = df.head(20).to_string(index=False)
        llm          = ChatGroq(
            model=GROQ_MODEL,
            api_key=GROQ_API_KEY,
            temperature=0
        )
        prompt   = INSIGHT_PROMPT.format(query=query, results_text=results_text)
        response = llm.invoke(prompt)
        return response.content.strip()
    except Exception as e:
        return _fallback_insight(df)


def _fallback_insight(df: pd.DataFrame) -> str:
    num_cols = df.select_dtypes(include="number").columns.tolist()
    lines    = [f"Query returned {len(df)} rows and {len(df.columns)} columns."]
    if num_cols:
        col = num_cols[0]
        try:
            lines.append(
                f"{col}: min={df[col].min():.2f}, "
                f"max={df[col].max():.2f}, "
                f"avg={df[col].mean():.2f}"
            )
        except Exception:
            pass
    return " ".join(lines)


def generate_insight_from_string(input_str: str) -> str:
    """
    LangChain tool wrapper.
    Input format: 'user question|||JSON array of rows'
    """
    try:
        parts = input_str.split("|||")
        query = parts[0].strip() if len(parts) > 0 else ""
        data  = parts[1].strip() if len(parts) > 1 else "[]"
        rows  = json.loads(data)
        df    = pd.DataFrame(rows)
        return generate_insight(query, df)
    except Exception as e:
        return f"Could not generate insight: {str(e)[:80]}"