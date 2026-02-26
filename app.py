"""NormaBot — Streamlit UI

Chat conversacional con el orquestador LangGraph.
Ejecutar: streamlit run app.py --server.port=8080
"""

import uuid

import streamlit as st

from src.orchestrator.main import run

st.set_page_config(page_title="NormaBot", page_icon="\u2696\ufe0f", layout="wide")

# --- Sidebar ---
st.sidebar.title("NormaBot v0.1")
st.sidebar.markdown("Consulta normativa española + EU AI Act")
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Agentes disponibles:**\n"
    "- RAG Normativo\n"
    "- Clasificador de Riesgo\n"
    "- Informes de Cumplimiento"
)

# --- Main ---
st.title("NormaBot")
st.caption("Asistente legal IA — EU AI Act, BOE, LOPD")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Escribe tu consulta legal..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Consultando agentes..."):
            result = run(prompt, session_id=st.session_state.session_id)

        messages = result.get("messages", [])
        response = messages[-1].content if messages else "Sin respuesta."
        st.markdown(response)

        trace_id = result.get("_langfuse_trace_id")
        if trace_id:
            col1, col2, _ = st.columns([1, 1, 8])
            with col1:
                if st.button("👍", key=f"up_{len(st.session_state.messages)}"):
                    try:
                        from langfuse import Langfuse
                        Langfuse().score(trace_id=trace_id, name="user_feedback", value=1)
                    except Exception:
                        pass
            with col2:
                if st.button("👎", key=f"down_{len(st.session_state.messages)}"):
                    try:
                        from langfuse import Langfuse
                        Langfuse().score(trace_id=trace_id, name="user_feedback", value=0)
                    except Exception:
                        pass

    st.session_state.messages.append({"role": "assistant", "content": response})
