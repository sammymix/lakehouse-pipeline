
import streamlit as st
import requests
import json
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
# The FastAPI server must be running: uvicorn main:app --port 8000
FASTAPI_URL = "http://localhost:8000"

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🏗️ Lakehouse AI")
    st.markdown("Ask natural language questions about **live crypto and stock market data**.")
    st.divider()

    st.subheader("⚙️ Settings")
    show_sql = st.toggle("Show generated SQL", value=True)
    show_raw_data = st.toggle("Show raw query results", value=False)
    api_url = st.text_input("FastAPI URL", value=FASTAPI_URL)

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
# Streamlit re-runs the entire script on every interaction.
# session_state persists data across re-runs.
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

# ── API health check ──────────────────────────────────────────────────────────
try:
    health = requests.get(f"{api_url}/health", timeout=3)
    if health.status_code == 200:
        st.success("✅ FastAPI server connected", icon="✅")
    else:
        st.error("⚠️ FastAPI server returned an error. Is uvicorn running?")
except requests.exceptions.ConnectionError:
    st.error(
        "❌ Cannot connect to FastAPI server. "
        "Run `cd src/ai && uvicorn main:app --reload --port 8000` in a terminal."
    )
    st.stop()  # Do not render the chat if the API is unreachable

st.divider()

# ── Render conversation history ───────────────────────────────────────────────
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            # Assistant message — show the answer prominently
            st.markdown(f"**{msg['answer']}**")

            # Optionally show the generated SQL
            if show_sql and msg.get("sql"):
                with st.expander("🔍 Generated SQL", expanded=False):
                    st.code(msg["sql"], language="sql")

            # Optionally show the raw results as a table
            if show_raw_data and msg.get("results"):
                with st.expander("📊 Raw query results", expanded=False):
                    try:
                        df = pd.DataFrame(msg["results"])
                        # Format large numbers (market cap, volume) for readability
                        for col in df.columns:
                            if df[col].dtype == "float64" or df[col].dtype == "int64":
                                if df[col].max() > 1e9:
                                    df[col] = df[col].apply(
                                        lambda x: f"${x/1e12:.2f}T" if x > 1e12
                                        else f"${x/1e9:.1f}B"
                                    )
                        st.dataframe(df, use_container_width=True)
                    except Exception:
                        st.json(msg["results"])

            # Show metadata (timestamp, response time)
            if msg.get("timestamp"):
                st.caption(
                    f"🕐 {msg['timestamp']}  "
                    f"{'⏱️ ' + str(msg.get('response_time_ms', '')) + 'ms' if msg.get('response_time_ms') else ''}"
                )

# ── Chat input ────────────────────────────────────────────────────────────────
# Handle pre-filled question from sidebar button click
default_value = st.session_state.pop("pending_question", "")

user_input = st.chat_input(
    "Ask a question about crypto and stock data...",
    key="chat_input"
)

# Accept input from either the chat box or a sidebar button
question = user_input or default_value

# ── Process the question ──────────────────────────────────────────────────────
if question:
    # Add user message to conversation
    st.session_state["messages"].append({
        "role": "user",
        "content": question
    })

    # Show the user message immediately
    with st.chat_message("user"):
        st.markdown(question)

    # Call the FastAPI endpoint
    with st.chat_message("assistant"):
        with st.spinner("Generating SQL and querying the database..."):
            start_time = datetime.now()
            try:
                response = requests.post(
                    f"{api_url}/ask",
                    json={"question": question},
                    timeout=30
                )
                elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)

                if response.status_code == 200:
                    data = response.json()
                    answer = data.get("answer", "No answer returned.")
                    sql = data.get("sql", "")
                    results = data.get("rows", [])
                    timestamp = datetime.now().strftime("%H:%M:%S")

                    # Display the answer
                    st.markdown(f"**{answer}**")

                    # Show SQL if enabled
                    if show_sql and sql:
                        with st.expander("🔍 Generated SQL", expanded=False):
                            st.code(sql, language="sql")

                    # Show raw results if enabled
                    if show_raw_data and results:
                        with st.expander("📊 Raw query results", expanded=False):
                            try:
                                df = pd.DataFrame(results)
                                st.dataframe(df, use_container_width=True)
                            except Exception:
                                st.json(results)

                    st.caption(f"🕐 {timestamp}  ⏱️ {elapsed_ms}ms")

                    # Save assistant message to conversation history
                    st.session_state["messages"].append({
                        "role": "assistant",
                        "answer": answer,
                        "sql": sql,
                        "results": results,
                        "timestamp": timestamp,
                        "response_time_ms": elapsed_ms,
                    })

                else:
                    error_detail = response.json().get("detail", response.text)
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

    # Rerun to update the conversation display cleanly
    st.rerun()