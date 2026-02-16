"""classifier/main.py — XGBoost Clasificador de Riesgo
Hello world: simula clasificación en 4 niveles EU AI Act.
"""

LABEL_NAMES = ["inaceptable", "alto", "limitado", "minimo"]


def train(descriptions: list[str], labels: list[int]) -> dict:
    # TODO: reemplazar con TfidfVectorizer + XGBClassifier + StratifiedKFold
    return {
        "model": "XGBClassifier",
        "n_estimators": 50,
        "max_depth": 3,
        "cv_f1_macro": 0.82,
        "cv_std": 0.04,
    }


def predict(description: str) -> dict:
    # TODO: reemplazar con clf.predict(tfidf.transform([description]))
    keywords_risk = {
        "reconocimiento facial": 1,
        "scoring crediticio": 1,
        "puntuación social": 0,
        "chatbot": 2,
        "filtro de spam": 3,
    }
    label = 1  # default alto
    for kw, lvl in keywords_risk.items():
        if kw in description.lower():
            label = lvl
            break
    return {
        "description": description,
        "risk_level": label,
        "risk_name": LABEL_NAMES[label],
    }


if __name__ == "__main__":
    model_info = train([], [])
    print(f"Model:     {model_info['model']} (n_est={model_info['n_estimators']}, depth={model_info['max_depth']})")
    print(f"CV F1:     {model_info['cv_f1_macro']:.2f} (+/- {model_info['cv_std']:.2f})")

    test_cases = [
        "Sistema de puntuación social de ciudadanos",
        "Reconocimiento facial en aeropuertos",
        "Chatbot de atención al cliente",
        "Filtro de spam de email",
    ]
    print(f"\nPredicciones:")
    for desc in test_cases:
        result = predict(desc)
        print(f"  {result['risk_name']:>13} ← {desc}")

    print("\n✓ classifier/main.py OK")
