#!/bin/bash
# Hook: Inyecta contexto del proyecto al inicio de sesión
# Se ejecuta en SessionStart para dar contexto inmediato a Claude

# Calcular días restantes hasta el 12 de marzo de 2026
DEADLINE="2026-03-12"
TODAY=$(date +%Y-%m-%d)
if command -v python3 &>/dev/null; then
  DAYS_LEFT=$(python3 -c "from datetime import date; print((date(2026,3,12) - date.today()).days)")
else
  DAYS_LEFT="?"
fi

# Contar componentes funcionales vs stubs
CWD=$(echo '{}' | jq -r '.cwd // empty' 2>/dev/null)
if [ -z "$CWD" ]; then
  CWD="."
fi

cat <<EOF
== NormaBot — Contexto de sesión ==
Proyecto final de bootcamp ML/IA. Deadline: 12 marzo 2026 ($DAYS_LEFT días restantes).
Equipo: Dani (Data+RAG), Rubén (ML+NLP), Maru (Agents+UI), Nati (MLOps).
Skills disponibles: /tutor, /diagnostico, /planificar, /progreso, /evaluar, /revisar.
Usa /tutor para orientación general o /diagnostico para auditar el estado del código.
Para ver el estado actual lee: NORMABOT_DIAGNOSIS.md, NORMABOT_PROGRESS.md, NORMABOT_ROADMAP.md.
EOF
