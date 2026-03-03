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


def _render_metadata(metadata: dict) -> None:
    """Renderiza datos verificados de las herramientas (side-channel).

    Estas citas y clasificaciones nunca pasaron por el LLM,
    por lo que son exactamente las que devolvieron las herramientas.
    """
    risk = metadata.get("risk")
    if risk:
        with st.expander("Clasificacion de riesgo (verificado)"):
            col1, col2 = st.columns(2)
            col1.metric("Nivel", risk["risk_level"].replace("_", " ").title())
            col2.metric("Confianza", f"{risk['confidence']:.0%}")
            st.markdown(f"**Ref. legal:** {risk['legal_ref']}")

    citations = metadata.get("citations", [])
    if citations:
        with st.expander(f"Fuentes legales verificadas ({len(citations)})"):
            for c in citations:
                unit = c.get("unit_title") or c.get("unit_id", "")
                label = f"{c.get('source', '')} - {unit}".strip(" -")
                if label:
                    st.markdown(f"- {label}")

# --- Sidebar ---
st.sidebar.title("NormaBot v0.1")
st.sidebar.markdown("Consulta normativa española + EU AI Act")
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Agentes disponibles:**\n"
    "- RAG Normativo\n"
    "- Clasificador de Riesgo + Checklist de Cumplimiento"
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
        if msg.get("metadata"):
            _render_metadata(msg["metadata"])

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

        metadata = result.get("metadata", {})
        if metadata:
            _render_metadata(metadata)

    st.session_state.messages.append({
        "role": "assistant",
        "content": response,
        "metadata": metadata,
    })
