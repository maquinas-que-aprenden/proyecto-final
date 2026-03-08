"""Orquestador de aumentación del dataset EU AI Act.

Lee el CSV original, aplica por cada ejemplo:
  - n paráfrasis via LLM (Bedrock Nova Lite)  [por defecto 3]
  - 1 back-translation ES → EN → ES

Guarda el resultado en:
  bert_pipeline/data/dataset_augmented.jsonl

Uso:
    python -m src.classifier.bert_pipeline.augmentation.run_augmentation
    python -m src.classifier.bert_pipeline.augmentation.run_augmentation --limit 10   # debug
    python -m src.classifier.bert_pipeline.augmentation.run_augmentation --n-paraphrases 3 --no-back-translation
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from .back_translation import back_translate
from .paraphrase_llm import paraphrase

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SEED = 42
random.seed(SEED)

_HERE = Path(__file__).parent

DATASET_CSV = (
    _HERE.parent.parent
    / "classifier_dataset_fusionado"
    / "datasets"
    / "eu_ai_act_flagged_es_limpio.csv"
)
OUTPUT_JSONL = _HERE.parent / "data" / "dataset_augmented.jsonl"


def augment_dataset(
    n_paraphrases: int = 3,
    include_back_translation: bool = True,
    limit: int | None = None,
) -> None:
    """Lee el CSV original, genera aumentaciones y las guarda en JSONL.

    El JSONL resultante contiene el ejemplo original más las variaciones,
    cada uno con su etiqueta y una columna ``source`` que indica su origen
    (original | paraphrase_1..N | back_translation).
    """
    if not DATASET_CSV.exists():
        raise FileNotFoundError(f"Dataset no encontrado: {DATASET_CSV}")

    logger.info("Cargando dataset desde %s", DATASET_CSV)
    df = pd.read_csv(DATASET_CSV)[["descripcion", "etiqueta_normalizada"]].dropna()

    if limit:
        df = df.head(limit)
        logger.info("Modo debug: limitado a %d ejemplos", limit)

    logger.info(
        "Dataset original: %d ejemplos\nDistribución:\n%s",
        len(df),
        df["etiqueta_normalizada"].value_counts().to_string(),
    )

    OUTPUT_JSONL.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    with OUTPUT_JSONL.open("w", encoding="utf-8") as out:
        for _, row in tqdm(df.iterrows(), total=len(df), desc="Aumentando dataset"):
            texto: str = str(row["descripcion"])
            etiqueta: str = str(row["etiqueta_normalizada"])

            def _write(desc: str, source: str) -> None:
                nonlocal total
                out.write(
                    json.dumps(
                        {"descripcion": desc, "etiqueta": etiqueta, "source": source},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                total += 1

            # Ejemplo original siempre incluido
            _write(texto, "original")

            # Paráfrasis LLM
            parafraseos = paraphrase(texto, n=n_paraphrases, label=etiqueta)
            for i, p in enumerate(parafraseos, start=1):
                _write(p, f"paraphrase_{i}")

            # Back-translation
            if include_back_translation:
                bt = back_translate(texto)
                if bt:
                    _write(bt, "back_translation")

    logger.info(
        "Dataset aumentado guardado en %s\nTotal ejemplos: %d (x%.1f del original)",
        OUTPUT_JSONL,
        total,
        total / len(df),
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Aumentación del dataset EU AI Act")
    parser.add_argument("--n-paraphrases", type=int, default=3, help="Paráfrasis LLM por ejemplo")
    parser.add_argument("--no-back-translation", action="store_true", help="Desactivar back-translation")
    parser.add_argument("--limit", type=int, default=None, help="Limitar a N filas (debug)")
    args = parser.parse_args()

    augment_dataset(
        n_paraphrases=args.n_paraphrases,
        include_back_translation=not args.no_back_translation,
        limit=args.limit,
    )
