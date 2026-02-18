"""NormaBot — Streamlit UI

Chat conversacional con el orquestador LangGraph.
Ejecutar: streamlit run app.py --server.port=8080
"""

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

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Escribe tu consulta legal..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Consultando agentes..."):
            result = run(prompt)

        response = result.get("response", "Sin respuesta.")
        st.markdown(response)

        sources = result.get("sources", [])
        if sources:
            with st.expander("Fuentes"):
                for s in sources:
                    st.markdown(
                        f"- Art. {s.get('articulo', '?')} {s.get('ley', '?')}"
                    )

        risk = result.get("risk_level", "")
        if risk:
            st.info(f"Nivel de riesgo: {risk}")

    st.session_state.messages.append({"role": "assistant", "content": response})
