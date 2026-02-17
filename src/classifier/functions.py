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
    roc_auc_score,
    roc_curve,
    auc,
)
from sklearn.preprocessing import label_binarize
import joblib
import os

# ──────────────────────────────────────────────
# Pipelines de spaCy (se cargan una sola vez)
# ──────────────────────────────────────────────
nlp = spacy.load("es_core_news_sm", disable=["parser", "ner"])
nlp_ner = spacy.load("es_core_news_sm")


# ══════════════════════════════════════════════
# 1. FUNCIONES DE LIMPIEZA DE TEXTO
# ══════════════════════════════════════════════

def limpiar_texto(texto):
    """
    Limpia el texto utilizando spaCy:
    - Convierte a minúsculas
    - Elimina puntuación, espacios y stop words
    Parameters:
    texto : str
        El texto a limpiar.
    Returns:
    str
        El texto limpio.
    """
    doc = nlp(texto.lower())
    tokens_limpios = [
        token.text
        for token in doc
        if not token.is_punct
        and not token.is_space
        and not token.is_stop
    ]
    return " ".join(tokens_limpios)


def limpiar_texto_preprocess(texto):
    """
    Limpia el texto utilizando spaCy con lematización:
    - Convierte a minúsculas
    - Elimina puntuación, espacios y stop words
    - Lematiza las palabras (reduce a su forma base o raíz).
      Por ejemplo, "corriendo", "corrí" y "correrá" se lematizan a "correr".
    Parameters:
    texto : str
        El texto a limpiar.
    Returns:
    str
        El texto limpio y lematizado.
    """
    doc = nlp(texto.lower())
    tokens = [
        token.lemma_
        for token in doc
        if not token.is_punct
        and not token.is_space
        and not token.is_stop
    ]
    return " ".join(tokens)


# ══════════════════════════════════════════════
# 2. FUNCIONES DE ANÁLISIS EXPLORATORIO (EDA)
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
    Crea y ajusta un vectorizador TF-IDF sobre el conjunto de entrenamiento
    y transforma train, validation y test.

    Returns:
    tuple (tfidf, X_train_tfidf, X_val_tfidf, X_test_tfidf)
    """
    tfidf = TfidfVectorizer(
        max_features=max_features,
        ngram_range=ngram_range,
        sublinear_tf=True,
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
    Entrena un modelo LogisticRegression como baseline y muestra resultados
    sobre el conjunto de validación.

    Returns:
    modelo : LogisticRegression entrenado
    """
    modelo = LogisticRegression(max_iter=1000, random_state=42)
    modelo.fit(X_train_tfidf, y_train)

    y_val_pred = modelo.predict(X_val_tfidf)

    print("=== Resultados en VALIDACIÓN ===\n")
    print(classification_report(y_val, y_val_pred))

    f1_macro = f1_score(y_val, y_val_pred, average="macro")
    print(f"F1-score macro (validación): {f1_macro:.4f}")

    return modelo


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
    report = classification_report(y_test, y_pred)
    print(report)

    f1_macro = f1_score(y_test, y_pred, average="macro")
    print(f"F1-score macro (test): {f1_macro:.4f}\n")

    report_dict = classification_report(y_test, y_pred, output_dict=True)
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
    Muestra los ejemplos mal clasificados para analizar patrones de error.

    Returns:
    df_errores : pd.DataFrame con las predicciones incorrectas.
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
