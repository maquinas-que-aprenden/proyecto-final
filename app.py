"""NormaBot — Streamlit UI con memoria conversacional.

Chat conversacional con el orquestador LangGraph.
Ejecutar: streamlit run app.py --server.port=8080
"""

import uuid

import streamlit as st

from src.orchestrator.main import run

st.set_page_config(page_title="NormaBot", page_icon="\u2696\ufe0f", layout="wide")

# --- Estado de sesion ---
if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "user_id" not in st.session_state:
    st.session_state.user_id = ""

# --- Sidebar ---
st.sidebar.title("NormaBot v0.2")
st.sidebar.markdown("Consulta normativa espa\u00f1ola + EU AI Act")
st.sidebar.markdown("---")

# Identificacion de usuario (opcional, sin autenticacion)
user_name = st.sidebar.text_input(
    "Tu nombre (opcional)",
    value=st.session_state.user_id,
    placeholder="Ej: maria_garcia",
    help="Identifica tu sesi\u00f3n para recordar preferencias entre conversaciones",
)
if user_name != st.session_state.user_id:
    st.session_state.user_id = user_name

# Boton nueva conversacion
if st.sidebar.button("Nueva conversaci\u00f3n", use_container_width=True):
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Agentes disponibles:**\n"
    "- RAG Normativo\n"
    "- Clasificador de Riesgo\n"
    "- Informes de Cumplimiento"
)

# Info de sesion
st.sidebar.caption(f"Sesi\u00f3n: {st.session_state.session_id[:8]}...")
if st.session_state.user_id:
    st.sidebar.caption(f"Usuario: {st.session_state.user_id}")

# --- Main ---
st.title("NormaBot")
st.caption("Asistente legal IA \u2014 EU AI Act, BOE, LOPD")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Escribe tu consulta legal..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Consultando agentes..."):
            result = run(
                prompt,
                session_id=st.session_state.session_id,
                user_id=st.session_state.user_id or None,
            )

        messages = result.get("messages", [])
        response = messages[-1].content if messages else "Sin respuesta."
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
