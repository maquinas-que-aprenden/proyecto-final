"""report/main.py — Agente de Informes de Cumplimiento
Hello world: simula generar un informe estructurado.
"""


def generate_report(system_desc: str, risk_level: str, articles: list[str]) -> str:
    # TODO: reemplazar con Groq LLM call + template
    citations = "\n".join(f"  - {a}" for a in articles)
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
3. Implementar supervisión humana (Art. 14)

### Disclaimer
*Informe preliminar generado por IA. Consulte profesional jurídico.*"""


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
