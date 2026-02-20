import spacy
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
# Configuración MLflow
# ──────────────────────────────────────────────
MLFLOW_TRACKING_URI = "https://34.240.189.163"
MLFLOW_EXPERIMENT = "clasificador_riesgo_ia"


def get_mlflow_password():
    """
    Obtiene la contraseña de MLflow desde:
    - Colab Secrets (si está en Colab)
    - Archivo .env en el directorio de trabajo (entorno local)
    - Variable de entorno del sistema (entorno local)
    """
    # Intentar obtener desde Colab
    try:
        from google.colab import userdata
        password = userdata.get("MLFLOW_PASSWORD")
        if password:
            print("Password obtenida desde Colab Secrets.")
            return password
    except ImportError:
        pass

    # Cargar .env si existe (necesario en Jupyter, donde las vars del sistema
    # no se propagan al kernel automáticamente).
    # Se usa la ruta del propio functions.py para no depender del directorio
    # de trabajo del kernel.
    try:
        from dotenv import load_dotenv
        from pathlib import Path
        dotenv_path = Path(__file__).parent / ".env"
        load_dotenv(dotenv_path=dotenv_path, override=True)
    except ImportError:
        pass  # python-dotenv no instalado, se continúa sin él

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
    """
    Configure MLflow credentials and tracking URI for the current process.
    
    Sets the MLFLOW_TRACKING_USERNAME and MLFLOW_TRACKING_PASSWORD environment variables (using the configured MLflow password), applies the module-level tracking URI via mlflow.set_tracking_uri, and prints a confirmation message. Does not modify MLFLOW_TRACKING_INSECURE_TLS.
    """
    password = get_mlflow_password()

    # No sobreescribir MLFLOW_TRACKING_INSECURE_TLS: respetar el valor que
    # el usuario haya configurado en su entorno (p. ej. para entornos con TLS válido).
    os.environ["MLFLOW_TRACKING_USERNAME"] = "tracker"
    os.environ["MLFLOW_TRACKING_PASSWORD"] = password

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    print(f"MLflow configurado correctamente → {MLFLOW_TRACKING_URI}")

# ──────────────────────────────────────────────
# Pipelines de spaCy (carga diferida bajo demanda)
# ──────────────────────────────────────────────
_nlp = None
_nlp_ner = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("es_core_news_sm", disable=["parser", "ner"])
    return _nlp


def _get_nlp_ner():
    global _nlp_ner
    if _nlp_ner is None:
        _nlp_ner = spacy.load("es_core_news_sm")
    return _nlp_ner


# ══════════════════════════════════════════════
# 1. FUNCIONES DE LIMPIEZA DE TEXTO
# ══════════════════════════════════════════════

def limpiar_texto(texto, lemmatize=False):
    """
    Limpia el texto utilizando spaCy:
    - Convierte a minúsculas
    - Elimina puntuación, espacios y stop words
    - Opcionalmente lematiza las palabras (reduce a su forma base o raíz).
      Por ejemplo, "corriendo", "corrí" y "correrá" se lematizan a "correr".

    Parameters:
    texto : str
        El texto a limpiar.
    lemmatize : bool
        Si True, lematiza los tokens (por defecto False).

    Returns:
    str
        El texto limpio.
    """
    doc = _get_nlp()(texto.lower())
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

# Palabras clave discriminativas por clase, extraídas del análisis exploratorio
KEYWORDS_DOMINIO = {
    "inaceptable": ["inferir", "vender", "emocional", "conocimiento", "biométrico",
                     "cámara", "facial", "vigilancia", "sindical", "parental"],
    "alto_riesgo": ["determinar", "autónomamente", "control", "supervisión",
                     "penitenciario", "juez", "autónomo", "reincidencia",
                     "medicación", "crediticio"],
    "riesgo_limitado": ["advertir", "indicar", "chatbot", "informar",
                         "automatizado", "limitación", "asesoramiento",
                         "artificial", "revelar", "asistente"],
    "riesgo_minimo": ["industrial", "sensor", "optimizar", "mejora",
                       "clasificación", "optimización", "investigador",
                       "gestión", "avería", "maquinaria"],
}


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

    resultados = []
    for doc in _get_nlp_ner().pipe(textos, batch_size=100):
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

def preparar_dataset(df, text_column, label_column):
    """
    Prepara el dataset aplicando limpieza con lematización.
    Devuelve un DataFrame con las columnas 'text_final' y la etiqueta.
    """
    df = df.copy()
    df["text_final"] = df[text_column].apply(limpiar_texto_preprocess)
    return df[["text_final", label_column]]


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

    X = df["text_final"]
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

    train_df = X_train.to_frame().join(y_train)
    val_df = X_val.to_frame().join(y_val)
    test_df = X_test.to_frame().join(y_test)

    print(f"Train: {len(train_df)} muestras")
    print(f"Validation: {len(val_df)} muestras")
    print(f"Test: {len(test_df)} muestras")

    return train_df, val_df, test_df


# ══════════════════════════════════════════════
# 5. FUNCIONES DE ENTRENAMIENTO
# ══════════════════════════════════════════════

def crear_tfidf(X_train, X_val, X_test, max_features=5000, ngram_range=(1, 2)):
    """
    Create and fit a TF-IDF vectorizer on training texts and transform train, validation, and test sets.
    
    Parameters:
        X_train (Sequence[str]): Iterable of raw training texts.
        X_val (Sequence[str]): Iterable of raw validation texts.
        X_test (Sequence[str]): Iterable of raw test texts.
        max_features (int): Maximum number of features (vocabulary size) for the vectorizer.
        ngram_range (tuple[int, int]): The lower and upper boundary of the range of n-values for different n-grams to be extracted.
    
    Returns:
        tuple: (tfidf, X_train_tfidf, X_val_tfidf, X_test_tfidf)
            - tfidf: Fitted TfidfVectorizer instance.
            - X_train_tfidf: Sparse matrix of TF-IDF features for the training set.
            - X_val_tfidf: Sparse matrix of TF-IDF features for the validation set.
            - X_test_tfidf: Sparse matrix of TF-IDF features for the test set.
    """
    tfidf = TfidfVectorizer(
        max_features=max_features,
        ngram_range=ngram_range,
        sublinear_tf=True,
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


def entrenar_modelo_baseline(X_train_tfidf, y_train, X_val_tfidf, y_val):
    """
    Train a logistic regression baseline and print validation metrics.
    
    Train a LogisticRegression classifier on the provided TF-IDF training matrix and print a classification report and macro F1 score computed on the validation set.
    
    Parameters:
        X_train_tfidf (sparse matrix or ndarray): TF-IDF features for training.
        y_train (array-like): Training labels.
        X_val_tfidf (sparse matrix or ndarray): TF-IDF features for validation.
        y_val (array-like): Validation labels.
    
    Returns:
        modelo (LogisticRegression): Fitted LogisticRegression model.
    """
    modelo = LogisticRegression(max_iter=2000, random_state=42)
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
    y_val_enc = le.transform(y_val)

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

    modelo = XGBClassifier(**default_params)
    modelo.fit(X_train, y_train_enc)

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

    grid.fit(X_train, y_train_enc)

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

def evaluar_modelo(modelo, tfidf, X_test, y_test):
    """
    Evalúa el modelo sobre el conjunto de test y muestra:
    - Classification report
    - F1-score macro
    - Matriz de confusión

    Returns:
    tuple (y_pred, report_dict)
    """
    X_test_tfidf = tfidf.transform(X_test)
    y_pred = modelo.predict(X_test_tfidf)

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


def plot_curva_roc_multiclase(modelo, tfidf, X_test, y_test):
    """
    Genera la curva ROC multiclase (One-vs-Rest) para el modelo.

    Parameters:
    modelo : modelo entrenado con predict_proba.
    tfidf : TfidfVectorizer ajustado.
    X_test : pd.Series con los textos de test.
    y_test : pd.Series con las etiquetas reales.

    Returns:
    fig : matplotlib.figure.Figure
    roc_auc_dict : dict con el AUC por clase.
    """
    clases = sorted(modelo.classes_)
    X_test_tfidf = tfidf.transform(X_test)
    y_test_bin = label_binarize(y_test, classes=clases)
    y_proba = modelo.predict_proba(X_test_tfidf)

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


def analisis_errores(modelo, tfidf, X_test, y_test):
    """
    Show misclassified test examples to assist error analysis.
    
    Parameters:
        modelo: Trained classifier with a `predict` method.
        tfidf: Fitted vectorizer with a `transform` method.
        X_test (pd.Series or array-like): Raw text samples to classify.
        y_test (pd.Series or array-like): True labels corresponding to X_test.
    
    Returns:
        df_errores (pd.DataFrame): Rows where predictions differ from true labels, with columns:
            - texto: original input text,
            - etiqueta_real: true label,
            - etiqueta_predicha: model prediction.
    """
    X_test_tfidf = tfidf.transform(X_test)
    y_pred = modelo.predict(X_test_tfidf)

    df_resultado = pd.DataFrame({
        "texto": X_test.values,
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

def log_mlflow_safe(run_name, params=None, metrics=None, artifacts=None, tags=None):
    """
    Log parameters, metrics, artifacts, and tags to a named MLflow run after configuring MLflow.
    
    Parameters:
        run_name (str): Name for the MLflow run.
        params (dict, optional): Hyperparameters or configuration key-value pairs to log.
        metrics (dict, optional): Numeric metrics to log.
        artifacts (list[str], optional): Local file paths to upload as run artifacts.
        tags (dict, optional): Additional tags to attach to the run.
    """
    configure_mlflow()
    mlflow.set_experiment(MLFLOW_EXPERIMENT)

    with mlflow.start_run(run_name=run_name):
        if params:
            mlflow.log_params(params)
        if metrics:
            mlflow.log_metrics(metrics)
        if artifacts:
            for path in artifacts:
                mlflow.log_artifact(path)
        if tags:
            mlflow.set_tags(tags)

    print(f"✓ Run '{run_name}' registrado en MLflow ({MLFLOW_TRACKING_URI})")


# ══════════════════════════════════════════════
# 8. SHAP — EXPLICABILIDAD
# ══════════════════════════════════════════════

_MAX_DENSE_ELEMENTS = 50_000_000  # ~400 MB en float64; ajustable según entorno


def _sparse_to_dense_safe(X, label="X", max_elements=_MAX_DENSE_ELEMENTS):
    """
    Safely convert a sparse matrix to a dense numpy array with a memory-size guard.
    
    If the input supports `toarray()`, the function converts it to a dense numpy array unless
    the total number of elements (rows × columns) exceeds `max_elements`, in which case a
    random subset of rows is sampled and converted to avoid out-of-memory errors; a warning
    is emitted when sampling occurs.
    
    Parameters:
        X: object
            Input matrix or array. If `X` does not implement `toarray()`, it is returned unchanged.
        label (str): optional
            Human-readable name used in the warning message when sampling is performed.
        max_elements (int): optional
            Maximum allowed number of elements (rows × columns) for a full dense conversion.
            If exceeded, the function samples rows so the resulting matrix has at most this many elements.
    
    Returns:
        numpy.ndarray or original input:
            A dense numpy array converted from `X` (or from a sampled subset of `X` if sampling occurred),
            or the original `X` when it does not support `toarray()`.
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
    Compute SHAP explanations for a trained classifier.
    
    Uses a linear SHAP explainer for sklearn LogisticRegression models and a tree explainer for other model types; sparse inputs will be converted to dense when required. The returned SHAP values are normalized to a list of 2-D arrays (n_samples, n_features), one array per class.
    
    Parameters:
        modelo: Trained classifier (e.g., sklearn LogisticRegression or tree-based model).
        X_background: Reference dataset (array or sparse matrix) used to initialize the explainer.
        X_explain: Samples (array or sparse matrix) to explain.
    
    Returns:
        tuple: (explainer, shap_values)
            explainer: The fitted SHAP explainer object.
            shap_values: List of 2-D numpy arrays, each of shape (n_samples, n_features), one entry per class.
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
    Generate and save SHAP summary visualizations: a beeswarm plot for each class and a global per-class importance bar chart.
    
    Parameters:
        shap_values: list or ndarray
            SHAP values as either a list of 2D arrays (one per class, shape (n_samples, n_features))
            or a 3D ndarray with one of the two shapes:
            - (n_samples, n_features, n_classes) or
            - (n_classes, n_samples, n_features).
            The function accepts these formats and normalizes them internally.
        X_explain: array-like or sparse matrix
            Samples used for plotting (rows correspond to samples). A sparse matrix will be converted to dense.
        feature_names: list[str]
            Names of the features (length = n_features).
        class_names: list[str]
            Names of the target classes (length = n_classes).
        output_dir: str
            Directory where plot files will be saved; created if it does not exist.
        max_display: int, optional
            Maximum number of features to display in each plot (default 20).
    
    Returns:
        saved_paths: list[str]
            Paths to the image files written to disk.
    """
    import shap
    import numpy as np

    os.makedirs(output_dir, exist_ok=True)
    X_dense = X_explain.toarray() if hasattr(X_explain, "toarray") else X_explain
    saved_paths = []

    # Normalizar shap_values a lista de arrays 2D (n_samples, n_features), uno por clase.
    # SHAP >= 0.46 puede devolver ndarray 3D o lista; hay que manejar ambos.
    n_classes = len(class_names)
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
    Create and save SHAP waterfall plots for a single sample, producing one plot per class.
    
    Parameters:
        explainer: A fitted SHAP Explainer whose `expected_value` provides base values.
        shap_values: List-like of SHAP value arrays (one entry per class) where each array has shape (n_samples, n_features).
        X_explain: 2D array or sparse matrix of samples used for explanations; the row at `idx` will be plotted.
        idx (int): Index of the sample (row) in `X_explain` to visualize.
        feature_names (list[str]): Names of the input features, in the same order as columns of `X_explain`.
        class_names (list[str]): Names of classes corresponding to entries in `shap_values`.
        output_dir (str): Directory where PNG files will be saved; the directory will be created if it does not exist.
        max_display (int): Maximum number of features to show in each waterfall plot.
    
    Returns:
        saved_paths (list[str]): Paths to the saved waterfall plot image files, one per class.
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
    Save the full trained pipeline (model, TF-IDF vectorizer, optional label encoder) and metadata to disk using a clear naming convention.
    
    Parameters:
        modelo: Trained model object to serialize (e.g., sklearn or XGBoost estimator).
        tfidf: Fitted TfidfVectorizer to serialize.
        label_encoder: Optional LabelEncoder to serialize alongside the model.
        metadata: Optional dict with additional metadata to merge into the saved JSON (e.g., experiment info or metrics).
        output_dir: Directory path where artefacts will be written. Files created: mejor_modelo.joblib, mejor_modelo_tfidf.joblib, optionally mejor_modelo_label_encoder.joblib, and model_metadata.json.
    
    Returns:
        tuple: (path_modelo, path_tfidf, path_meta) — filesystem paths to the saved model file, TF-IDF file, and metadata JSON respectively.
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
    Register a model artifact produced in an MLflow run to the MLflow Model Registry and transition it to the specified stage.
    
    This function registers the model located at the given run artifact path under the provided registered name, transitions the created model version to `stage` (for example "Staging" or "Production"), updates the registered model description, and tags the registered model with `best_model=true`.
    
    Parameters:
        run_id (str): MLflow run identifier that contains the logged model.
        artifact_path (str): Relative artifact path inside the run (e.g., "modelo" or "model").
        registered_name (str): Name to use for the registered model in the Model Registry.
        stage (str): Target stage to transition the new model version to (e.g., "Staging" or "Production").
    
    Returns:
        model_version: The created mlflow.entities.model_registry.ModelVersion object for the registered model.
    """
    from mlflow.tracking import MlflowClient

    model_uri = f"runs:/{run_id}/{artifact_path}"
    model_version = mlflow.register_model(model_uri, registered_name)

    client = MlflowClient()
    client.transition_model_version_stage(
        name=registered_name,
        version=model_version.version,
        stage=stage,
    )
    client.update_registered_model(
        name=registered_name,
        description=f"Mejor modelo del experimento {MLFLOW_EXPERIMENT}.",
    )
    client.set_registered_model_tag(registered_name, "best_model", "true")

    print(f"✓ '{registered_name}' v{model_version.version} → stage='{stage}'")
    return model_version