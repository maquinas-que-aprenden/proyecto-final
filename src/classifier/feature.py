"""classifier/feature.py — Feature Extraction + spaCy NER
Hello world: simula TF-IDF + features manuales + NER sobre texto legal.
"""


def extract_tfidf(descriptions: list[str]) -> dict:
    # TODO: reemplazar con TfidfVectorizer(max_features=50).fit_transform(...)
    return {
        "shape": (len(descriptions), 50),
        "top_terms": ["sistema", "riesgo", "IA", "datos", "reconocimiento", "automático", "scoring", "vigilancia"],
    }


def extract_manual_features(sectors: list[str], data_types: list[str]) -> dict:
    # TODO: reemplazar con encoding numérico real
    return {
        "features": ["sector_encoded", "data_type_encoded"],
        "n_samples": len(sectors),
    }


def extract_ner(text: str) -> list[dict]:
    # TODO: reemplazar con spacy.load("es_core_news_sm")(text).ents
    return [
        {"text": "Reglamento UE 2024/1689", "label": "MISC"},
        {"text": "AESIA", "label": "ORG"},
        {"text": "España", "label": "LOC"},
    ]


if __name__ == "__main__":
    descriptions = [
        "Sistema de reconocimiento facial en aeropuertos",
        "Chatbot de atención al cliente",
        "Scoring crediticio automático",
    ]
    sectors = ["transporte", "comercio", "finanzas"]
    data_types = ["biometrico", "texto", "financiero"]

    tfidf = extract_tfidf(descriptions)
    print(f"TF-IDF:    {tfidf['shape']} (samples × features)")
    print(f"Top terms: {tfidf['top_terms'][:5]}")

    manual = extract_manual_features(sectors, data_types)
    print(f"Manual:    {manual['features']} ({manual['n_samples']} samples)")

    text = "El artículo 6 del Reglamento UE 2024/1689 establece que AESIA supervisará los sistemas de alto riesgo en España."
    entities = extract_ner(text)
    print(f"\nNER:       '{text[:50]}...'")
    for ent in entities:
        print(f"  {ent['text']} → {ent['label']}")

    print("\n✓ classifier/feature.py OK")
