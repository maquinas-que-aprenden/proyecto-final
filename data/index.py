"""data/index.py — Pipeline de indexacion: chunks JSONL → embeddings + ChromaDB

Carga los chunks generados por ingest.py, genera embeddings con
SentenceTransformer y puebla un vectorstore ChromaDB persistente.

Uso:
    python data/index.py
"""

from pathlib import Path
import json

import chromadb
import numpy as np
from sentence_transformers import SentenceTransformer

# ── Rutas ───────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "chunks_legal" / "chunks_final_all_sources.jsonl"
VSTORE_DIR = PROJECT_ROOT / "data" / "processed" / "vectorstore"
CHROMA_DIR = VSTORE_DIR / "chroma"

MODEL_NAME = "intfloat/multilingual-e5-base"
COLLECTION_NAME = "normabot_legal_chunks"
BATCH_SIZE = 200

# ── Pipeline ────────────────────────────────────────────────────────


def load_chunks(path: Path) -> tuple[list[str], list[dict]]:
    """Carga chunks desde JSONL. Devuelve (textos, metadata)."""
    texts = []
    metadata = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            texts.append(rec["text"])
            metadata.append(rec)
    return texts, metadata


def generate_embeddings(texts: list[str], model: SentenceTransformer) -> np.ndarray:
    """Genera embeddings para todos los textos (con prefijo 'passage: ' para e5)."""
    prefixed = [f"passage: {t}" for t in texts]
    return model.encode(
        prefixed,
        batch_size=16,
        show_progress_bar=True,
        convert_to_numpy=True,
        device="cpu",
    )


def populate_chroma(
    texts: list[str],
    embeddings: np.ndarray,
    metadata: list[dict],
) -> None:
    """Puebla ChromaDB desde cero (re-indexación completa)."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    # Re-indexación completa: borrar colección anterior si existe
    try:
        client.delete_collection(name=COLLECTION_NAME)
    except ValueError:
        pass  # Primera ejecución: no existe colección anterior
    col = client.create_collection(name=COLLECTION_NAME)

    ids = []
    metas = []
    for i, rec in enumerate(metadata):
        cid = rec.get("id") or f"chunk_{i}"
        ids.append(str(cid))
        m = dict(rec)
        m.pop("text", None)  # no duplicar texto en metadata
        metas.append(m)

    n = len(ids)
    for start in range(0, n, BATCH_SIZE):
        end = min(start + BATCH_SIZE, n)
        col.upsert(
            ids=ids[start:end],
            documents=texts[start:end],
            embeddings=embeddings[start:end].tolist(),
            metadatas=metas[start:end],
        )
        print(f"  Upsert {start}:{end} OK")

    print(f"  Chroma count: {col.count()}")


# ── Main ────────────────────────────────────────────────────────────


def main() -> None:
    print("=== Indexacion de chunks ===")
    print(f"Input:  {DATA_PATH}")
    print(f"Output: {VSTORE_DIR}")

    if not DATA_PATH.exists():
        print(f"\n[ERROR] No existe {DATA_PATH}. Ejecuta primero: python data/ingest.py")
        return

    # 1) Cargar chunks
    print("\n-- Cargando chunks --")
    texts, metadata = load_chunks(DATA_PATH)
    print(f"  Chunks: {len(texts)}")

    # 2) Generar embeddings
    print(f"\n-- Generando embeddings ({MODEL_NAME}) --")
    model = SentenceTransformer(MODEL_NAME)
    embeddings = generate_embeddings(texts, model)
    print(f"  Shape: {embeddings.shape}")

    # 3) Poblar ChromaDB
    print("\n-- Poblando ChromaDB --")
    populate_chroma(texts, embeddings, metadata)

    print("\n=== Indexacion completada ===")


if __name__ == "__main__":
    main()
