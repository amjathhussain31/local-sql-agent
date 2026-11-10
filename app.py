# app.py
"""
NL-to-SQL DataAgent — Futuristic SaaS UI
Run: streamlit run app.py
"""
import uuid, sys, os, re
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(
    page_title="DataAgent",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────
# Load CSS from static/styles.css
# ─────────────────────────────────────────
_CSS_PATH = os.path.join(os.path.dirname(__file__), "static", "styles.css")

def _load_css():
    if os.path.exists(_CSS_PATH):
        with open(_CSS_PATH, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"[CSS missing] Expected: {_CSS_PATH}")

_load_css()

# ─────────────────────────────────────────
# Backend imports — matched to your project
# ─────────────────────────────────────────
from config import FAISS_INDEX_PATH

from agent.react_agent          import build_agent, run_agent
from agent.query_router         import route_query

from memory.short_term          import get_short_term_memory
from memory.long_term           import (save_interaction, get_recent_history,
                                        get_all_history, clear_history)

from rag.embedder               import load_vectorstore, rebuild_index

from guardrails.pipeline        import run_input_rails
from guardrails.output_rails    import classify_sql, SQLVerdict

from tools.sql_executor         import run_sql, run_sql_as_string
from tools.chart_builder        import build_chart, detect_chart_type
from tools.insight_generator    import generate_insight_from_string

try:
    from observability.langfuse_client import flush
    _LANGFUSE = True
except Exception:
    _LANGFUSE = False

try:
    from tools.dbhub_client import list_tools as _dbhub_list_tools
    _DBHUB = True
except Exception:
    _DBHUB = False

import re as _re
import pandas as pd


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────
def _dbhub_status() -> tuple[bool, int]:
    if not _DBHUB:
        return False, 0
    try:
        result = _dbhub_list_tools()
        tools  = result.get("result", {}).get("tools", [])
        return len(tools) > 0, len(tools)
    except Exception:
        return False, 0


def _safe_flush():
    if _LANGFUSE:
        try:
            flush()
        except Exception:
            pass


# ─────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────
def init_session():
    defaults = {
        "session_id":         str(uuid.uuid4()),
        "messages":           [],
        "memory":             get_short_term_memory(k=6),
        "vectorstore":        None,
        "agent":              None,
        "pending_hitl":       None,
        "trace_steps":        [],
        "db_label":           "Neon · PostgreSQL",
        "db_status":          "online",
        "pending_suggestion": None,
        "total_queries":      0,
        "trace_panel_open":   True,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # Load vectorstore once
    if st.session_state.vectorstore is None:
        try:
            st.session_state.vectorstore = load_vectorstore(FAISS_INDEX_PATH)
        except Exception:
            st.session_state.vectorstore = None


def get_agent():
    if st.session_state.agent is None:
        with st.spinner("⬡ Initialising agent…"):
            # build_agent does NOT take db_url — DBHub handles the DB
            st.session_state.agent = build_agent(
                memory=st.session_state.memory,
                vectorstore=st.session_state.vectorstore,
            )
    return st.session_state.agent


# ─────────────────────────────────────────
# LEFT SIDEBAR
# ─────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        # Logo
        st.markdown("""
        <div class="sidebar-logo">
          <div class="logo-mark">
            <div class="hexagon"></div>
            <span class="brand-name">DataAgent</span>
          </div>
          <div class="brand-sub">Natural Language SQL Interface</div>
        </div>
        """, unsafe_allow_html=True)

        # New Chat
        if st.button("＋  New Chat", key="new_chat_btn",
                     use_container_width=True, type="primary"):
            st.session_state.messages         = []
            st.session_state.memory           = get_short_term_memory(k=6)
            st.session_state.agent            = None
            st.session_state.trace_steps      = []
            st.session_state.pending_hitl     = None
            st.session_state.pending_suggestion = None
            st.rerun()

        # Recent history list
        history = get_all_history()
        if history:
            st.markdown('<div class="sidebar-section-label">Recent</div>',
                        unsafe_allow_html=True)
            for h in reversed(history[-6:]):
                label = h["query"][:36] + ("…" if len(h["query"]) > 36 else "")
                st.markdown(f"""
                <div class="chat-hist-item">
                  <span class="dot"></span>{label}
                </div>""", unsafe_allow_html=True)

        st.markdown("<hr>", unsafe_allow_html=True)

        # DBHub / DB status
        st.markdown('<div class="sidebar-section-label">Database</div>',
                    unsafe_allow_html=True)

        dbhub_ok, n_tools = _dbhub_status()
        badge_cls = "online" if dbhub_ok else "offline"
        badge_txt = f"DBHub · {n_tools} tools" if dbhub_ok else "DBHub · offline"
        st.markdown(f'<span class="status-badge {badge_cls}">{badge_txt}</span>',
                    unsafe_allow_html=True)

        st.markdown("""
        <div style="margin:8px 0 4px;font-family:var(--font-mono);
                    font-size:9px;color:var(--text-muted);">
          Neon PostgreSQL via DBHub MCP
        </div>
        """, unsafe_allow_html=True)

        if st.button("Refresh status", use_container_width=True, key="db_refresh"):
            ok, _ = _dbhub_status()
            st.session_state.db_status = "online" if ok else "offline"
            st.session_state.agent     = None   # rebuild on next query
            st.rerun()

        st.markdown("<hr>", unsafe_allow_html=True)

        # Knowledge base / RAG
        st.markdown('<div class="sidebar-section-label">Knowledge Base</div>',
                    unsafe_allow_html=True)

        if st.session_state.vectorstore:
            n = st.session_state.vectorstore.index.ntotal
            st.markdown(f'<span class="status-badge online">{n} chunks indexed</span>',
                        unsafe_allow_html=True)
            if os.path.exists("data/docs"):
                for f in os.listdir("data/docs"):
                    if f.endswith((".txt",".pdf",".csv")):
                        st.caption(f"  📄 {f}")
        else:
            st.markdown('<span class="status-badge offline">No index</span>',
                        unsafe_allow_html=True)

        uploaded = st.file_uploader(
            "Upload docs", type=["pdf","csv","txt"],
            accept_multiple_files=True,
            label_visibility="collapsed", key="doc_upload")

        if uploaded and st.button("Index docs", type="primary",
                                  use_container_width=True, key="idx_btn"):
            _handle_doc_upload(uploaded)

        st.markdown("<hr>", unsafe_allow_html=True)

        # Session info
        st.markdown('<div class="sidebar-section-label">Session</div>',
                    unsafe_allow_html=True)
        sid = st.session_state.session_id[:8]
        q   = st.session_state.total_queries
        st.markdown(f"""
        <div style="padding:6px 0 10px;">
          <div style="display:flex;justify-content:space-between;align-items:baseline;">
            <span style="font-family:var(--font-mono);font-size:9px;
                         color:var(--text-muted);">ID · {sid}…</span>
            <span style="font-family:var(--font-mono);font-size:18px;
                         font-weight:700;color:var(--accent-cyan);">{q}</span>
          </div>
          <div style="font-family:var(--font-mono);font-size:8px;
                      color:var(--text-dim);text-align:right;margin-top:-2px;">
            queries this session
          </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Clear memory", use_container_width=True, key="clr_mem"):
            clear_history()
            st.session_state.messages         = []
            st.session_state.trace_steps      = []
            st.session_state.total_queries    = 0
            st.rerun()


def _handle_doc_upload(files):
    os.makedirs("data/docs", exist_ok=True)
    saved = []
    for f in files:
        p = f"data/docs/{f.name}"
        with open(p, "wb") as out:
            out.write(f.read())
        saved.append(f.name)
    with st.spinner(f"Indexing {len(saved)} file(s)…"):
        try:
            vs = rebuild_index("data/docs", FAISS_INDEX_PATH)
            st.session_state.vectorstore = vs
            st.session_state.agent       = None
            st.success(f"Indexed: {', '.join(saved)}")
        except Exception as e:
            st.error(f"Failed: {e}")


# ─────────────────────────────────────────
# TOP NAVBAR
# ─────────────────────────────────────────
def render_navbar():
    db_status = st.session_state.get("db_status", "online")
    db_label  = st.session_state.get("db_label",  "Neon · PostgreSQL")
    badge_cls = "online" if db_status == "online" else "offline"
    msgs      = len(st.session_state.messages)
    panel_open = st.session_state.get("trace_panel_open", True)
    toggle_icon = "▶" if panel_open else "◀"

    # Render navbar with toggle button embedded directly inside the nav
    st.markdown(f"""
    <div class="top-nav">
      <div class="nav-left">
        <div class="nav-breadcrumb">
          <span>DataAgent</span>
          <span class="sep">/</span>
          <span class="active">Chat</span>
        </div>
        <span class="status-badge {badge_cls}">{db_label}</span>
      </div>
      <div class="nav-right">
        <div class="nav-pill">⬡ Groq ·openai/gpt-oss-120b</div>
        <div class="nav-pill">{msgs} msgs</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Toggle button inside a keyed container — CSS targets the key to fix it top-right
    with st.container(key="toggle_trace_container"):
        if st.button(f"{toggle_icon}", key="toggle_trace_btn"):
            st.session_state.trace_panel_open = not panel_open
            st.rerun()


# ─────────────────────────────────────────
# HITL APPROVAL PANEL
# ─────────────────────────────────────────
def render_hitl_approval():
    if not st.session_state.pending_hitl:
        return

    p      = st.session_state.pending_hitl
    sql    = p["sql"]
    reason = p["reason"]
    query  = p.get("query", "")

    st.markdown(f"""
    <div class="hitl-banner">
      <div class="hitl-title">⚠ Human Approval Required</div>
      <div class="hitl-sub">Triggered by: "{query[:60]}"</div>
    </div>
    """, unsafe_allow_html=True)

    st.code(sql, language="sql")
    st.caption(f"Reason: {reason}")

    c1, c2, _ = st.columns([1, 1, 5])

    if c1.button("✅ Approve", type="primary", key="hitl_approve"):
        # run_sql is the correct function — no db_url needed
        r = run_sql(sql, auto_approve=True)
        st.session_state.pending_hitl = None
        content = (f"✅ Executed — {r['row_count']} row(s) affected."
                   if r["success"] else f"❌ Failed: {r['error']}")
        st.session_state.messages.append({
            "role": "assistant", "content": content,
            "id": str(uuid.uuid4())[:8]
        })
        st.rerun()

    if c2.button("❌ Reject", key="hitl_reject"):
        st.session_state.pending_hitl = None
        st.session_state.messages.append({
            "role": "assistant",
            "content": "❌ Query rejected — no changes made.",
            "id": str(uuid.uuid4())[:8]
        })
        st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)


# ─────────────────────────────────────────
# WELCOME SCREEN  (safe — no query calls)
# ─────────────────────────────────────────
def render_welcome():
    st.markdown("""
    <div class="welcome-screen">
      <div class="welcome-glyph">⬡</div>
      <h1 class="welcome-title">Ask your <span>database</span><br>anything</h1>
      <p class="welcome-sub">
        DataAgent converts natural language into SQL, executes queries on your
        Neon PostgreSQL database, and returns insights with charts —
        powered by Groq&nbsp;+&nbsp;Gemini via DBHub MCP.
      </p>
      <div class="chips-label">Try one of these →</div>
    </div>
    """, unsafe_allow_html=True)

    suggestions = [
        ("📊", "Show total sales by region"),
        ("🏆", "Top 5 customers by spend"),
        ("↩️", "Which category has most returns?"),
        ("📦", "Products with low stock"),
        ("📈", "Monthly revenue trend for all time"),
        ("🧮", "What is the average order value?"),
    ]

    st.markdown(
        '<div style="max-width:580px;margin:0 auto;padding:0 24px 80px;">',
        unsafe_allow_html=True)
    cols = st.columns(2, gap="small")
    for i, (icon, label) in enumerate(suggestions):
        with cols[i % 2]:
            if st.button(f"{icon}  {label}", key=f"chip_{i}",
                         use_container_width=True):
                # Store and process after rerun — avoids running inside render
                st.session_state.pending_suggestion = label
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────
# CHAT MESSAGES RENDERER
# ─────────────────────────────────────────
def render_messages():
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg.get("blocked"):
                st.markdown(
                    '<div class="blocked-tag">🛡 BLOCKED</div>',
                    unsafe_allow_html=True)
                st.error(msg.get("block_reason", msg["content"]))
            else:
                # Show route badge for assistant messages
                if msg["role"] == "assistant" and msg.get("route"):
                    route = msg["route"]
                    label = {"sql":"⚡ SQL","rag":"📚 RAG","hybrid":"⬡ Hybrid"}.get(route, route)
                    st.markdown(
                        f'<div class="route-badge {route}">{label}</div>',
                        unsafe_allow_html=True)

                st.write(msg["content"])

            if msg.get("sql"):
                with st.expander("⚡ Generated SQL", expanded=False):
                    st.code(msg["sql"], language="sql")

            if msg.get("chart") is not None:
                st.plotly_chart(msg["chart"], use_container_width=True,
                                key=f"chart_{msg.get('id','x')}")


# ─────────────────────────────────────────
# QUERY PROCESSOR
# ─────────────────────────────────────────
def process_query(query: str):
    msg_id   = str(uuid.uuid4())[:8]
    trace_id = str(uuid.uuid4())

    # Show user message immediately
    st.session_state.messages.append({
        "role": "user", "content": query, "id": msg_id
    })
    with st.chat_message("user"):
        st.write(query)

    # ── 1. Destructive keyword hard block ─────────────────────
    if re.search(r'\b(drop|delete|truncate|erase)\b', query.lower()):
        msg = ("🛡️ Permanently blocked — DROP, DELETE and TRUNCATE "
               "are never permitted. This agent is read-only by default.")
        _append_blocked(msg, msg, msg_id)
        with st.chat_message("assistant"):
            st.markdown('<div class="blocked-tag">🛡 BLOCKED</div>',
                        unsafe_allow_html=True)
            st.error(msg)
        return

    # ── 2. Input guardrails ───────────────────────────────────
    # run_input_rails — call without trace_id if your version doesn't accept it
    try:
        allowed, reason = run_input_rails(query, trace_id=trace_id)
    except TypeError:
        allowed, reason = run_input_rails(query)

    if not allowed:
        _append_blocked(reason, reason, msg_id)
        with st.chat_message("assistant"):
            st.markdown('<div class="blocked-tag">🛡 BLOCKED</div>',
                        unsafe_allow_html=True)
            st.error(reason)
        return

    # ── 3. Route the query ────────────────────────────────────
    route = route_query(query)   # "sql" | "rag" | "hybrid"

    # ── 4. Run agent ──────────────────────────────────────────
    with st.chat_message("assistant"):
        with st.spinner("⬡ Thinking…"):
            agent  = get_agent()
            result = run_agent(agent, query,
                               session_id=st.session_state.session_id)

        if result["error"]:
            try:
                from agent.error_handler import classify_error
                err = classify_error(result["error"])
                if err["retry"]:
                    st.warning(err["message"])
                else:
                    st.error(err["message"])
                content = err["message"]
            except Exception:
                content = result["error"][:140]
                st.error(content)
            st.session_state.messages.append({
                "role": "assistant", "content": content, "id": msg_id
            })
            return

        st.session_state.trace_steps  = result["steps"]
        st.session_state.total_queries += 1

        # ── 5. HITL signal ────────────────────────────────────
        hitl = _find_signal(result["steps"], "HITL_REQUIRED|||")
        if hitl:
            st.session_state.pending_hitl = {
                "sql": hitl["sql"], "reason": hitl["reason"],
                "query": query, "msg_id": msg_id
            }
            content = "⚠️ This query requires your approval — see the panel above."
            st.session_state.messages.append({
                "role": "assistant", "content": content, "id": msg_id
            })
            st.write(content)
            st.rerun()
            return

        # ── 6. Permanent block signal ─────────────────────────
        blk = _find_signal(result["steps"], "BLOCKED|||")
        if blk:
            msg = f"🛡️ **Permanently blocked** — {blk['reason']}"
            st.markdown('<div class="blocked-tag">🛡 BLOCKED</div>',
                        unsafe_allow_html=True)
            st.error(msg)
            _append_blocked(msg, blk["reason"], msg_id)
            return

        # ── 7. Extract SQL + build chart ──────────────────────
        sql, df_from_steps = _extract_sql_and_df(result["steps"])
        chart = None

        if df_from_steps is not None and not df_from_steps.empty:
            if len(df_from_steps.columns) >= 2 and len(df_from_steps) >= 2:
                try:
                    chart = build_chart(df_from_steps, title=query[:52])
                except Exception as e:
                    st.caption(f"Chart error: {e}")
                    chart = None
        elif sql:
            # fallback: re-run the SQL
            r = run_sql(sql)
            if r["success"] and r["df"] is not None and not r["df"].empty:
                df = r["df"]
                if len(df.columns) >= 2:
                    try:
                        chart = build_chart(df, title=query[:52])
                    except Exception:
                        chart = None

        # ── 8. Show route badge + output ──────────────────────
        route_label = {"sql":"⚡ SQL","rag":"📚 RAG","hybrid":"⬡ Hybrid"}.get(route, route)
        st.markdown(f'<div class="route-badge {route}">{route_label}</div>',
                    unsafe_allow_html=True)

        output = result["output"]
        # Strip "Chart ready:..." lines and raw data tables the agent pastes
        output = _re.sub(r'Chart ready:.*', '', output, flags=_re.IGNORECASE).strip()
        output = _re.sub(r'\nData:[\s\S]*', '', output).strip()
        output = _re.sub(r'\n\|.*', '', output).strip()   # markdown table rows
        st.write(output)

        if sql:
            with st.expander("⚡ Generated SQL", expanded=False):
                st.code(sql, language="sql")

        if chart:
            st.plotly_chart(chart, use_container_width=True,
                            key=f"chart_{msg_id}")

        # ── 9. Persist ────────────────────────────────────────
        save_interaction(query, sql or "", output, "", 0)
        _safe_flush()

        st.session_state.messages.append({
            "role":    "assistant",
            "content": output,
            "sql":     sql,
            "chart":   chart,
            "route":   route,
            "id":      msg_id,
        })


# ─────────────────────────────────────────
# Signal / SQL step helpers
# ─────────────────────────────────────────
def _append_blocked(content, reason, msg_id):
    st.session_state.messages.append({
        "role": "assistant", "content": content,
        "blocked": True, "block_reason": reason, "id": msg_id
    })


def _find_signal(steps, prefix):
    for action, obs in steps:
        if action.tool == "sql_executor" and str(obs).startswith(prefix):
            parts = str(obs).split("|||")
            return {
                "sql":    parts[1] if len(parts) > 1 else "",
                "reason": parts[2] if len(parts) > 2 else "",
            }
    return None


def _extract_sql(steps):
    for action, _ in steps:
        if action.tool == "sql_executor":
            sql = str(action.tool_input).strip()
            if sql.upper().startswith("SELECT"):
                return sql
    return ""

def _extract_sql_and_df(steps):
    """
    Returns (sql, dataframe).
    Priority: parse DataFrame from chart_builder tool input JSON.
    Fallback: re-run the SQL.
    """
    import pandas as pd
    import json

    sql = _extract_sql(steps)
    df  = None

    # First choice: get data from chart_builder's JSON input
    for action, obs in steps:
        if action.tool == "chart_builder":
            try:
                raw = str(action.tool_input).strip()
                data = json.loads(raw)
                if isinstance(data, list) and len(data) > 0:
                    df = pd.DataFrame(data)
                    return sql, df
            except Exception:
                pass

    # Fallback: re-run SQL only if chart_builder JSON not found
    if sql:
        try:
            r = run_sql(sql)
            if r["success"] and r["df"] is not None and not r["df"].empty:
                df = r["df"]
        except Exception:
            pass

    return sql, df


# ─────────────────────────────────────────
# RIGHT PANEL — Trace + Memory
# ─────────────────────────────────────────
def render_right_panel():
    st.markdown("""
    <div class="tab-bar">
      <div class="tab-item active">⬡&nbsp; Trace and Memory</div>
    </div>
    """, unsafe_allow_html=True)

    steps = st.session_state.trace_steps

    if not steps:
        st.markdown("""
        <div style="padding:28px 16px;text-align:center;">
          <div style="font-family:var(--font-mono);font-size:11px;
                      color:var(--text-muted);line-height:2.2;">
            ∅ No trace yet<br>
            <span style="font-size:9px;">Run a query to see agent steps</span>
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        tool_icons = {
            "schema_fetcher":    "🗂",
            "sql_executor":      "⚡",
            "rag_retriever":     "📚",
            "insight_generator": "💡",
            "chart_builder":     "📊",
        }
        n = len(steps)
        st.markdown(f"""
        <div style="padding:8px 16px 4px;display:flex;align-items:center;gap:8px;">
          <div class="trace-dot"></div>
          <span style="font-family:var(--font-mono);font-size:9px;
                       letter-spacing:0.12em;text-transform:uppercase;
                       color:var(--text-muted);">{n} step{"s" if n!=1 else ""} executed</span>
        </div>
        """, unsafe_allow_html=True)

        for i, (action, obs) in enumerate(steps):
            icon    = tool_icons.get(action.tool, "🔧")
            inp_txt = str(action.tool_input)[:220]
            out_txt = str(obs)[:280]
            with st.expander(f"{icon} Step {i+1} · {action.tool}",
                             expanded=(i == n - 1)):
                st.markdown(f"""
                <div class="trace-io-label">INPUT</div>
                <div class="trace-io input-block">{inp_txt}</div>
                <div class="trace-io-label" style="margin-top:6px;">OUTPUT</div>
                <div class="trace-io output-block">{out_txt}</div>
                """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # Memory section
    st.markdown('<div class="section-hdr">🧠 Long-term Memory</div>',
                unsafe_allow_html=True)

    history = get_all_history()
    if history:
        st.markdown(f"""
        <div style="padding:4px 16px 8px;">
          <span style="font-family:var(--font-mono);font-size:9px;color:var(--text-muted);">
            {len(history)} interactions stored
          </span>
        </div>
        """, unsafe_allow_html=True)
        for h in reversed(history[-4:]):
            q = h["query"][:42] + ("…" if len(h["query"]) > 42 else "")
            with st.expander(q, expanded=False):
                if h.get("sql"):
                    st.code(h["sql"][:180], language="sql")
                if h.get("summary"):
                    st.caption(h["summary"][:90])
    else:
        st.markdown("""
        <div style="padding:12px 16px;font-family:var(--font-mono);
                    font-size:10px;color:var(--text-dim);">No memory yet</div>
        """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("""
    <div style="padding:8px 16px;">
      <a href="https://cloud.langfuse.com" target="_blank"
         style="font-family:var(--font-mono);font-size:10px;
                color:var(--accent-cyan);text-decoration:none;">
        ↗ View in Langfuse
      </a>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def main():
    init_session()
    render_sidebar()
    render_navbar()
    render_hitl_approval()

    # ── Handle suggestion chip clicks (stored from welcome screen) ──
    if st.session_state.get("pending_suggestion"):
        q = st.session_state.pop("pending_suggestion")
        process_query(q)
        st.rerun()

    # ── Layout: conditional two-column or full-width ──────────────
    panel_open = st.session_state.get("trace_panel_open", True)

    if panel_open:
        col_chat, col_trace = st.columns([3, 2], gap="small")

        with col_trace:
            st.markdown('<div class="right-panel-wrap">', unsafe_allow_html=True)
            render_right_panel()
            st.markdown("</div>", unsafe_allow_html=True)

        with col_chat:
            if not st.session_state.messages:
                render_welcome()
            else:
                render_messages()

            query = st.chat_input("Ask anything about your data…",
                                  key="chat_input")
            if query:
                process_query(query)
                st.rerun()
    else:
        # Full-width chat when trace panel is closed
        if not st.session_state.messages:
            render_welcome()
        else:
            render_messages()

        query = st.chat_input("Ask anything about your data…",
                              key="chat_input")
        if query:
            process_query(query)
            st.rerun()


if __name__ == "__main__":
    main()