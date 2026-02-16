"""data/main.py — Embeddings + ChromaDB
Hello world: simula indexar artículos y buscar por similitud.
"""

ARTICLES = [
    {"id": "euaiact-art5", "text": "Quedan prohibidas las prácticas de IA que manipulen el comportamiento humano mediante técnicas subliminales.", "metadata": {"ley": "EU AI Act", "articulo": "5", "tema": "prohibiciones"}},
    {"id": "euaiact-art6", "text": "Los sistemas de IA de alto riesgo del Anexo III deberán cumplir los requisitos del Capítulo 2.", "metadata": {"ley": "EU AI Act", "articulo": "6", "tema": "alto_riesgo"}},
    {"id": "euaiact-art52", "text": "Los proveedores de sistemas de riesgo limitado garantizarán transparencia informando a los usuarios.", "metadata": {"ley": "EU AI Act", "articulo": "52", "tema": "transparencia"}},
]


def ingest(articles: list[dict]) -> dict:
    # TODO: reemplazar con SentenceTransformer + chromadb.Client()
    return {
        "collection": "normabot_legal",
        "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
        "documents_indexed": len(articles),
        "ids": [a["id"] for a in articles],
    }


def search(query: str, top_k: int = 2) -> list[dict]:
    # TODO: reemplazar con collection.query(query_embeddings=...)
    return [
        {"id": "euaiact-art6", "score": 0.91, "text": ARTICLES[1]["text"], "metadata": ARTICLES[1]["metadata"]},
        {"id": "euaiact-art5", "score": 0.73, "text": ARTICLES[0]["text"], "metadata": ARTICLES[0]["metadata"]},
    ][:top_k]


if __name__ == "__main__":
    result = ingest(ARTICLES)
    print(f"Indexed:   {result['documents_indexed']} docs en '{result['collection']}'")
    print(f"Model:     {result['embedding_model']}")

    hits = search("sistemas de alto riesgo")
    print(f"\nQuery:     'sistemas de alto riesgo'")
    for i, h in enumerate(hits):
        print(f"  [{i+1}] score={h['score']:.2f}  Art. {h['metadata']['articulo']} — {h['text'][:60]}...")

    print("\n✓ data/main.py OK")
