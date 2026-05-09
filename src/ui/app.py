
import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# ── Page configuration ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Lakehouse AI — Crypto & Stock Query Interface",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Configuration ──────────────────────────────────────────────────────────────
DEFAULT_FASTAPI_URL = "http://localhost:8000"

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🏗️ Lakehouse AI")
    st.markdown("Ask natural language questions about **live crypto and stock market data**.")
    st.divider()

    st.subheader("⚙️ Settings")
    api_url = st.text_input("FastAPI URL", value=DEFAULT_FASTAPI_URL)
    api_key = st.text_input("API Key", type="password", placeholder="Bearer token for /ask endpoint")
    show_sql = st.toggle("Show generated SQL", value=True)
    show_raw_data = st.toggle("Show raw query results", value=False)

    st.divider()
    st.subheader("💡 Example Questions")

    # Clicking an example button pre-fills the chat input
    example_questions = [
        "Which asset has the highest market cap?",
        "Compare total market cap of crypto vs stocks",
        "Which crypto had the biggest 24h price change?",
        "List the top 5 assets ranked by market cap",
        "Which stocks have a lower market cap than Bitcoin?",
        "What is the average price change across all assets?",
        "Show me all assets with a positive 24h price change",
        "Which asset has the highest trading volume today?",
    ]

    for i, q in enumerate(example_questions):
        if st.button(q, use_container_width=True, key=f"btn_{i}"):
            st.session_state["pending_question"] = q
            st.rerun()

    st.divider()

    # Clear conversation button
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state["messages"] = []
        st.session_state["pending_question"] = ""
        st.rerun()

    st.caption("Data refreshes hourly via AWS Lambda + EventBridge")

# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state["messages"] = []

if "pending_question" not in st.session_state:
    st.session_state["pending_question"] = ""

# ── Header ────────────────────────────────────────────────────────────────────
st.title("💬 Agentic Data Lakehouse")
st.caption(
    "Powered by GPT-4o-mini · PostgreSQL · dbt · AWS Lambda · "
    f"Last refreshed: check the `/health` endpoint"
)


# ── Shared helpers ────────────────────────────────────────────────────────────
def format_large_numbers(df: pd.DataFrame) -> pd.DataFrame:
    """Format billion/trillion numeric columns for readability."""
    df = df.copy()
    for col in df.columns:
        if df[col].dtype in ("float64", "int64"):
            if df[col].max() > 1e9:
                df[col] = df[col].apply(
                    lambda x: (
                        f"${x/1e12:.2f}T" if pd.notna(x) and x > 1e12
                        else f"${x/1e9:.1f}B" if pd.notna(x)
                        else x
                    )
                )
    return df


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


# ── API health check ──────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def check_health(url: str) -> int:
    try:
        return requests.get(f"{url}/health", timeout=3).status_code
    except requests.exceptions.ConnectionError:
        return 0


health_status = check_health(api_url)
if health_status == 200:
    st.success("✅ FastAPI server connected", icon="✅")
elif health_status == 0:
    st.error(
        "❌ Cannot connect to FastAPI server. "
        "Run `cd src/ai && uvicorn main:app --reload --port 8000` in a terminal."
    )
    st.stop()
else:
    st.error("⚠️ FastAPI server returned an error. Is uvicorn running?")

st.divider()

# ── Render conversation history ───────────────────────────────────────────────
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            st.markdown(f"**{msg['answer']}**")

            if show_sql and msg.get("sql"):
                with st.expander("🔍 Generated SQL", expanded=False):
                    st.code(msg["sql"], language="sql")

            if show_raw_data and msg.get("results"):
                with st.expander("📊 Raw query results", expanded=False):
                    try:
                        df = format_large_numbers(pd.DataFrame(msg["results"]))
                        st.dataframe(df, use_container_width=True)
                    except Exception:
                        st.json(msg["results"])

            if msg.get("timestamp"):
                st.caption(
                    f"🕐 {msg['timestamp']}  "
                    f"{'⏱️ ' + str(msg.get('response_time_ms', '')) + 'ms' if msg.get('response_time_ms') else ''}"
                )

# ── Chat input ────────────────────────────────────────────────────────────────
# Consume the pending question set by sidebar buttons
pending = st.session_state.get("pending_question", "")
if pending:
    st.session_state["pending_question"] = ""

user_input = st.chat_input("Ask a question about crypto and stock data...", key="chat_input")

question = user_input or pending

# ── Process the question ──────────────────────────────────────────────────────
if question:
    st.session_state["messages"].append({"role": "user", "content": question})

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Generating SQL and querying the database..."):
            start_time = datetime.now()
            try:
                response = requests.post(
                    f"{api_url}/ask",
                    json={"question": question},
                    headers=_auth_headers(),
                    timeout=30,
                )
                elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)

                if response.status_code == 200:
                    data = response.json()
                    answer = data.get("answer", "No answer returned.")
                    sql = data.get("sql", "")
                    results = data.get("rows", [])
                    timestamp = datetime.now().strftime("%H:%M:%S")

                    st.markdown(f"**{answer}**")

                    if show_sql and sql:
                        with st.expander("🔍 Generated SQL", expanded=False):
                            st.code(sql, language="sql")

                    if show_raw_data and results:
                        with st.expander("📊 Raw query results", expanded=False):
                            try:
                                df = format_large_numbers(pd.DataFrame(results))
                                st.dataframe(df, use_container_width=True)
                            except Exception:
                                st.json(results)

                    st.caption(f"🕐 {timestamp}  ⏱️ {elapsed_ms}ms")

                    st.session_state["messages"].append({
                        "role": "assistant",
                        "answer": answer,
                        "sql": sql,
                        "results": results,
                        "timestamp": timestamp,
                        "response_time_ms": elapsed_ms,
                    })

                else:
                    try:
                        error_detail = response.json().get("detail", response.text)
                    except Exception:
                        error_detail = response.text
                    st.error(f"API error ({response.status_code}): {error_detail}")

            except requests.exceptions.Timeout:
                st.error(
                    "Request timed out after 30 seconds. "
                    "The database might be unavailable or the query is too complex."
                )
            except requests.exceptions.ConnectionError:
                st.error(
                    "Lost connection to the FastAPI server. "
                    "Check that uvicorn is still running."
                )
            except Exception as e:
                st.error(f"Unexpected error: {e}")

    st.rerun()
