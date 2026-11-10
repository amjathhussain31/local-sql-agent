# tools/chart_builder.py
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.graph_objs import Figure

# Time-related column name keywords
_TIME_KEYS = {"date", "month", "year", "week", "quarter", "period", "time"}

# Month number → short name
_MONTH_NAMES = {
    1:"Jan", 2:"Feb", 3:"Mar", 4:"Apr", 5:"May", 6:"Jun",
    7:"Jul", 8:"Aug", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dec"
}


def _coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """
    PostgreSQL returns numeric columns as strings.
    Convert them to float so dtype checks work correctly.
    """
    for col in df.columns:
        try:
            converted = pd.to_numeric(df[col])
            df[col] = converted
        except (ValueError, TypeError):
            pass
    return df


def _is_time_col(col: str) -> bool:
    return any(kw in col.lower() for kw in _TIME_KEYS)


def _build_period_axis(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """
    When df has both 'year' and 'month' columns, combine them into a
    'period' string column (e.g. '2024-05') sorted chronologically.
    Returns (modified_df, x_col_name).
    """
    cols_lower = {c.lower(): c for c in df.columns}

    has_year  = "year"  in cols_lower
    has_month = "month" in cols_lower

    if has_year and has_month:
        yr_col = cols_lower["year"]
        mo_col = cols_lower["month"]

        df = df.copy()

        # Safe numeric conversion — drop rows with bad values
        df[yr_col] = pd.to_numeric(df[yr_col], errors="coerce")
        df[mo_col] = pd.to_numeric(df[mo_col], errors="coerce")
        df = df.dropna(subset=[yr_col, mo_col])
        df[yr_col] = df[yr_col].astype(int)
        df[mo_col] = df[mo_col].astype(int)

        df = df.sort_values([yr_col, mo_col]).reset_index(drop=True)

        df["period"] = (
            df[yr_col].astype(str) + "-"
            + df[mo_col].astype(str).str.zfill(2)
        )
        return df, "period"

    # Single month column (no year) — map to names and sort
    if has_month and not has_year:
        mo_col = cols_lower["month"]
        df = df.copy()
        df[mo_col] = pd.to_numeric(df[mo_col], errors="coerce")
        df = df.dropna(subset=[mo_col])
        df[mo_col] = df[mo_col].astype(int)
        df = df.sort_values(mo_col).reset_index(drop=True)
        df[mo_col] = df[mo_col].map(_MONTH_NAMES)
        return df, mo_col

    # Single year column (no month) — sort and stringify
    if has_year and not has_month:
        yr_col = cols_lower["year"]
        df = df.copy()
        df[yr_col] = pd.to_numeric(df[yr_col], errors="coerce")
        df = df.dropna(subset=[yr_col])
        df[yr_col] = df[yr_col].astype(int)
        df = df.sort_values(yr_col).reset_index(drop=True)
        df[yr_col] = df[yr_col].astype(str)
        return df, yr_col

    # Generic date/time column — use first match
    for col in df.columns:
        if _is_time_col(col):
            return df, col

    return df, df.columns[0]


def detect_chart_type(df: pd.DataFrame) -> str:
    if df.empty or len(df.columns) < 2:
        return "table"
    if len(df) == 1:
        return "table"

    df       = _coerce_numeric(df.copy())
    cols     = list(df.columns)
    num_cols = df.select_dtypes(include="number").columns.tolist()
    str_cols = df.select_dtypes(include="object").columns.tolist()
    n_rows   = len(df)

    # Any time keyword in column names → line chart
    for col in cols:
        if _is_time_col(col):
            return "line"

    # Bar — categorical + numeric, more than 2 rows
    if len(str_cols) >= 1 and len(num_cols) >= 1 and n_rows > 2:
        return "bar"

    # Pie — 2 or fewer categories
    if len(str_cols) == 1 and len(num_cols) == 1 and n_rows <= 2:
        return "pie"

    # Multiple numeric cols → scatter
    if len(num_cols) >= 3:
        return "scatter"

    # Single numeric
    if len(num_cols) == 1:
        return "histogram"

    return "table"


def build_chart(df: pd.DataFrame,
                title: str = "Query Results",
                chart_type: str = None) -> Figure:

    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(title="No data to display")
        return _style(fig)

    df       = _coerce_numeric(df.copy())
    cols     = list(df.columns)
    num_cols = df.select_dtypes(include="number").columns.tolist()
    str_cols = df.select_dtypes(include="object").columns.tolist()

    if chart_type is None:
        chart_type = detect_chart_type(df)

    try:
        # ── LINE ──────────────────────────────────────────────
        if chart_type == "line":
            df, x_col = _build_period_axis(df)

            # y = first numeric col that is NOT a time column and NOT x_col
            y_candidates = [c for c in df.select_dtypes(include="number").columns
                            if c != x_col and not _is_time_col(c)]
            if not y_candidates:
                # fallback: last column
                y_col = df.columns[-1]
            else:
                y_col = y_candidates[0]

            fig = px.line(
                df, x=x_col, y=y_col, title=title,
                markers=True,
                color_discrete_sequence=["#52a6ff"]
            )
            fig.update_xaxes(tickangle=-45)

        # ── BAR ───────────────────────────────────────────────
        elif chart_type == "bar":
            x_col = str_cols[0] if str_cols else cols[0]
            y_col = num_cols[0] if num_cols else cols[1]
            fig   = px.bar(
                df, x=x_col, y=y_col, title=title,
                color=x_col,
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            y_min = df[y_col].min()
            y_max = df[y_col].max()
            spread = y_max - y_min
            if spread > 0 and (spread / y_max) < 0.4:
                padding = spread * 0.3
                fig.update_yaxes(range=[max(0, y_min - padding), y_max + padding])
            else:
                fig.update_yaxes(rangemode="tozero")

        # ── PIE ───────────────────────────────────────────────
        elif chart_type == "pie":
            name_col  = str_cols[0] if str_cols else cols[0]
            value_col = num_cols[0] if num_cols else cols[1]
            fig       = px.pie(df, names=name_col, values=value_col, title=title)

        # ── SCATTER ───────────────────────────────────────────
        elif chart_type == "scatter":
            fig = px.scatter(
                df, x=num_cols[0], y=num_cols[1], title=title,
                color=str_cols[0] if str_cols else None
            )

        # ── HISTOGRAM ─────────────────────────────────────────
        elif chart_type == "histogram":
            fig = px.histogram(df, x=num_cols[0], title=title)

        # ── TABLE FALLBACK ────────────────────────────────────
        else:
            fig = go.Figure(data=[go.Table(
                header=dict(
                    values=cols,
                    fill_color="#1f6feb",
                    font=dict(color="white", size=12),
                    align="left"
                ),
                cells=dict(
                    values=[df[c].tolist() for c in cols],
                    fill_color="#161b22",
                    font=dict(color="#e6edf3", size=11),
                    align="left"
                )
            )])
            fig.update_layout(title=title)

        return _style(fig)

    except Exception as e:
        fig = go.Figure()
        fig.update_layout(title=f"Chart error: {str(e)}")
        return _style(fig)


def _style(fig: Figure) -> Figure:
    """Apply consistent dark theme styling to any figure."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(13,17,23,0.6)",
        font_color="#e8edf5",
        title_font_color="#e8edf5",
        title_font_size=14,
        margin=dict(l=20, r=20, t=44, b=20),
        height=380,
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color="#8b97b0", size=11)
        ),
        xaxis=dict(
            gridcolor="rgba(99,120,180,0.1)",
            tickfont=dict(color="#8b97b0", size=10),
        ),
        yaxis=dict(
            gridcolor="rgba(99,120,180,0.1)",
            tickfont=dict(color="#8b97b0", size=10),
        ),
    )
    return fig


def build_chart_from_string(data_json: str, title: str = "Results") -> str:
    """LangChain tool wrapper — returns status string to the agent."""
    try:
        data  = json.loads(data_json)
        df    = pd.DataFrame(data)
        df    = _coerce_numeric(df)
        ctype = detect_chart_type(df)
        return f"Chart ready: type={ctype}, rows={len(df)}, cols={list(df.columns)}"
    except Exception as e:
        return f"Chart error: {str(e)}"