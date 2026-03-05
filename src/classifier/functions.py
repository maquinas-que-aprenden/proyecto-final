import threading

from ._constants import (
    KEYWORDS_DOMINIO,
    LEAKAGE_COLUMNS as _LEAKAGE_COLUMNS,
    PALABRAS_SUPERVISION as _PALABRAS_SUPERVISION,
    STOPWORDS_ES as _STOPWORDS_ES,
)

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import Counter
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
    f1_score,
    roc_curve,
    auc,
)
from sklearn.preprocessing import label_binarize
from scipy.sparse import hstack
from scipy import sparse
import joblib
import os
import mlflow

# ──────────────────────────────────────────────
# Cargar .env al importar el módulo
# (Jupyter no propaga las vars del sistema al kernel automáticamente)
# ──────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=False)
except ImportError:
    pass  # python-dotenv no instalado; se leen las vars del sistema tal cual

# ──────────────────────────────────────────────
# Configuración MLflow
# ──────────────────────────────────────────────
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "")
MLFLOW_EXPERIMENT = "clasificador_riesgo_dataset_fusionado"

# Marca del dataset para MLflow
_DATASET_TAGS = {"dataset_type": "fusionado", "dataset_source": "eu_ai_act_flagged"}


def get_mlflow_password():
    """
    Obtiene la contraseña de MLflow desde:
    - Colab Secrets (si está en Colab)
    - Archivo .env en el directorio de trabajo (entorno local)
    - Variable de entorno del sistema (entorno local)
    """
    # Intentar obtener desde Colab
    try:
        from google.colab import userdata  # type: ignore[import]
        password = userdata.get("MLFLOW_PASSWORD")
        if password:
            print("Password obtenida desde Colab Secrets.")
            return password
    except ImportError:
        pass

    # El .env ya se cargó al importar el módulo; aquí solo leemos la variable.
    password = os.getenv("MLFLOW_PASSWORD")
    if password:
        print("Password obtenida desde variable de entorno local.")
        return password

    raise EnvironmentError(
        "No se encontró MLFLOW_PASSWORD.\n"
        "Opciones:\n"
        "  1. Crea un archivo .env en src/classifier/ con: MLFLOW_PASSWORD=tu_password\n"
        "  2. Define la variable de entorno y reinicia el kernel de Jupyter.\n"
        "  3. En Colab, configúrala en Colab Secrets."
    )


def configure_mlflow():
    """Configura las credenciales y la URI de seguimiento de MLflow."""
    if not MLFLOW_TRACKING_URI:
        raise EnvironmentError(
            "MLFLOW_TRACKING_URI no está configurada.\n"
            "Añádela al archivo .env: MLFLOW_TRACKING_URI=https://..."
        )

    password = get_mlflow_password()

    # TLS inseguro solo si se opta explícitamente (MLFLOW_ALLOW_INSECURE=true en .env).
    # Nunca se activa automáticamente para evitar exposición sin consentimiento.
    if os.getenv("MLFLOW_ALLOW_INSECURE") == "true":
        os.environ.setdefault("MLFLOW_TRACKING_INSECURE_TLS", "true")
    os.environ["MLFLOW_TRACKING_USERNAME"] = os.getenv("MLFLOW_TRACKING_USERNAME", "tracker")
    os.environ["MLFLOW_TRACKING_PASSWORD"] = password

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    print(f"MLflow configurado correctamente → {MLFLOW_TRACKING_URI}")

# ──────────────────────────────────────────────
# Pipelines de spaCy (carga diferida bajo demanda, thread-safe)
# ──────────────────────────────────────────────
_nlp = None
_nlp_ner = None
_spacy_available = None  # None = no comprobado aún
_spacy_lock = threading.Lock()  # protege la inicialización concurrente


def _check_spacy():
    """Comprueba si spaCy es importable y devuelve True/False."""
    global _spacy_available
    if _spacy_available is None:
        try:
            import spacy  # noqa: F401
            _spacy_available = True
        except Exception:
            _spacy_available = False
    return _spacy_available


def _get_nlp():
    global _nlp
    if not _check_spacy():
        return None
    if _nlp is None:
        with _spacy_lock:
            if _nlp is None:  # double-check tras adquirir el lock
                try:
                    import spacy
                    _nlp = spacy.load("es_core_news_sm", disable=["parser", "ner"])
                except Exception:
                    return None
    return _nlp


def _get_nlp_ner():
    global _nlp_ner
    if not _check_spacy():
        return None
    if _nlp_ner is None:
        with _spacy_lock:
            if _nlp_ner is None:  # double-check tras adquirir el lock
                try:
                    import spacy
                    _nlp_ner = spacy.load("es_core_news_sm")
                except Exception:
                    return None
    return _nlp_ner



def _limpiar_texto_fallback(texto, lemmatize=False):
    """Limpieza básica con regex cuando spaCy no está disponible."""
    import re
    import warnings
    if texto is None or (hasattr(texto, '__float__') and texto != texto):
        return ""
    texto = str(texto)
    if lemmatize:
        warnings.warn(
            "Lematización no disponible sin spaCy; se devuelve texto sin lematizar.",
            UserWarning,
            stacklevel=2,
        )
    tokens = re.findall(r'\b[a-záéíóúüñ]{3,}\b', texto.lower())
    return " ".join(t for t in tokens if t not in _STOPWORDS_ES)


# ══════════════════════════════════════════════
# 1. FUNCIONES DE LIMPIEZA DE TEXTO
# ══════════════════════════════════════════════

def limpiar_texto(texto, lemmatize=False):
    """
    Limpia el texto utilizando spaCy (si está disponible) o regex como fallback:
    - Convierte a minúsculas
    - Elimina puntuación, espacios y stop words
    - Opcionalmente lematiza las palabras (solo con spaCy).

    Parameters:
    texto : str
        El texto a limpiar.
    lemmatize : bool
        Si True, lematiza los tokens (por defecto False).

    Returns:
    str
        El texto limpio.
    """
    nlp = _get_nlp()
    if nlp is None or texto is None or (isinstance(texto, float) and texto != texto):
        return _limpiar_texto_fallback(texto, lemmatize)

    doc = nlp(str(texto).lower())
    tokens = [
        (token.lemma_ if lemmatize else token.text)
        for token in doc
        if not token.is_punct
        and not token.is_space
        and not token.is_stop
    ]
    return " ".join(tokens)


def limpiar_texto_preprocess(texto):
    """Alias mantenido por compatibilidad. Equivale a limpiar_texto(texto, lemmatize=True)."""
    return limpiar_texto(texto, lemmatize=True)


# ══════════════════════════════════════════════
# 2. FUNCIONES DE FEATURES MANUALES
# ══════════════════════════════════════════════

# KEYWORDS_DOMINIO y _PALABRAS_SUPERVISION importados desde _constants.py (ver cabecera del módulo).
# Palabras clave en forma lematizada; matching token-exacto sobre texto lematizado (kw in t.split()).


def crear_features_manuales(X_texts):
    """
    Genera features numéricas a partir de los textos lematizados.

    Features creadas:
    - num_palabras: número de palabras
    - num_caracteres: número de caracteres
    - kw_inaceptable: conteo de keywords de la clase inaceptable
    - kw_alto_riesgo: conteo de keywords de la clase alto_riesgo
    - kw_riesgo_limitado: conteo de keywords de la clase riesgo_limitado
    - kw_riesgo_minimo: conteo de keywords de la clase riesgo_minimo
    - kw_salvaguarda: conteo de palabras de supervisión/garantía humana
      (discrimina alto_riesgo vs inaceptable: en inaceptable el daño es
      el propósito y no hay supervisión posible; en alto_riesgo sí la hay)

    Parameters:
    X_texts : pd.Series con los textos lematizados.

    Returns:
    pd.DataFrame con las features numéricas.
    """
    features = pd.DataFrame()
    features["num_palabras"] = X_texts.apply(lambda t: len(t.split()))
    features["num_caracteres"] = X_texts.apply(len)

    for clase, keywords in KEYWORDS_DOMINIO.items():
        features[f"kw_{clase}"] = X_texts.apply(
            lambda t, kws=keywords: sum(1 for kw in kws if kw in t.split())
        )

    features["kw_salvaguarda"] = X_texts.apply(
        lambda t: sum(1 for kw in _PALABRAS_SUPERVISION if kw in t.split())
    )

    return features


def combinar_features(X_tfidf, X_manual):
    """
    Concatena la matriz TF-IDF (sparse) con las features manuales (dense).

    Parameters:
    X_tfidf : sparse matrix de TF-IDF.
    X_manual : pd.DataFrame con features numéricas.

    Returns:
    sparse matrix combinada.
    """
    X_manual_sparse = sparse.csr_matrix(X_manual.values)
    return hstack([X_tfidf, X_manual_sparse])


# ══════════════════════════════════════════════
# 3. FUNCIONES DE ANÁLISIS EXPLORATORIO (EDA)
# ══════════════════════════════════════════════

def analyze_text_length_distribution(df, text_column, label_column):
    """
    Calcula media y mediana de longitud de texto por clase
    y muestra un boxplot de distribución.
    """
    import seaborn as sns

    df = df.copy()
    df["char_count"] = df[text_column].apply(len)

    stats = df.groupby(label_column)["char_count"].agg(["mean", "median"])
    print("\nMedia y mediana de caracteres por clase:\n")
    print(stats)

    plt.figure(figsize=(10, 6))
    sns.boxplot(x=label_column, y="char_count", data=df)
    plt.title("Distribución de caracteres por clase")
    plt.xticks(rotation=45)
    plt.show()

    return stats


def top_ngrams(df, n=20, ngram=2, text_column="descripcion_limpia"):
    """
    Devuelve los n-grams más comunes en la columna indicada del
    DataFrame y muestra una gráfica de barras con su frecuencia.

    df: DataFrame con la columna de texto.
    n: Número de n-grams más comunes a devolver (por defecto 20).
    ngram: Tamaño del n-grama (por defecto 2 = bigramas).
    text_column: Nombre de la columna de texto (por defecto 'descripcion_limpia').
    return: Lista de tuplas (n-gram, frecuencia).
    """
    all_ngrams = []
    for review in df[text_column]:
        words = review.split()
        ngrams = zip(*[words[i:] for i in range(ngram)])
        ngrams = [' '.join(ng) for ng in ngrams]
        all_ngrams.extend(ngrams)

    ngram_counter = Counter(all_ngrams)
    ngram_most_common = ngram_counter.most_common(n)

    ngram_df = pd.DataFrame(ngram_most_common, columns=['ngram', 'frequency'])
    plt.figure(figsize=(10, 6))
    plt.barh(ngram_df['ngram'], ngram_df['frequency'], color='skyblue')
    plt.xlabel('Frecuencia')
    plt.ylabel(f'Top {n} {ngram}-grams')
    plt.title(f'Top {n} {ngram}-grams en el corpus')
    plt.gca().invert_yaxis()
    plt.show()

    return ngram_most_common


# ══════════════════════════════════════════════
# 3. FUNCIONES DE NER
# ══════════════════════════════════════════════

def extraer_entidades(df, text_column):
    """
    Extrae entidades nombradas (NER) de una columna de texto de un DataFrame
    usando spaCy con nlp.pipe para mayor eficiencia.

    Parameters:
    df : pandas.DataFrame
        El DataFrame que contiene los textos.
    text_column : str
        Nombre de la columna con el texto.

    Returns:
    pandas.DataFrame
        El DataFrame original con una nueva columna 'entidades' que contiene,
        para cada fila, una lista de diccionarios con las claves
        'texto', 'etiqueta' y 'descripcion'.
    """
    df = df.copy()
    textos = df[text_column].fillna("").astype(str).tolist()

    nlp_ner = _get_nlp_ner()
    if nlp_ner is None:
        df["entidades"] = [[] for _ in range(len(df))]
        df["ner_failed"] = True
        return df

    import spacy
    resultados = []
    for doc in nlp_ner.pipe(textos, batch_size=100):
        entidades = [
            {
                "texto": ent.text,
                "etiqueta": ent.label_,
                "descripcion": spacy.explain(ent.label_),
            }
            for ent in doc.ents
        ]
        resultados.append(entidades)

    df["entidades"] = resultados
    return df


def resumen_entidades(df):
    """
    Genera un resumen de las entidades NER extraídas: frecuencia por tipo
    de entidad y frecuencia por tipo de entidad y clase de riesgo.

    Parameters:
    df : pandas.DataFrame
        DataFrame con columnas 'entidades' (lista de dicts) y 'etiqueta'.

    Returns:
    tuple (freq_por_tipo, freq_por_tipo_clase)
        - freq_por_tipo: pd.Series con el conteo global por tipo de entidad.
        - freq_por_tipo_clase: pd.DataFrame con conteo por tipo y clase.
    """
    registros = []
    for _, row in df.iterrows():
        for ent in row["entidades"]:
            registros.append({
                "tipo_entidad": ent["etiqueta"],
                "texto_entidad": ent["texto"],
                "clase": row["etiqueta"],
            })

    if not registros:
        print("No se encontraron entidades en el dataset.")
        return pd.Series(dtype=int), pd.DataFrame()

    df_ents = pd.DataFrame(registros)

    freq_por_tipo = df_ents["tipo_entidad"].value_counts()
    print("Frecuencia global de entidades por tipo:")
    print(freq_por_tipo)
    print()

    freq_por_tipo_clase = df_ents.groupby(["clase", "tipo_entidad"]).size().unstack(fill_value=0)
    print("Frecuencia de entidades por tipo y clase de riesgo:")
    print(freq_por_tipo_clase)

    return freq_por_tipo, freq_por_tipo_clase


# ══════════════════════════════════════════════
# 4. FUNCIONES DE PREPROCESADO Y DIVISIÓN
# ══════════════════════════════════════════════

def preparar_dataset(df, text_column, label_column, extra_columns=None):
    """
    Prepara el dataset aplicando limpieza con lematización y añade
    opcionalmente features estructuradas seguras (sin leakage).

    Si 'articles' está presente en el DataFrame, calcula automáticamente
    la feature derivada 'num_articles' (número de artículos citados).

    Columnas con leakage que NUNCA deben incluirse en extra_columns:
      - violation, severity  → mapeo 1-a-1 con la etiqueta
      - ambiguity            → 93 % NULL, identifica riesgo_limitado al 100 %
      - explanation          → solo existe en etiquetado, no en producción
      - split                → metadato del pipeline

    Columnas seguras recomendadas:
      - category, context, longitud, num_articles

    Parameters
    ----------
    df : pd.DataFrame
    text_column : str
        Columna con el texto original (se lematiza para crear 'text_final').
    label_column : str
        Columna de etiquetas (target).
    extra_columns : list[str] | None
        Columnas adicionales a incluir en el output. 'num_articles' puede
        incluirse aunque no exista aún en df; se calcula internamente si
        la columna 'articles' está disponible.

    Returns
    -------
    pd.DataFrame con columnas ['text_final', label_column, *extra_columns].
    """
    import ast

    df = df.copy()
    df["text_final"] = df[text_column].fillna("").astype(str).apply(limpiar_texto_preprocess)

    # Calcular num_articles si la columna articles está presente
    if "articles" in df.columns:
        def _count_articles(val):
            try:
                return len(ast.literal_eval(str(val)))
            except Exception:
                return 0
        df["num_articles"] = df["articles"].apply(_count_articles)

    cols_output = ["text_final", label_column]
    if extra_columns:
        leakage_solicitadas = _LEAKAGE_COLUMNS & set(extra_columns)
        if leakage_solicitadas:
            raise ValueError(
                f"extra_columns contiene columnas con data leakage: {sorted(leakage_solicitadas)}. "
                f"Estas columnas tienen correspondencia directa con la etiqueta o no existen en "
                f"producción. Elimínalas de extra_columns."
            )
        for col in extra_columns:
            if col in df.columns and col not in cols_output:
                cols_output.append(col)
            elif col not in df.columns:
                print(f"  ⚠ Columna '{col}' no encontrada en el DataFrame, se omite.")

    return df[cols_output]


def split_dataset(df, label_column, test_size=0.15, val_size=0.15, random_state=42):
    """
    Divide el dataset en train, validation y test con estratificación.

    Parameters:
    df : pandas.DataFrame
        DataFrame con columnas 'text_final' y la columna de etiquetas.
    label_column : str
        Nombre de la columna de etiquetas.
    test_size : float
        Proporción del conjunto de test (por defecto 0.15).
    val_size : float
        Proporción del conjunto de validation (por defecto 0.15).
    random_state : int
        Semilla para reproducibilidad.

    Returns:
    tuple (train_df, val_df, test_df)
    """
    if test_size <= 0 or val_size <= 0:
        raise ValueError(
            f"test_size ({test_size}) y val_size ({val_size}) deben ser > 0."
        )
    if test_size + val_size >= 1.0:
        raise ValueError(
            f"test_size ({test_size}) + val_size ({val_size}) debe ser < 1.0 "
            f"para que queden muestras de entrenamiento."
        )

    # Separar features (todas las columnas menos la etiqueta) y target
    feature_cols = [c for c in df.columns if c != label_column]
    X = df[feature_cols]
    y = df[label_column]

    # Primera división: separar test
    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y,
        test_size=test_size,
        stratify=y,
        random_state=random_state,
    )

    # Segunda división: separar validation del resto
    # val_size relativo al conjunto temporal
    val_relative = val_size / (1 - test_size)
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp,
        test_size=val_relative,
        stratify=y_temp,
        random_state=random_state,
    )

    # Recombinar features + etiqueta preservando todas las columnas
    train_df = X_train.join(y_train)
    val_df = X_val.join(y_val)
    test_df = X_test.join(y_test)

    print(f"Train: {len(train_df)} muestras")
    print(f"Validation: {len(val_df)} muestras")
    print(f"Test: {len(test_df)} muestras")

    return train_df, val_df, test_df


# ══════════════════════════════════════════════
# 5. FUNCIONES DE ENTRENAMIENTO
# ══════════════════════════════════════════════

def crear_tfidf(X_train, X_val, X_test, max_features=5000, ngram_range=(1, 2), min_df=1):
    """
    Crea y ajusta un vectorizador TF-IDF sobre el conjunto de entrenamiento
    y transforma train, validation y test.

    Parameters:
    min_df : int
        Mínimo de documentos en los que debe aparecer un término para incluirse.
        Por defecto 1 (sin filtrado). Con max_features=5000 y este corpus, la
        cota de vocabulario es max_features, no min_df.

    Returns:
    tuple (tfidf, X_train_tfidf, X_val_tfidf, X_test_tfidf)
    """
    tfidf = TfidfVectorizer(
        max_features=max_features,
        ngram_range=ngram_range,
        sublinear_tf=True,
        min_df=min_df,
        token_pattern=r"(?u)\b[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]{3,}\b",
    )
    X_train_tfidf = tfidf.fit_transform(X_train)
    X_val_tfidf = tfidf.transform(X_val)
    X_test_tfidf = tfidf.transform(X_test)

    print(f"Vocabulario TF-IDF: {len(tfidf.vocabulary_)} términos")
    print(f"Forma train: {X_train_tfidf.shape}")
    print(f"Forma validation: {X_val_tfidf.shape}")
    print(f"Forma test: {X_test_tfidf.shape}")

    return tfidf, X_train_tfidf, X_val_tfidf, X_test_tfidf


def entrenar_modelo_baseline(X_train_tfidf, y_train, X_val_tfidf, y_val, class_weight=None):
    """
    Entrena un modelo LogisticRegression como baseline y muestra resultados
    sobre el conjunto de validación.

    Parameters:
    class_weight : str | dict | None
        Parámetro class_weight de LogisticRegression (e.g. 'balanced').
        Por defecto None (sin balanceo de clases).

    Returns:
    modelo : LogisticRegression entrenado
    """
    modelo = LogisticRegression(max_iter=2000, random_state=42, class_weight=class_weight)
    modelo.fit(X_train_tfidf, y_train)

    y_val_pred = modelo.predict(X_val_tfidf)

    print("=== Resultados en VALIDACIÓN ===\n")
    print(classification_report(y_val, y_val_pred))

    f1_macro = f1_score(y_val, y_val_pred, average="macro")
    print(f"F1-score macro (validación): {f1_macro:.4f}")

    return modelo


def entrenar_xgboost(X_train, y_train, X_val, y_val, params=None):
    """
    Entrena un XGBClassifier con los parámetros dados y evalúa en validación.

    Parameters:
    X_train : sparse matrix o array con features de entrenamiento.
    y_train : pd.Series con etiquetas de entrenamiento.
    X_val : sparse matrix o array con features de validación.
    y_val : pd.Series con etiquetas de validación.
    params : dict, hiperparámetros para XGBClassifier (opcional).

    Returns:
    tuple (modelo, label_encoder)
        - modelo: XGBClassifier entrenado.
        - label_encoder: LabelEncoder ajustado sobre y_train.
    """
    from xgboost import XGBClassifier
    from sklearn.preprocessing import LabelEncoder

    le = LabelEncoder()
    y_train_enc = le.fit_transform(y_train)

    default_params = {
        "n_estimators": 200,
        "max_depth": 5,
        "learning_rate": 0.1,
        "subsample": 0.8,
        "random_state": 42,
        "eval_metric": "mlogloss",
    }
    if params:
        default_params.update(params)

    from sklearn.utils.class_weight import compute_sample_weight
    sample_weight = compute_sample_weight(class_weight="balanced", y=y_train_enc)
    modelo = XGBClassifier(**default_params)
    modelo.fit(X_train, y_train_enc, sample_weight=sample_weight)

    y_val_pred_enc = modelo.predict(X_val)
    y_val_pred = le.inverse_transform(y_val_pred_enc)

    print("=== Resultados en VALIDACIÓN (XGBoost) ===\n")
    print(classification_report(y_val, y_val_pred))

    f1_macro = f1_score(y_val, y_val_pred, average="macro")
    print(f"F1-score macro (validación): {f1_macro:.4f}")

    # Exponemos el LabelEncoder como atributo público para predicciones posteriores
    modelo.label_encoder = le

    return modelo, le


def grid_search_cv(X_train, y_train, param_grid, cv=5):
    """
    Ejecuta Grid Search con StratifiedKFold sobre XGBClassifier.

    Parameters:
    X_train : sparse matrix o array con features de entrenamiento.
    y_train : pd.Series con etiquetas de entrenamiento.
    param_grid : dict, grid de hiperparámetros a explorar.
    cv : int, número de folds para cross-validation (por defecto 5).

    Returns:
    tuple (best_model, best_params, cv_results, label_encoder)
        - best_model: XGBClassifier con los mejores hiperparámetros.
        - best_params: dict con los mejores parámetros.
        - cv_results: pd.DataFrame con los resultados del Grid Search.
        - label_encoder: LabelEncoder ajustado sobre y_train.
    """
    from xgboost import XGBClassifier
    from sklearn.model_selection import GridSearchCV, StratifiedKFold
    from sklearn.preprocessing import LabelEncoder

    le = LabelEncoder()
    y_train_enc = le.fit_transform(y_train)

    base_model = XGBClassifier(
        random_state=42,
        eval_metric="mlogloss",
    )

    skf = StratifiedKFold(n_splits=cv, shuffle=True, random_state=42)

    grid = GridSearchCV(
        estimator=base_model,
        param_grid=param_grid,
        cv=skf,
        scoring="f1_macro",
        n_jobs=-1,
        verbose=1,
        refit=True,
    )

    from sklearn.utils.class_weight import compute_sample_weight
    sample_weight = compute_sample_weight(class_weight="balanced", y=y_train_enc)
    grid.fit(X_train, y_train_enc, sample_weight=sample_weight)

    print(f"\n=== Resultados Grid Search ({cv}-fold CV) ===")
    print(f"Mejor F1-macro CV: {grid.best_score_:.4f}")
    print(f"Mejores parámetros: {grid.best_params_}")

    best_model = grid.best_estimator_
    best_model.label_encoder = le

    cv_results = pd.DataFrame(grid.cv_results_).sort_values("rank_test_score")

    return best_model, grid.best_params_, cv_results, le


def guardar_artefactos(modelo, tfidf, output_dir):
    """
    Guarda el modelo entrenado y el vectorizador TF-IDF con joblib.

    Parameters:
    modelo : modelo entrenado de sklearn.
    tfidf : TfidfVectorizer ajustado.
    output_dir : str, ruta de la carpeta donde guardar los artefactos.
    """
    os.makedirs(output_dir, exist_ok=True)

    path_modelo = os.path.join(output_dir, "modelo_clasificador.joblib")
    path_tfidf = os.path.join(output_dir, "tfidf_vectorizer.joblib")

    joblib.dump(modelo, path_modelo)
    joblib.dump(tfidf, path_tfidf)

    print(f"Modelo guardado en: {path_modelo}")
    print(f"Vectorizador guardado en: {path_tfidf}")


def cargar_artefactos(model_dir):
    """
    Carga el modelo y el vectorizador TF-IDF desde disco.

    Returns:
    tuple (modelo, tfidf)
    """
    modelo = joblib.load(os.path.join(model_dir, "modelo_clasificador.joblib"))
    tfidf = joblib.load(os.path.join(model_dir, "tfidf_vectorizer.joblib"))
    print("Modelo y vectorizador cargados correctamente.")
    return modelo, tfidf


# ══════════════════════════════════════════════
# 6. FUNCIONES DE MÉTRICAS Y EVALUACIÓN
# ══════════════════════════════════════════════

def evaluar_modelo(modelo, X_test, y_test):
    """
    Evalúa el modelo sobre el conjunto de test y muestra:
    - Classification report
    - F1-score macro

    Parameters:
    modelo : modelo sklearn entrenado.
    X_test : sparse matrix o array — features de test ya transformadas
             (TF-IDF, TF-IDF + OHE + numéricas, o cualquier pipeline).
             El notebook es responsable de construir esta matriz antes de llamar.
    y_test : pd.Series con las etiquetas reales.

    Returns:
    tuple (y_pred, report_dict)
    """
    y_pred = modelo.predict(X_test)
    if hasattr(modelo, "label_encoder"):
        y_pred = modelo.label_encoder.inverse_transform(y_pred)

    print("=== Resultados en TEST ===\n")
    report_dict = classification_report(y_test, y_pred, output_dict=True)
    print(classification_report(y_test, y_pred))

    f1_macro = report_dict["macro avg"]["f1-score"]
    print(f"F1-score macro (test): {f1_macro:.4f}\n")

    return y_pred, report_dict


def mostrar_matriz_confusion(y_test, y_pred, labels=None):
    """
    Muestra la matriz de confusión como gráfico.

    Returns:
    fig : matplotlib.figure.Figure
    """
    cm = confusion_matrix(y_test, y_pred, labels=labels)
    fig, ax = plt.subplots(figsize=(8, 6))
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=labels)
    disp.plot(ax=ax, cmap="Blues", values_format="d")
    ax.set_title("Matriz de confusión")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.show()
    return fig


def plot_curva_roc_multiclase(modelo, X_test, y_test):
    """
    Genera la curva ROC multiclase (One-vs-Rest) para el modelo.

    Parameters:
    modelo : modelo entrenado con predict_proba.
    X_test : sparse matrix o array — features de test ya transformadas.
             El notebook es responsable de construir esta matriz antes de llamar.
    y_test : pd.Series con las etiquetas reales.

    Returns:
    fig : matplotlib.figure.Figure
    roc_auc_dict : dict con el AUC por clase.
    """
    if hasattr(modelo, "label_encoder"):
        clases = list(modelo.label_encoder.classes_)
        y_test_int = modelo.label_encoder.transform(y_test)
        y_test_bin = label_binarize(y_test_int, classes=list(range(len(clases))))
    else:
        clases = sorted(modelo.classes_)
        y_test_bin = label_binarize(y_test, classes=clases)
    y_proba = modelo.predict_proba(X_test)

    fig, ax = plt.subplots(figsize=(10, 7))
    roc_auc_dict = {}

    for i, clase in enumerate(clases):
        fpr, tpr, _ = roc_curve(y_test_bin[:, i], y_proba[:, i])
        roc_auc_val = auc(fpr, tpr)
        roc_auc_dict[clase] = roc_auc_val
        ax.plot(fpr, tpr, label=f"{clase} (AUC = {roc_auc_val:.2f})")

    ax.plot([0, 1], [0, 1], "k--", label="Azar")
    ax.set_xlabel("Tasa de falsos positivos")
    ax.set_ylabel("Tasa de verdaderos positivos")
    ax.set_title("Curva ROC multiclase (One-vs-Rest)")
    ax.legend(loc="lower right")
    plt.tight_layout()
    plt.show()

    roc_auc_macro = np.mean(list(roc_auc_dict.values()))
    print(f"\nROC AUC macro: {roc_auc_macro:.4f}")
    for clase, val in roc_auc_dict.items():
        print(f"  {clase}: {val:.4f}")

    return fig, roc_auc_dict


def generar_resumen_metricas(y_test, y_pred, modelo, X_test, metrics_dict,
                             class_names=None, output_dir="model/plots",
                             filename="resumen_metricas.png"):
    """
    Genera una figura resumen con las métricas clave del modelo en un único gráfico:
    - Matriz de confusión
    - Métricas principales (F1-macro, Accuracy, ROC-AUC) en barras horizontales
    - Curvas ROC multiclase (One-vs-Rest)

    Útil para loguear en MLflow como artefacto único en lugar de imágenes dispersas.

    Parameters:
    y_test       : pd.Series — etiquetas reales de test.
    y_pred       : array — predicciones del modelo.
    modelo       : modelo sklearn con predict_proba.
    X_test       : sparse matrix o array — features de test ya transformadas.
    metrics_dict : dict con claves "f1_macro", "accuracy", "roc_auc".
    class_names  : list de str — nombres de clases. Si None, se infiere de y_test.
    output_dir   : str — carpeta donde guardar la figura.
    filename     : str — nombre del archivo PNG.

    Returns:
    str — ruta completa al archivo guardado.
    """
    os.makedirs(output_dir, exist_ok=True)

    if class_names is None:
        class_names = sorted(y_test.unique())

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle("Resumen de Métricas del Modelo", fontsize=14, fontweight="bold")

    # 1. Matriz de confusión
    cm = confusion_matrix(y_test, y_pred, labels=class_names)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=class_names)
    disp.plot(ax=axes[0], cmap="Blues", values_format="d", colorbar=False)
    axes[0].set_title("Matriz de Confusión")
    axes[0].tick_params(axis="x", rotation=45)

    # 2. Métricas principales en barras horizontales
    metric_labels = ["F1-macro", "Accuracy", "ROC-AUC"]
    metric_values = [
        metrics_dict.get("f1_macro", 0),
        metrics_dict.get("accuracy", 0),
        metrics_dict.get("roc_auc", 0),
    ]
    colors = ["#2196F3", "#4CAF50", "#FF9800"]
    bars = axes[1].barh(metric_labels, metric_values, color=colors)
    axes[1].set_xlim(0, 1.1)
    axes[1].set_title("Métricas Principales")
    for bar, val in zip(bars, metric_values):
        axes[1].text(
            bar.get_width() + 0.01, bar.get_y() + bar.get_height() / 2,
            f"{val:.3f}", va="center", fontsize=11,
        )

    # 3. Curvas ROC multiclase (One-vs-Rest)
    y_test_bin = label_binarize(y_test, classes=class_names)
    y_proba = modelo.predict_proba(X_test)
    for i, cls in enumerate(class_names):
        fpr, tpr, _ = roc_curve(y_test_bin[:, i], y_proba[:, i])
        roc_auc_val = auc(fpr, tpr)
        axes[2].plot(fpr, tpr, label=f"{cls} (AUC={roc_auc_val:.2f})")
    axes[2].plot([0, 1], [0, 1], "k--", alpha=0.5, label="Azar")
    axes[2].set_title("Curvas ROC (OvR)")
    axes[2].set_xlabel("Tasa de falsos positivos")
    axes[2].set_ylabel("Tasa de verdaderos positivos")
    axes[2].legend(fontsize=8, loc="lower right")

    plt.tight_layout()
    path = os.path.join(output_dir, filename)
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.show()
    plt.close()

    print(f"Resumen de métricas guardado: {path}")
    return path


def analisis_errores(modelo, X_test_features, y_test, X_test_text=None):
    """
    Muestra los ejemplos mal clasificados para analizar patrones de error.

    Parameters:
    modelo          : modelo sklearn entrenado.
    X_test_features : sparse matrix o array — features de test ya transformadas.
                      El notebook es responsable de construir esta matriz antes de llamar.
    y_test          : pd.Series con las etiquetas reales.
    X_test_text     : pd.Series con el texto original (opcional).
                      Si se pasa, se muestra en los ejemplos de error.

    Returns:
    df_errores : pd.DataFrame con las predicciones incorrectas.
    """
    import warnings

    y_pred = modelo.predict(X_test_features)
    if hasattr(modelo, "label_encoder"):
        y_pred = modelo.label_encoder.inverse_transform(y_pred)

    if X_test_text is None:
        warnings.warn(
            "analisis_errores llamado sin X_test_text: los ejemplos de error se mostrarán "
            "sin texto original. Pasa X_test_text=X_test['text_final'] para análisis completo.",
            stacklevel=2,
        )
    textos = X_test_text.values if X_test_text is not None else ["[texto no disponible]"] * len(y_test)
    df_resultado = pd.DataFrame({
        "texto": textos,
        "etiqueta_real": y_test.values,
        "etiqueta_predicha": y_pred,
    })

    df_errores = df_resultado[df_resultado["etiqueta_real"] != df_resultado["etiqueta_predicha"]]

    if df_errores.empty:
        print("No hay errores de clasificación en el conjunto de test.")
    else:
        print(f"Total de errores: {len(df_errores)} de {len(df_resultado)} "
              f"({len(df_errores)/len(df_resultado)*100:.1f}%)\n")
        print("Confusiones más frecuentes:")
        confusiones = df_errores.groupby(
            ["etiqueta_real", "etiqueta_predicha"]
        ).size().sort_values(ascending=False)
        print(confusiones)
        print("\nEjemplos mal clasificados:")
        for _, row in df_errores.iterrows():
            print(f"  Real: {row['etiqueta_real']} | Predicho: {row['etiqueta_predicha']}")
            print(f"  Texto: {row['texto'][:120]}...")
            print()

    return df_errores


# ══════════════════════════════════════════════
# 7. MLFLOW — HELPER SEGURO
# ══════════════════════════════════════════════

def log_mlflow_safe(run_name, params=None, metrics=None, artifacts=None, tags=None,
                    datasets=None, models=None):
    """
    Registra un experimento en MLflow de forma centralizada.

    Diseñado para ser la única llamada dentro del bloque try/except de la
    última celda de cada notebook, de modo que solo esa celda falle si el
    servidor no está disponible.

    Parameters:
    run_name  : str  — nombre del run en MLflow.
    params    : dict — hiperparámetros / configuración a loguear.
    metrics   : dict — métricas numéricas a loguear.
    artifacts : list — rutas de ficheros locales a subir como artefactos.
                       Acepta strings simples o tuplas (path, subfolder) para
                       organizar en subcarpetas de la UI de MLflow.
                       Ejemplo: [
                           "model/resumen_metricas.png",                        # raíz
                           ("model/plots/shap/beeswarm.png", "plots/shap"),     # subcarpeta
                       ]
    tags      : dict — etiquetas adicionales del run.
    datasets  : list — lista de tuplas (df, context, name) para registrar datasets.
                       context: "training", "test" o "validation".
                       Ejemplo: [(df_train, "training", "fusionado_train"),
                                 (df_test,  "test",     "fusionado_test")]
    models    : list — lista de dicts para loguear modelos sklearn con mlflow.sklearn.
                       Claves: "model" (requerido), "artifact_path" (default "model"),
                       "signature" (opcional), "input_example" (opcional),
                       "registered_name" (opcional) — si se indica, registra el modelo
                       en el Model Registry (pestaña Models de la UI).
                       Ejemplo:
                       [
                           {
                               "model": clf,
                               "artifact_path": "classifier",
                               "signature": infer_signature(X_train, clf.predict(X_train)),
                               "input_example": X_train[:3],
                               "registered_name": "normabot-classifier",  # → aparece en Models
                           },
                           {"model": tfidf, "artifact_path": "tfidf_vectorizer"},
                       ]
    """
    configure_mlflow()
    mlflow.set_experiment(MLFLOW_EXPERIMENT)

    _all_tags = {**_DATASET_TAGS, **(tags or {})}

    with mlflow.start_run(run_name=run_name) as run:
        if params:
            mlflow.log_params(params)
        if metrics:
            mlflow.log_metrics(metrics)
        if artifacts:
            for item in artifacts:
                if isinstance(item, (list, tuple)):
                    path, artifact_subdir = item
                    mlflow.log_artifact(path, artifact_path=artifact_subdir)
                else:
                    mlflow.log_artifact(item)
        if datasets:
            for df, context, name in datasets:
                dataset = mlflow.data.from_pandas(df, name=name)
                mlflow.log_input(dataset, context=context)
        if models:
            for model_entry in models:
                artifact_path = model_entry.get("artifact_path", "model")
                mlflow.sklearn.log_model(
                    sk_model=model_entry["model"],
                    artifact_path=artifact_path,
                    signature=model_entry.get("signature"),
                    input_example=model_entry.get("input_example"),
                )
                registered_name = model_entry.get("registered_name")
                if registered_name:
                    model_uri = f"runs:/{run.info.run_id}/{artifact_path}"
                    mlflow.register_model(model_uri, registered_name)
        mlflow.set_tags(_all_tags)

    print(f"✓ Run '{run_name}' registrado en MLflow ({MLFLOW_TRACKING_URI})")


# ══════════════════════════════════════════════
# 8. SHAP — EXPLICABILIDAD
# ══════════════════════════════════════════════

_MAX_DENSE_ELEMENTS = 50_000_000  # ~400 MB en float64; ajustable según entorno


def _sparse_to_dense_safe(X, label="X", max_elements=_MAX_DENSE_ELEMENTS):
    """
    Convierte una matriz sparse a densa solo si no supera el umbral de memoria.
    Si lo supera, hace un muestreo aleatorio de filas antes de convertir y emite
    una advertencia.
    """
    import warnings
    import numpy as np

    if not hasattr(X, "toarray"):
        return X

    n_rows, n_cols = X.shape
    n_elements = n_rows * n_cols

    if n_elements > max_elements:
        max_rows = max(1, max_elements // n_cols)
        warnings.warn(
            f"[SHAP] {label} tiene {n_elements:,} elementos ({n_rows}×{n_cols}), "
            f"supera el umbral de {max_elements:,}. "
            f"Se muestrean {max_rows} filas aleatorias para evitar OOM.",
            UserWarning,
            stacklevel=3,
        )
        idx = np.random.choice(n_rows, size=max_rows, replace=False)
        X = X[idx]

    return X.toarray()


def explicar_con_shap(modelo, X_background, X_explain):
    """
    Calcula valores SHAP para el modelo dado.

    - LogisticRegression → shap.LinearExplainer (admite matrices sparse)
    - XGBClassifier      → shap.TreeExplainer   (convierte a denso internamente)

    Parameters:
    modelo       : modelo sklearn/xgboost entrenado.
    X_background : sparse matrix o array — datos de referencia para el explainer.
    X_explain    : sparse matrix o array — muestras a explicar.

    Returns:
    tuple (explainer, shap_values)
        shap_values es una lista de arrays (n_samples, n_features), uno por clase.
    """
    import shap
    import numpy as np
    from sklearn.linear_model import LogisticRegression

    if isinstance(modelo, LogisticRegression):
        explainer = shap.LinearExplainer(modelo, X_background)
        shap_values = explainer.shap_values(X_explain)
    else:
        # XGBoost u otro modelo de árbol — necesita arrays densos
        X_bg = _sparse_to_dense_safe(X_background, label="X_background")
        X_ex = _sparse_to_dense_safe(X_explain, label="X_explain")
        explainer = shap.TreeExplainer(modelo, X_bg)
        shap_values = explainer.shap_values(X_ex)

    # Normalizar a lista de arrays 2D (n_samples, n_features), uno por clase.
    # SHAP >= 0.46 puede devolver un ndarray 3D en lugar de lista.
    n_samples = X_explain.shape[0]
    if isinstance(shap_values, np.ndarray):
        if shap_values.ndim == 3:
            if shap_values.shape[0] == n_samples:
                # formato (n_samples, n_features, n_classes)
                shap_values = [shap_values[:, :, i] for i in range(shap_values.shape[2])]
            else:
                # formato (n_classes, n_samples, n_features)
                shap_values = [shap_values[i] for i in range(shap_values.shape[0])]
        else:
            shap_values = [shap_values]
    elif not isinstance(shap_values, list):
        shap_values = [shap_values]

    n_clases = len(shap_values)
    print(f"SHAP calculado: {n_clases} clases, {n_samples} muestras")
    return explainer, shap_values


def plot_shap_summary(shap_values, X_explain, feature_names, class_names, output_dir, max_display=20):
    """
    Genera y guarda los plots SHAP de resumen:
    - Un beeswarm por clase (top features más influyentes).
    - Un bar plot global con la importancia media por clase.

    Parameters:
    shap_values   : lista de arrays SHAP (uno por clase).
    X_explain     : sparse matrix o array con las muestras explicadas.
    feature_names : list de str con los nombres de las features.
    class_names   : list de str con los nombres de las clases.
    output_dir    : str — carpeta donde guardar los plots.
    max_display   : int — número máximo de features a mostrar (default 20).

    Returns:
    saved_paths : list de rutas de los archivos guardados.
    """
    import shap
    import numpy as np

    os.makedirs(output_dir, exist_ok=True)
    X_dense = X_explain.toarray() if hasattr(X_explain, "toarray") else X_explain
    feature_names = np.array(feature_names)  # SHAP indexa con arrays numpy
    saved_paths = []

    # Normalizar shap_values a lista de arrays 2D (n_samples, n_features), uno por clase.
    # SHAP >= 0.46 puede devolver ndarray 3D o lista; hay que manejar ambos.
    if isinstance(shap_values, list):
        sv_list = shap_values
    elif isinstance(shap_values, np.ndarray) and shap_values.ndim == 3:
        if shap_values.shape[0] == X_dense.shape[0]:
            # (n_samples, n_features, n_classes)
            sv_list = [shap_values[:, :, i] for i in range(shap_values.shape[2])]
        else:
            # (n_classes, n_samples, n_features)
            sv_list = [shap_values[i] for i in range(shap_values.shape[0])]
    else:
        raise ValueError(
            f"Formato de shap_values no reconocido: type={type(shap_values)}, "
            f"shape={getattr(shap_values, 'shape', 'N/A')}. "
            f"Ejecuta primero explicar_con_shap para obtener el formato correcto."
        )

    # Beeswarm por clase
    for i, clase in enumerate(class_names):
        shap.summary_plot(
            sv_list[i], X_dense,
            feature_names=feature_names,
            max_display=max_display,
            show=False,
            plot_type="dot",
        )
        plt.title(f"SHAP beeswarm — {clase}")
        plt.tight_layout()
        path = os.path.join(output_dir, f"shap_beeswarm_{clase}.png")
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.show()
        plt.close()
        saved_paths.append(path)
        print(f"Guardado: {path}")

    # Bar plot global: SHAP >= 0.46 espera array 3D (n_samples, n_features, n_classes)
    sv_3d = np.stack(sv_list, axis=2)
    shap.summary_plot(
        sv_3d, X_dense,
        feature_names=feature_names,
        class_names=class_names,
        max_display=max_display,
        show=False,
        plot_type="bar",
    )
    plt.title("Importancia media SHAP por clase")
    plt.tight_layout()
    path_bar = os.path.join(output_dir, "shap_importancia_clases.png")
    plt.savefig(path_bar, dpi=150, bbox_inches="tight")
    plt.show()
    plt.close()
    saved_paths.append(path_bar)
    print(f"Guardado: {path_bar}")

    return saved_paths


def plot_shap_waterfall(explainer, shap_values, X_explain, idx, feature_names, class_names, output_dir, max_display=15):
    """
    Genera un waterfall plot para la muestra `idx`, uno por clase.

    Parameters:
    explainer     : SHAP explainer ajustado.
    shap_values   : lista de arrays SHAP (uno por clase).
    X_explain     : sparse matrix o array con las muestras explicadas.
    idx           : int — índice de la muestra a visualizar.
    feature_names : list de str con los nombres de las features.
    class_names   : list de str con los nombres de las clases.
    output_dir    : str — carpeta donde guardar los plots.
    max_display   : int — número máximo de features a mostrar (default 15).

    Returns:
    saved_paths : list de rutas de los archivos guardados.
    """
    import shap

    os.makedirs(output_dir, exist_ok=True)
    X_dense = X_explain.toarray() if hasattr(X_explain, "toarray") else X_explain
    expected = explainer.expected_value
    saved_paths = []

    for i, clase in enumerate(class_names):
        ev = expected[i] if hasattr(expected, "__len__") else expected
        explanation = shap.Explanation(
            values=shap_values[i][idx],
            base_values=ev,
            data=X_dense[idx],
            feature_names=feature_names,
        )
        shap.plots.waterfall(explanation, max_display=max_display, show=False)
        plt.title(f"SHAP waterfall — muestra {idx} — clase {clase}")
        plt.tight_layout()
        path = os.path.join(output_dir, f"shap_waterfall_idx{idx}_{clase}.png")
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.show()
        plt.close()
        saved_paths.append(path)
        print(f"Guardado: {path}")

    return saved_paths


# ══════════════════════════════════════════════
# 9. SERIALIZACIÓN Y REGISTRO DEL MEJOR MODELO
# ══════════════════════════════════════════════

def guardar_pipeline_completo(modelo, tfidf, label_encoder=None, metadata=None, output_dir="model"):
    """
    Guarda el pipeline completo del mejor modelo con naming convention claro.

    Artefactos generados:
    - mejor_modelo.joblib
    - mejor_modelo_tfidf.joblib
    - mejor_modelo_label_encoder.joblib  (solo si se pasa label_encoder)
    - model_metadata.json

    Parameters:
    modelo         : modelo sklearn entrenado.
    tfidf          : TfidfVectorizer ajustado.
    label_encoder  : LabelEncoder opcional (para modelos XGBoost).
    metadata       : dict con información adicional (experimento, métricas, etc.).
    output_dir     : str — carpeta donde guardar los artefactos.

    Returns:
    tuple (path_modelo, path_tfidf, path_meta)
    """
    import json
    from datetime import datetime

    os.makedirs(output_dir, exist_ok=True)

    path_modelo = os.path.join(output_dir, "mejor_modelo.joblib")
    path_tfidf = os.path.join(output_dir, "mejor_modelo_tfidf.joblib")

    joblib.dump(modelo, path_modelo)
    joblib.dump(tfidf, path_tfidf)
    print(f"Modelo guardado:      {path_modelo}")
    print(f"Vectorizador guardado: {path_tfidf}")

    if label_encoder is not None:
        path_le = os.path.join(output_dir, "mejor_modelo_label_encoder.joblib")
        joblib.dump(label_encoder, path_le)
        print(f"LabelEncoder guardado: {path_le}")

    meta = {
        "fecha": datetime.now().isoformat(),
        "model_type": type(modelo).__name__,
        "tfidf_vocab_size": len(tfidf.vocabulary_),
        "tfidf_ngram_range": str(tfidf.ngram_range),
        "tfidf_max_features": tfidf.max_features,
    }
    if metadata:
        meta.update(metadata)

    path_meta = os.path.join(output_dir, "model_metadata.json")
    with open(path_meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"Metadata guardada:    {path_meta}")

    return path_modelo, path_tfidf, path_meta


def registrar_modelo_en_registry(run_id, artifact_path, registered_name, stage="Production"):
    """
    Registra un modelo de un run de MLflow en el Model Registry y lo
    transita al stage indicado.

    Parameters:
    run_id          : str — ID del run de MLflow donde está logueado el modelo.
    artifact_path   : str — ruta relativa del artefacto dentro del run (e.g. "modelo").
    registered_name : str — nombre con el que registrar el modelo.
    stage           : str — stage al que transitar ("Staging" o "Production").

    Returns:
    model_version : mlflow.entities.model_registry.ModelVersion
    """
    from mlflow.tracking import MlflowClient

    model_uri = f"runs:/{run_id}/{artifact_path}"
    model_version = mlflow.register_model(model_uri, registered_name)

    client = MlflowClient()
    client.set_registered_model_alias(
        name=registered_name,
        alias=stage.lower(),
        version=model_version.version,
    )
    client.update_registered_model(
        name=registered_name,
        description=f"Mejor modelo del experimento {MLFLOW_EXPERIMENT}.",
    )
    client.set_registered_model_tag(registered_name, "best_model", "true")

    print(f"✓ '{registered_name}' v{model_version.version} → stage='{stage}'")
    return model_version
