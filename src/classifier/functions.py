import spacy

# Se carga una sola vez al importar el módulo
nlp = spacy.load("es_core_news_sm", disable=["parser", "ner"])

def limpiar_texto(texto):
    doc = nlp(texto.lower())
    
    tokens_limpios = [
        token.text
        for token in doc
        if not token.is_punct
        and not token.is_space
        and not token.is_stop
    ]
    
    return " ".join(tokens_limpios)