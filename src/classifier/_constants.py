"""_constants.py — Constantes compartidas del clasificador EU AI Act.

Fuente única de verdad para keywords de dominio, stopwords y etiquetas canónicas.
Importar desde aquí en lugar de duplicar en functions.py, main.py y retrain.py.

Sin dependencias pesadas (solo builtins) para que retrain.py y main.py puedan
importar este módulo sin necesidad de spaCy, MLflow ni torch.
"""

# ── Etiquetas canónicas de riesgo (EU AI Act) ─────────────────────────────────
# Orden de severidad: 0=inaceptable (más grave) → 3=mínimo (menos grave)
RISK_LABELS: dict[str, str] = {
    "0": "inaceptable",
    "1": "alto_riesgo",
    "2": "riesgo_limitado",
    "3": "riesgo_minimo",
}

# ── Stopwords básicas en español (fallback sin spaCy) ─────────────────────────
STOPWORDS_ES: set[str] = {
    "a", "al", "algo", "algunas", "algunos", "ante", "antes", "como",
    "con", "contra", "cual", "cuando", "de", "del", "desde", "donde",
    "durante", "e", "el", "ella", "ellos", "en", "entre", "era", "es",
    "esa", "esas", "ese", "eso", "esos", "esta", "estas", "este", "esto",
    "estos", "fue", "ha", "han", "hasta", "hay", "he", "la", "las", "le",
    "les", "lo", "los", "me", "mi", "mis", "muy", "ni", "no", "nos",
    "o", "os", "otro", "para", "pero", "por", "que", "quien", "quienes",
    "se", "si", "sin", "sobre", "son", "su", "sus", "también", "tanto",
    "te", "todo", "todos", "tu", "tus", "un", "una", "unas", "uno",
    "unos", "ya", "yo",
}

# ── Keywords de dominio por nivel de riesgo (EU AI Act) ──────────────────────
# En forma lematizada (tal como spaCy las genera) para matching post-limpieza.
# Si se añade/elimina una keyword aquí se propaga automáticamente a training
# (functions.py / crear_features_manuales) e inferencia (main.py, retrain.py).
KEYWORDS_DOMINIO: dict[str, list[str]] = {
    # Sistemas prohibidos: biometría masiva en espacios públicos, venta de
    # datos sensibles, manipulación subconsciente, puntuación social,
    # categorización por etnia/religión/sindicato.
    "inaceptable": [
        "inferir", "vender", "manipular", "subconsciente", "biométrico",
        "facial", "vigilancia", "sindical", "racial", "etnia",
        "religioso", "discriminar", "coerción", "prohibido",
    ],
    # Anexo III EU AI Act: infraestructura crítica, acceso educativo/laboral,
    # servicios esenciales, aplicación ley, migración/asilo, justicia.
    "alto_riesgo": [
        "penitenciario", "juez", "reincidencia", "crediticio",
        "diagnóstico", "sanitario", "migración", "asilo",
        "policial", "empleabilidad", "infraestructura", "vinculante",
        "medicación", "autónomamente",
        "reclamación", "subsidio", "escolar", "triage",
        "urgencia", "aeronave", "piloto", "laboral",
        # Anexo III cat. 4 — selección de personal (CV screening)
        "curricular", "candidato", "reclutamiento", "curriculum",
        # Anexo III cat. 5 — servicios financieros esenciales
        "solvencia", "préstamo", "crédito", "hipoteca",
        # Anexo III cat. 6 — justicia penal
        "recidiva", "reincidente",
        # Anexo III cat. 7 — migración
        "frontera", "visado", "refugiado",
        # Anexo III cat. 8 — administración de justicia
        "sentencia", "judicial",
        # Anexo III cat. 3 — educación
        "admisión", "matriculación",
    ],
    # Obligaciones de transparencia: chatbots, deepfakes, contenido sintético.
    "riesgo_limitado": [
        "chatbot", "revelar", "transparencia", "deepfake",
        "sintético", "notificar", "asesoramiento", "asistente",
        "informar", "advertir", "indicar",
    ],
    # Sin obligaciones específicas: herramientas de sugerencia/asistencia,
    # juegos, spam, optimización industrial, IoT de mantenimiento.
    "riesgo_minimo": [
        "sugerir", "borrador", "juego", "spam", "entretenimiento",
        "filtro", "aficionado", "hobby", "receta",
        "avería", "maquinaria", "logística", "mantenimiento",
        "sensor", "industrial", "gestión",
    ],
}

# ── Palabras de supervisión humana ────────────────────────────────────────────
# Señal de alto_riesgo (no de inaceptable): los sistemas prohibidos no tienen
# supervisión humana posible porque el daño es el propósito mismo.
PALABRAS_SUPERVISION: list[str] = [
    "supervisión", "supervisar", "revisar", "revisión", "garantía",
    "confirmación", "criterio", "auditoría", "humano",
    "pediatra", "médico", "piloto", "pedagógico",
]

# ── Columnas con data leakage (nunca pasar a preparar_dataset) ────────────────
# Mapping 1-a-1 con la etiqueta o inexistentes en producción.
LEAKAGE_COLUMNS: frozenset[str] = frozenset({
    "violation",    # mapeo directo con la etiqueta
    "severity",     # mapeo directo con la etiqueta
    "ambiguity",    # 93% NULL, identifica riesgo_limitado al 100%
    "explanation",  # solo existe en etiquetado, no en producción
    "split",        # metadato del pipeline
})
