"""NormaBot — Streamlit UI

Chat conversacional con el orquestador LangGraph.
Ejecutar: streamlit run app.py --server.port=8080
"""

import logging
import re
import sys
import uuid

import streamlit as st

from src.orchestrator.main import run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)

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
        raw = messages[-1].content if messages else "Sin respuesta."
        response = re.sub(r"<thinking>.*?</thinking>", "", raw, flags=re.DOTALL).strip()
        st.markdown(response)


    st.session_state.messages.append({"role": "assistant", "content": response})
