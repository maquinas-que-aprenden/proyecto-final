"""
create_normative_features.py

Enriquece el dataset de clasificación con features binarias derivadas del
Art. 5 del EU AI Act (prácticas prohibidas).

Cada feature detecta con regex si el texto describe una práctica explícitamente
prohibida. Estas features se concatenan al vector TF-IDF+SVD fuera de la
reducción de dimensionalidad, ya que son señales compactas e interpretables.

Uso:
    python src/classifier/create_normative_features.py
    python src/classifier/create_normative_features.py --input ruta/dataset.csv --output ruta/salida.csv

Columnas nuevas:
    contains_subliminal          — Art. 5.1.a: manipulación subliminal o engañosa
    contains_exploitation_vuln   — Art. 5.1.b: explotación de vulnerabilidades
    contains_social_scoring      — Art. 5.1.c: puntuación social ciudadana
    contains_real_time_biometric — Art. 5.1.d: biometría en tiempo real en espacios públicos
    contains_predictive_profiling— Art. 5.1.e: perfilado policial predictivo
    article_5_flag               — OR de todas las anteriores (señal de alto nivel)
"""

import argparse
import re
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Rutas por defecto
# ---------------------------------------------------------------------------
_BASE = Path(__file__).parent
_DEFAULT_INPUT = (
    _BASE
    / "classifier_dataset_fusionado"
    / "datasets"
    / "eu_ai_act_flagged_es_limpio.csv"
)
_DEFAULT_OUTPUT = (
    _BASE
    / "classifier_dataset_fusionado"
    / "datasets"
    / "eu_ai_act_flagged_normative_features.csv"
)

# ---------------------------------------------------------------------------
# Patrones regex — Art. 5 EU AI Act (prácticas prohibidas)
# Nota: se aplican sobre texto en minúsculas (str.lower())
# ---------------------------------------------------------------------------

# Art. 5.1.a — Manipulación subliminal o engañosa del comportamiento
PATTERN_SUBLIMINAL = re.compile(
    r"subliminal"
    r"|manipul\w+\s+(conduc|compor|decis)"
    r"|técnica[s]?\s+(engañosa|manipuladora)"
    r"|sin\s+consentimiento"
    r"|influenc\w+\s+(inconsciente|psicológi)"
    r"|engañ\w+\s+para\s+(modif|alterar|cambiar)"
)

# Art. 5.1.b — Explotación de vulnerabilidades (edad, discapacidad, situación)
PATTERN_EXPLOITATION_VULN = re.compile(
    r"(exploit|explot)\w*\s+(vulnerab|discapac|edad|minor)"
    r"|menor[es]?\s+de\s+edad"
    r"|discapacidad\s+(mental|cognitiva|física)"
    r"|situación\s+(económica\s+precaria|vulnerable|de\s+precariedad)"
    r"|personas\s+mayor[es]?\s+(vulnerab|depend|fragilidad)"
    r"|aprovech\w+\s+(discapacid|vulnerabilid)"
)

# Art. 5.1.c — Puntuación social ciudadana por autoridades públicas
PATTERN_SOCIAL_SCORING = re.compile(
    r"puntuación\s+social"
    r"|sistema[s]?\s+de\s+(crédito|scoring)\s+social"
    r"|clasificación\s+de\s+ciudadanos"
    r"|evaluación\s+de\s+comportamiento\s+(social|ciudadano)"
    r"|reputación\s+social\s+(general|global|ciudadana)"
    r"|ranking\s+(social|ciudadano)\s+(de\s+)?(conduct|comportamiento)"
)

# Art. 5.1.d — Identificación biométrica en tiempo real en espacios públicos
PATTERN_REAL_TIME_BIOMETRIC = re.compile(
    r"biométric\w+\s+en\s+tiempo\s+real"
    r"|reconocimiento\s+facial\s+(en\s+)?(vía|espacio)\s+público"
    r"|identificación\s+remota\s+en\s+(masa|tiempo\s+real)"
    r"|vigilancia\s+masiva\s+biométrica"
    r"|cámaras?\s+de\s+reconocimiento\s+facial\s+público"
    r"|detección\s+biométrica\s+masiva"
)

# Art. 5.1.e (post-AIA 2024) — Perfilado policial predictivo
PATTERN_PREDICTIVE_PROFILING = re.compile(
    r"predicción\s+(policial|criminal|delictiva)"
    r"|perfilado\s+(racial|étnico|conductual)\s+(policial|delictivo)"
    r"|riesgo\s+delictivo\s+(sin\s+indicio|preventivo)"
    r"|clasificación\s+de\s+(sospechosos?|delincuentes?)\s+potenciales?"
    r"|predicción\s+de\s+delitos?\s+futuros?"
    r"|perfil\s+de\s+riesgo\s+crim\w+"
)

PATTERNS = {
    "contains_subliminal": PATTERN_SUBLIMINAL,
    "contains_exploitation_vuln": PATTERN_EXPLOITATION_VULN,
    "contains_social_scoring": PATTERN_SOCIAL_SCORING,
    "contains_real_time_biometric": PATTERN_REAL_TIME_BIOMETRIC,
    "contains_predictive_profiling": PATTERN_PREDICTIVE_PROFILING,
}

FEATURE_COLS = list(PATTERNS.keys())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _apply_pattern(series: pd.Series, pattern: re.Pattern) -> pd.Series:
    """Devuelve serie binaria (0/1) indicando si el patrón aparece en cada texto.

    Espera una serie ya en minúsculas para evitar llamadas repetidas a str.lower().
    """
    return series.str.contains(pattern, regex=True, na=False).astype(int)


def add_normative_features(df: pd.DataFrame, text_col: str = "descripcion") -> pd.DataFrame:
    """
    Añade las 5 features del Art. 5 EU AI Act y el flag compuesto al DataFrame.

    Parámetros
    ----------
    df : DataFrame con al menos la columna `text_col`
    text_col : nombre de la columna con el texto a analizar

    Devuelve
    --------
    DataFrame original más las 6 columnas nuevas (in-place no aplicado).
    """
    if text_col not in df.columns:
        raise ValueError(
            f"Columna '{text_col}' no encontrada en el DataFrame. "
            f"Columnas disponibles: {list(df.columns)}"
        )
    df = df.copy()
    series_lower = df[text_col].fillna("").astype(str).str.lower()
    for col_name, pattern in PATTERNS.items():
        df[col_name] = _apply_pattern(series_lower, pattern)

    # Flag compuesto: 1 si cualquier práctica prohibida del Art. 5 se detecta
    df["article_5_flag"] = df[FEATURE_COLS].max(axis=1)

    return df


def verificar_discriminacion(df: pd.DataFrame, label_col: str = "etiqueta") -> None:
    """
    Imprime la activación media de cada feature por clase.
    Permite comprobar que las features discriminan principalmente 'inaceptable'.
    """
    cols = FEATURE_COLS + ["article_5_flag"]
    print("\n=== Activación media por clase (valores entre 0 y 1) ===")
    print(df.groupby(label_col)[cols].mean().round(3).to_string())
    print()

    # Alerta si alguna feature tiene activación alta en clases que no son inaceptable
    alertas = []
    for col in FEATURE_COLS:
        por_clase = df.groupby(label_col)[col].mean()
        no_inac = por_clase.drop("inaceptable", errors="ignore")
        if not no_inac.empty and no_inac.max() > 0.10:
            clase_alta = no_inac.idxmax()
            alertas.append(
                f"  ⚠️  '{col}': activación {no_inac.max():.0%} en '{clase_alta}'"
                " — considera afinar la regex"
            )

    if alertas:
        print("Alertas de posible regex demasiado amplia:")
        for a in alertas:
            print(a)
    else:
        print("✅ Todas las features discriminan principalmente 'inaceptable'.")


def mostrar_distribucion(df: pd.DataFrame, label_col: str = "etiqueta") -> None:
    """Muestra distribución de clases para detectar desbalanceo."""
    dist = df[label_col].value_counts(normalize=True).mul(100).round(1)
    print("\n=== Distribución de clases (%) ===")
    for label, pct in dist.items():
        aviso = " ← clase minoritaria, considera augmentación contrastiva" if pct < 10 else ""
        print(f"  {label:<20} {pct:>5.1f}%{aviso}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(input_path: Path, output_path: Path, text_col: str, label_col: str) -> None:
    # Paso 1 — Cargar dataset original (sin sobrescribir)
    print(f"Cargando dataset desde: {input_path}")
    df = pd.read_csv(input_path)
    print(f"  Filas: {len(df)} | Columnas: {list(df.columns)}")

    # Paso 2 — Generar columnas normativas
    print("\nGenerando features normativas (Art. 5 EU AI Act)...")
    df_enriquecido = add_normative_features(df, text_col=text_col)
    nuevas = FEATURE_COLS + ["article_5_flag"]
    print(f"  Columnas añadidas: {nuevas}")

    # Paso 3 — Verificar discriminación por clase
    if label_col in df_enriquecido.columns:
        verificar_discriminacion(df_enriquecido, label_col=label_col)
        mostrar_distribucion(df_enriquecido, label_col=label_col)
    else:
        print(f"\n⚠️  Columna '{label_col}' no encontrada, omitiendo verificación.")

    # Paso 4 — Guardar nuevo CSV enriquecido
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_enriquecido.to_csv(output_path, index=False)
    print(f"Dataset enriquecido guardado en: {output_path}")
    print(f"  Total columnas: {len(df_enriquecido.columns)} "
          f"(original: {len(df.columns)} + nuevas: {len(nuevas)})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Añade features normativas del Art. 5 EU AI Act al dataset del clasificador."
    )
    parser.add_argument(
        "--input", type=Path, default=_DEFAULT_INPUT,
        help="Ruta al CSV original (default: eu_ai_act_flagged_es_limpio.csv)"
    )
    parser.add_argument(
        "--output", type=Path, default=_DEFAULT_OUTPUT,
        help="Ruta del CSV de salida enriquecido"
    )
    parser.add_argument(
        "--text-col", default="descripcion",
        help="Columna de texto del dataset (default: descripcion)"
    )
    parser.add_argument(
        "--label-col", default="etiqueta",
        help="Columna de etiqueta del dataset (default: etiqueta)"
    )
    args = parser.parse_args()

    main(
        input_path=args.input,
        output_path=args.output,
        text_col=args.text_col,
        label_col=args.label_col,
    )
