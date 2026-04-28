import streamlit as st

from src.agent import run_triage


st.set_page_config(page_title="MumzHelper", page_icon="🍼", layout="wide")
st.title("🍼 MumzHelper — Email Triage Agent")

email_text = st.text_area(
    "Paste customer email",
    height=220,
    placeholder="Paste the customer email here...",
)

if st.button("Triage Email", type="primary"):
    if not email_text.strip():
        st.warning("Please paste a customer email first.")
    else:
        try:
            with st.spinner("Triaging email..."):
                result = run_triage(email_text)
            st.subheader("Structured Output")
            st.json(result.model_dump())
        except Exception as exc:
            st.error(f"Something went wrong while triaging the email: {exc}")
