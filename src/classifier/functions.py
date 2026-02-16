import spacy
import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter
# Se carga una sola vez al importar el módulo
nlp = spacy.load("es_core_news_sm", disable=["parser", "ner"])

def limpiar_texto(texto):
    """
    Esta función limpia el texto utilizando spaCy:
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


def analyze_text_length_distribution(df, text_column, label_column):
    """
    Calcula media y mediana de longitud de texto por clase
    y muestra un boxplot de distribución.

    Parameters:
    df : pandas.DataFrame
    text_column : str
        Nombre de la columna con el texto.
    label_column : str
        Nombre de la columna con la etiqueta/clase.
    """

    import matplotlib.pyplot as plt
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


#Creamos una función que nos de los n-grams más comunes en el corpus, nos muestre una lista ordenada de los 20 primeros y una gráfica de barras con su frecuencia
def top_ngrams(df, n=20, ngram=2):
    """
    Esta función devuelve los n-grams más comunes en un dataframe de pandas que contiene reviews de texto en una columna llamada 'reviewText'
    
    df: Es el dataset o corpus que informamos a la función. Debe contener la columna 'reviewText'
    n: Es el número de n-grams más comunes que queremos obtener. Por defecto es 20, pero podemos ajustarlo a nuestro gusto.
    ngram: Es el tamaño del n-grama que queremos obtener. Por defecto es 2 (bigramas), pero podemos ajustarlo a nuestro gusto.
    return: Una lista de tuplas con los n-grams más comunes y su frecuencia.
    """
    all_ngrams = []
    for review in df['descripcion_limpia']:
        words = review.split()
        ngrams = zip(*[words[i:] for i in range(ngram)])
        ngrams = [' '.join(ngram) for ngram in ngrams]
        all_ngrams.extend(ngrams)
    
    # contador global
    ngram_counter = Counter(all_ngrams)
    ngram_most_common = ngram_counter.most_common(n)
    
    # Gráfica de barras
    ngram_df = pd.DataFrame(ngram_most_common, columns=['ngram', 'frequency'])
    plt.figure(figsize=(10,6))
    plt.barh(ngram_df['ngram'], ngram_df['frequency'], color='skyblue')
    plt.xlabel('Frequency')
    plt.ylabel(f'Top {n} {ngram}-grams')
    plt.title(f'Top {n} {ngram}-grams in Reviews')
    plt.gca().invert_yaxis()
    plt.show()
    
    return ngram_most_common