"""tests/test_constants.py — Verifica la integridad de src/classifier/_constants.py.

Garantiza que las constantes compartidas tienen las claves y tipos correctos,
evitando regresiones silenciosas cuando se editan KEYWORDS_DOMINIO, RISK_LABELS
o LEAKAGE_COLUMNS.
"""

from src.classifier._constants import (
    KEYWORDS_DOMINIO,
    LEAKAGE_COLUMNS,
    PALABRAS_SUPERVISION,
    RISK_LABELS,
    STOPWORDS_ES,
)

# ── Etiquetas canónicas ───────────────────────────────────────────────────────

EXPECTED_RISK_KEYS = {"0", "1", "2", "3"}
EXPECTED_RISK_VALUES = {"inaceptable", "alto_riesgo", "riesgo_limitado", "riesgo_minimo"}


def test_risk_labels_keys():
    assert set(RISK_LABELS.keys()) == EXPECTED_RISK_KEYS


def test_risk_labels_values():
    assert set(RISK_LABELS.values()) == EXPECTED_RISK_VALUES


def test_risk_labels_no_abbreviated_forms():
    """Asegura que no se usen las formas abreviadas que causaron el bug E1."""
    abbreviated = {"alto", "limitado", "mínimo", "minimo"}
    assert not abbreviated & set(RISK_LABELS.values()), (
        "RISK_LABELS contiene etiquetas abreviadas. Usar formas canónicas: "
        "alto_riesgo, riesgo_limitado, riesgo_minimo."
    )


# ── Keywords de dominio ───────────────────────────────────────────────────────

EXPECTED_CLASSES = {"inaceptable", "alto_riesgo", "riesgo_limitado", "riesgo_minimo"}


def test_keywords_dominio_clases():
    assert set(KEYWORDS_DOMINIO.keys()) == EXPECTED_CLASSES


def test_keywords_dominio_no_vacias():
    for clase, keywords in KEYWORDS_DOMINIO.items():
        assert len(keywords) > 0, f"KEYWORDS_DOMINIO['{clase}'] está vacía"


def test_keywords_dominio_sin_duplicados_internos():
    for clase, keywords in KEYWORDS_DOMINIO.items():
        assert len(keywords) == len(set(keywords)), (
            f"KEYWORDS_DOMINIO['{clase}'] contiene duplicados: "
            f"{[kw for kw in keywords if keywords.count(kw) > 1]}"
        )


def test_keywords_dominio_clases_disjuntas():
    """Una misma keyword no debería aparecer en dos clases distintas."""
    seen: dict[str, str] = {}
    for clase, keywords in KEYWORDS_DOMINIO.items():
        for kw in keywords:
            if kw in seen:
                raise AssertionError(
                    f"Keyword '{kw}' aparece en '{seen[kw]}' y en '{clase}'. "
                    f"Elimina el duplicado para evitar features ambiguas."
                )
            seen[kw] = clase


# ── Palabras de supervisión ───────────────────────────────────────────────────

def test_palabras_supervision_no_vacia():
    assert len(PALABRAS_SUPERVISION) > 0


def test_palabras_supervision_es_lista():
    assert isinstance(PALABRAS_SUPERVISION, list)


# ── Stopwords ─────────────────────────────────────────────────────────────────

def test_stopwords_es_set():
    assert isinstance(STOPWORDS_ES, set)


def test_stopwords_minimas():
    # Artículos y preposiciones básicas deben estar siempre presentes
    minimas = {"de", "la", "el", "en", "con", "por", "para", "que"}
    assert minimas <= STOPWORDS_ES, f"Faltan stopwords básicas: {minimas - STOPWORDS_ES}"


# ── Columnas con leakage ──────────────────────────────────────────────────────

EXPECTED_LEAKAGE = {"violation", "severity", "ambiguity", "explanation", "split"}


def test_leakage_columns_contiene_criticas():
    assert EXPECTED_LEAKAGE <= set(LEAKAGE_COLUMNS), (
        f"Faltan columnas de leakage críticas: {EXPECTED_LEAKAGE - set(LEAKAGE_COLUMNS)}"
    )


def test_leakage_columns_es_frozenset():
    assert isinstance(LEAKAGE_COLUMNS, frozenset)


# ── Consistencia entre RISK_LABELS y KEYWORDS_DOMINIO ────────────────────────

def test_clases_sincronizadas():
    """Los valores de RISK_LABELS deben coincidir exactamente con las claves de KEYWORDS_DOMINIO."""
    assert set(RISK_LABELS.values()) == set(KEYWORDS_DOMINIO.keys()), (
        "RISK_LABELS y KEYWORDS_DOMINIO tienen clases distintas. "
        "Actualiza ambos cuando añadas/elimines una clase de riesgo."
    )
