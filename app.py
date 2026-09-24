from __future__ import annotations

import streamlit as st
import pandas as pd

from src.access import is_admin_email, is_logged_in, user_email
from src.run_agent import run_question

st.set_page_config(page_title="Pagila SQL Agent", page_icon="🧠", layout="wide")

if not is_logged_in(st.user):
    st.title("Pagila SQL Agent")
    st.write("Sign in to ask questions about the Pagila database.")
    st.button("Sign in with Google", on_click=st.login)
    st.stop()

email = user_email(st.user)
admin_user = is_admin_email(email)

st.markdown("<h1 style='margin-top: 0; margin-bottom: 10px;'>Pagila SQL Agent</h1>", unsafe_allow_html=True)
st.caption("Ask natural-language questions about the Pagila sample database and route uncertain SQL to review.")
st.caption(f"Signed in as {email or 'authenticated user'}")
st.button("Sign out", on_click=st.logout)

if "history" not in st.session_state:
    st.session_state.history = []

if "pending_result" not in st.session_state:
    st.session_state.pending_result = None

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

if "pending_thread_id" not in st.session_state:
    st.session_state.pending_thread_id = None


def submit_question(question: str):
    result = run_question(question, auto_approve=False)
    st.session_state.pending_question = question
    st.session_state.pending_result = result
    st.session_state.pending_thread_id = result.get("thread_id")


def resume_review(action: str, reason: str | None = None):
    if not st.session_state.pending_thread_id or not st.session_state.pending_question:
        return

    decision = {"action": action}
    if reason:
        decision["reason"] = reason

    result = run_question(
        st.session_state.pending_question,
        auto_approve=False,
        thread_id=st.session_state.pending_thread_id,
        decision=decision,
    )
    st.session_state.pending_result = result

with st.container():
    tabs = st.tabs(["Admin approval", "Ask question"])
    with tabs[0]:
        if not admin_user:
            st.info("Admin approval is restricted to configured reviewers.")
        elif st.session_state.pending_result and st.session_state.pending_result.get("status") == "needs_human":
            st.write("Human review flow is active when confidence is low or the SQL is uncertain.")
            result = st.session_state.pending_result
            st.warning("This query needs human review before execution.")
            st.code(result.get("generated_sql"), language="sql")
            st.write(f"Confidence: {result.get('confidence')}")
            st.write(f"Reasoning: {result.get('confidence_reasoning')}")

            review_reason = st.text_area(
                "Reason for rejection (optional)",
                key="review_reason",
                placeholder="Describe any issue with the generated SQL.",
                height=120,
            )

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Approve SQL", key="approve_sql"):
                    resume_review("approve")
            with col_b:
                if st.button("Reject SQL", key="reject_sql"):
                    resume_review("reject", review_reason)

        elif admin_user and st.session_state.pending_result:
            result = st.session_state.pending_result
            if result.get("final_answer"):
                st.success("Query executed successfully.")
                st.markdown(f"**Answer:**\n{result['final_answer']}")
            elif result.get("sql_error"):
                st.error(f"Query failed: {result['sql_error']}")
            else:
                st.info("No result available.")

            if result.get("confidence") is not None:
                st.write(f"Confidence: {result['confidence']}")
            if result.get("confidence_reasoning"):
                st.write(f"Reasoning: {result['confidence_reasoning']}")
            if result.get("generated_sql"):
                st.code(result["generated_sql"], language="sql")

            if result.get("execution_result"):
                rows = result["execution_result"]
                if rows:
                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.write("No rows returned.")
    with tabs[1]:
        pass

example_questions = [
    "Which 5 films were rented the most?",
    "What is the average rental duration by film category?",
    "Which customers have never returned a film?",
]

question = st.text_input("What would you like to know?", value=example_questions[0], key="question_input")

if st.button("Ask question", type="primary"):
    with st.spinner("Generating and checking SQL..."):
        submit_question(question)

    result = st.session_state.pending_result
    if result and result.get("status") == "needs_human":
        st.warning("This query needs human review before execution.")
        st.json({
            "generated_sql": result.get("generated_sql"),
            "confidence": result.get("confidence"),
            "reasoning": result.get("confidence_reasoning"),
        })
    elif result:
        if result.get("final_answer"):
            st.success("Query executed successfully.")
            st.markdown(f"**Answer:**\n{result['final_answer']}")
        elif result.get("sql_error"):
            st.error(f"Query failed: {result['sql_error']}")
        else:
            st.info("No result available.")

        if result.get("confidence") is not None:
            st.write(f"Confidence: {result['confidence']}")
        if result.get("confidence_reasoning"):
            st.write(f"Reasoning: {result['confidence_reasoning']}")
        if result.get("generated_sql"):
            st.code(result["generated_sql"], language="sql")

        if result.get("execution_result"):
            rows = result["execution_result"]
            if rows:
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True)
            else:
                st.write("No rows returned.")
