# agent/react_agent.py
import os
import sys
import uuid
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import Tool
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferWindowMemory
from langchain_groq import ChatGroq

from config import GROQ_API_KEY, GROQ_MODEL
from memory.long_term import get_recent_history
from tools.schema_fetcher import get_schema, get_schema_as_tool_input
from tools.sql_executor import run_sql_as_string
from tools.chart_builder import build_chart_from_string
from tools.insight_generator import generate_insight_from_string


REACT_PROMPT_TEMPLATE = """You are DataAgent — an enterprise data analyst AI connected to a PostgreSQL database.

ABSOLUTE RULES — follow these without exception:
1. NEVER use "Action: None" — it is invalid. Always use a real tool or go to Final Answer.
2. For off-topic questions (poems, weather, jokes, stories), go DIRECTLY to Final Answer:
   Final Answer: I can only answer data and analytics questions about your database.
3. For UPDATE/INSERT/ALTER questions: call sql_executor with the SQL — guardrails handle approval.
4. For DELETE/DROP questions: call sql_executor with the SQL — guardrails will block it.
5. Never put Final Answer and Action in the same step. One or the other, never both.
6. chart_builder input must be ONLY a JSON array. No title. No extra text.
7. The order_date column is stored as TEXT in PostgreSQL. ALWAYS use
    TO_DATE(order_date, 'YYYY-MM-DD') when using EXTRACT or date functions.
    NEVER use EXTRACT(field FROM order_date) directly — it will fail.
    Correct: EXTRACT(YEAR FROM TO_DATE(order_date, 'YYYY-MM-DD'))
    Wrong:   EXTRACT(YEAR FROM order_date)

WORKFLOW for data questions:
Step 1: Call schema_fetcher to confirm table and column names
Step 2: Call sql_executor with the SQL query
Step 3: Call insight_generator with results
Step 4: Call chart_builder if results have numeric data
Step 5: Final Answer with complete response

TOOLS:
------
{tools}

DATABASE SCHEMA:
----------------
{schema}

LONG TERM MEMORY:
-----------------
{long_term_memory}

CONVERSATION HISTORY:
---------------------
{chat_history}

EXACT FORMAT — follow this precisely:

Question: the input question
Thought: your reasoning about what to do
Action: one tool from [{tool_names}]
Action Input: the input to the tool
Observation: the result of the tool
... (repeat Thought/Action/Action Input/Observation)
Thought: I now know the final answer
Final Answer: your complete answer to the user

EXAMPLES:

Example 1 — off-topic:
Question: Write me a poem
Thought: This is not a data question. I must go directly to Final Answer.
Final Answer: I can only answer data and analytics questions about your database.

Example 2 — UPDATE (agent calls sql_executor, guardrails return HITL signal):
Question: Update stock of Laptop Pro 15 to 100
Thought: This is an UPDATE. I will call sql_executor — guardrails will handle approval.
Action: sql_executor
Action Input: UPDATE products SET stock = 100 WHERE name = 'Laptop Pro 15'
Observation: HITL_REQUIRED|||UPDATE products SET stock = 100 WHERE name = 'Laptop Pro 15'|||'UPDATE' requires human approval
Thought: The guardrail requires human approval. I will inform the user.
Final Answer: This query requires human approval before execution. Please use the approval panel.

Example 3 — DELETE (blocked):
Question: Delete all customers
Thought: This is a DELETE. I will call sql_executor — guardrails will block it.
Action: sql_executor
Action Input: DELETE FROM customers
Observation: ERROR: Blocked: 'DELETE' is permanently blocked.
Thought: The guardrail blocked this. I will inform the user.
Final Answer: This operation is permanently blocked. DELETE queries are not permitted.

Begin!

Question: {input}
Thought: {agent_scratchpad}"""


def build_tools(vectorstore=None) -> list:
    tools = [
        Tool(
            name="schema_fetcher",
            func=get_schema_as_tool_input,
            description=(
                "Fetches the full database schema — tables, columns, foreign keys. "
                "Call this first before writing any SQL."
            )
        ),
        Tool(
            name="sql_executor",
            func=run_sql_as_string,
            description=(
                "Executes SQL on Neon PostgreSQL via DBHub. "
                "Input: raw SQL only — no markdown, no backticks. "
                "SELECT runs automatically. "
                "UPDATE/INSERT returns HITL_REQUIRED for human approval. "
                "DELETE/DROP is permanently blocked. "
                "Always call this for ANY SQL operation including UPDATE and DELETE."
            )
        ),
        Tool(
            name="insight_generator",
            func=generate_insight_from_string,
            description=(
                "Generates plain-English summary from SQL results. "
                "Input format: 'user question|||JSON array of result rows'"
            )
        ),
        Tool(
            name="chart_builder",
            func=build_chart_from_string,
            description=(
                "Builds a Plotly chart from query results. "
                "Input: JSON array string ONLY. No title. No extra text. "
                "Example: [{\"region\":\"East\",\"sales\":74264.61}]"
            )
        ),
    ]

    if vectorstore is not None:
        from rag.retriever import retrieve_context
        tools.append(Tool(
            name="rag_retriever",
            func=lambda q: retrieve_context(vectorstore, q),
            description=(
                "Searches enterprise documents: company reports, policies, portfolios. "
                "Use ONLY for document questions, NOT for database queries."
            )
        ))

    return tools


def build_agent(memory: ConversationBufferWindowMemory,
                vectorstore=None) -> AgentExecutor:

    llm = ChatGroq(
        model=GROQ_MODEL,
        api_key=GROQ_API_KEY,
        temperature=0
    )
    print(f"[agent] Using Groq — {GROQ_MODEL}")

    tools  = build_tools(vectorstore)
    schema = get_schema()

    prompt = PromptTemplate(
        input_variables=[
            "input", "tools", "tool_names",
            "agent_scratchpad", "chat_history",
            "schema", "long_term_memory"
        ],
        template=REACT_PROMPT_TEMPLATE
    )

    agent = create_react_agent(llm, tools, prompt)

    return AgentExecutor(
        agent=agent,
        tools=tools,
        memory=memory,
        verbose=True,
        max_iterations=10,
        handle_parsing_errors=True,
        return_intermediate_steps=True
    )


def run_agent(agent_executor: AgentExecutor,
              query: str,
              session_id: str = None) -> dict:

    if session_id is None:
        session_id = str(uuid.uuid4())

    long_term = get_recent_history(n=3)
    schema    = get_schema()

    callbacks = []
    try:
        from observability.langfuse_client import get_langchain_handler, flush
        handler   = get_langchain_handler(session_id=session_id,
                                          trace_name=f"agent: {query[:50]}")
        callbacks = [handler]
    except Exception:
        pass

    for attempt in range(3):
        try:
            result = agent_executor.invoke(
                {
                    "input":            query,
                    "schema":           schema,
                    "long_term_memory": long_term,
                },
                config={"callbacks": callbacks}
            )
            try:
                flush()
            except Exception:
                pass
            return {
                "output":     result.get("output", ""),
                "steps":      result.get("intermediate_steps", []),
                "error":      None,
                "session_id": session_id
            }
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                wait = 20 * (attempt + 1)
                print(f"[rate limit] Waiting {wait}s... retry {attempt+2}/3")
                time.sleep(wait)
            else:
                return {
                    "output":     "",
                    "steps":      [],
                    "error":      str(e),
                    "session_id": session_id
                }