"""report/main.py — Agente de Informes de Cumplimiento
Genera informes estructurados de cumplimiento EU AI Act usando Bedrock Nova Lite.
Fallback a template estático si el LLM no está disponible.
"""

from __future__ import annotations

import logging
import os

from langfuse.decorators import observe, langfuse_context

logger = logging.getLogger(__name__)

BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "eu.amazon.nova-lite-v1:0")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION") or os.environ.get("AWS_REGION", "eu-west-1")

REPORT_PROMPT = """\
Eres un asistente juridico especializado en el EU AI Act y normativa española de IA.
Genera un informe de cumplimiento estructurado en markdown para el sistema descrito.
Usa SOLO las citas legales proporcionadas y su contenido textual. No inventes articulos,
referencias ni contenido de articulos. Si no dispones de texto suficiente para una seccion,
indica "No se dispone de informacion suficiente en el corpus consultado".

Sistema: {system_desc}
Nivel de riesgo asignado: {risk_level}

Fragmentos legales recuperados (referencia + contenido textual):
{citations}

El informe debe incluir las siguientes secciones:
1. **Resumen Ejecutivo**: descripcion breve del sistema y su contexto regulatorio.
2. **Clasificacion de Riesgo**: nivel asignado con justificacion basada en las citas.
3. **Obligaciones Aplicables**: segun el nivel de riesgo, citando articulos concretos. Describe cada obligacion usando SOLO el contenido textual proporcionado arriba.
4. **Citas Legales**: listado de las referencias normativas utilizadas.
5. **Recomendaciones**: acciones concretas para cumplir con la normativa.

IMPORTANTE: No atribuyas contenido inventado a los articulos. Cada afirmacion sobre un
articulo debe basarse en el texto proporcionado en los fragmentos legales.

Responde en español. Se conciso y preciso."""

_report_llm = None


def _get_report_llm():
    """Devuelve el LLM para generacion de informes (Bedrock Nova Lite, singleton)."""
    global _report_llm
    if _report_llm is None:
        from langchain_aws import ChatBedrockConverse

        _report_llm = ChatBedrockConverse(
            model=BEDROCK_MODEL_ID,
            region_name=BEDROCK_REGION,
            temperature=0.2,
            max_tokens=2048,
        )
    return _report_llm


def _fallback_report(system_desc: str, risk_level: str, citations: str) -> str:
    """Template estático usado como fallback si Bedrock no está disponible."""
    return f"""## Informe de Cumplimiento — NormaBot

### Resumen Ejecutivo
El sistema "{system_desc}" está sujeto al EU AI Act por tratarse de un sistema de {risk_level}.

### Clasificación de Riesgo
Nivel: **{risk_level}**
Justificación: El sistema procesa datos sensibles en un contexto regulado.

### Obligaciones Aplicables
- Evaluación de conformidad (Art. 43)
- Sistema de gestión de riesgos (Art. 9)
- Gobernanza de datos (Art. 10)
- Documentación técnica (Art. 11)

### Citas Legales
{citations}

### Recomendaciones
1. Realizar evaluación de impacto
2. Documentar el sistema según Art. 11
3. Implementar supervisión humana (Art. 14)"""


@observe(name="report.generate")
def generate_report(system_desc: str, risk_level: str, articles: list[str]) -> str:
    """Genera un informe de cumplimiento usando Bedrock Nova Lite.

    Fallback a template estático si el LLM no está disponible.
    """
    citations = "\n".join(f"  - {a}" for a in articles) if articles else "  (sin citas disponibles)"

    grounded = True
    try:
        llm = _get_report_llm()
        prompt = REPORT_PROMPT.format(
            system_desc=system_desc,
            risk_level=risk_level,
            citations=citations,
        )
        response = llm.invoke(prompt)
        report = response.content.strip()
    except Exception as e:
        logger.warning("LLM de informes no disponible, usando fallback: %s", e)
        try:
            langfuse_context.update_current_observation(
                level="WARNING",
                status_message=f"Bedrock no disponible — informe con template estático: {e}",
            )
        except Exception:
            pass
        report = _fallback_report(system_desc, risk_level, citations)
        grounded = False

    report += "\n\n---\n*Informe preliminar generado por IA. Consulte profesional jurídico.*"

    try:
        langfuse_context.update_current_observation(
            metadata={
                "risk_level": risk_level,
                "n_articles": len(articles),
                "grounded": grounded,
                "model": BEDROCK_MODEL_ID,
                "report_length": len(report),
            }
        )
    except Exception:
        pass

    return report


if __name__ == "__main__":
    report = generate_report(
        system_desc="Scoring crediticio automático para préstamos",
        risk_level="Alto riesgo",
        articles=[
            "Art. 6 EU AI Act — Sistemas de alto riesgo",
            "Art. 9 EU AI Act — Gestión de riesgos",
            "Anexo III punto 5.b — Evaluación de solvencia",
        ],
    )
    print(report)
    print("\n✓ report/main.py OK")
