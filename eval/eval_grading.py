"""eval/eval_grading.py — Evaluación del prompt de grading.

Mide precision y recall del GRADING_PROMPT contra el test set manual.
Guarda los resultados en eval/grading_results.json para comparar variantes.

Uso:
    python eval/eval_grading.py
    python eval/eval_grading.py --variant v1  # para variantes futuras

Requiere Ollama corriendo localmente:
    brew services start ollama
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

TEST_SET_PATH = Path(__file__).parent / "grading_test_set.json"
RESULTS_PATH = Path(__file__).parent / "grading_results.json"

# Prompt v0 — el actual en src/rag/main.py
GRADING_PROMPTS = {
    "v0": (
        "Dado el siguiente documento y la pregunta, "
        "¿el documento contiene información útil para responder la pregunta?\n\n"
        "Documento: {document}\n"
        "Pregunta: {query}\n\n"
        'Responde solo con "si" o "no":'
    ),
}


def get_llm():
    """Devuelve el LLM de grading (Ollama Qwen 2.5 3B)."""
    from langchain_ollama import ChatOllama
    return ChatOllama(model="qwen2.5:3b", temperature=0, num_predict=10)


def predict_label(llm, prompt_template: str, query: str, document: str) -> str:
    """Devuelve 'si' o 'no' según el prompt de grading."""
    prompt = prompt_template.format(document=document, query=query)
    response = llm.invoke(prompt)
    answer = response.content.strip().lower()
    return "si" if answer.startswith("si") or answer.startswith("sí") else "no"


def evaluate(variant: str = "v0") -> dict:
    """Corre el prompt indicado contra el test set y calcula métricas."""
    prompt_template = GRADING_PROMPTS[variant]

    with open(TEST_SET_PATH, encoding="utf-8") as f:
        test_set = json.load(f)

    logger.info("Cargando Ollama...")
    llm = get_llm()

    logger.info("Evaluando variante '%s' con %d pares...", variant, len(test_set))

    results = []
    for i, item in enumerate(test_set, 1):
        predicted = predict_label(llm, prompt_template, item["query"], item["document"])
        correct = predicted == item["label"]
        results.append({
            "query": item["query"],
            "document": item["document"][:80] + "...",
            "label": item["label"],
            "predicted": predicted,
            "correct": correct,
        })
        logger.info(
            "[%d/%d] label=%s predicted=%s %s",
            i, len(test_set),
            item["label"], predicted,
            "✓" if correct else "✗",
        )

    # Calcular precision y recall
    tp = sum(1 for r in results if r["label"] == "si" and r["predicted"] == "si")
    fp = sum(1 for r in results if r["label"] == "no" and r["predicted"] == "si")
    fn = sum(1 for r in results if r["label"] == "si" and r["predicted"] == "no")

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    accuracy = sum(1 for r in results if r["correct"]) / len(results)

    metrics = {
        "variant": variant,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "accuracy": round(accuracy, 4),
        "tp": tp, "fp": fp, "fn": fn,
        "n_total": len(results),
    }

    logger.info("─" * 40)
    logger.info("Resultados variante '%s':", variant)
    logger.info("  Precision : %.4f", precision)
    logger.info("  Recall    : %.4f", recall)
    logger.info("  Accuracy  : %.4f", accuracy)
    logger.info("─" * 40)

    # Guardar resultados
    all_results = {}
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH, encoding="utf-8") as f:
            all_results = json.load(f)

    all_results[variant] = {"metrics": metrics, "detail": results}

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    logger.info("Resultados guardados en %s", RESULTS_PATH)
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluación del prompt de grading")
    parser.add_argument(
        "--variant", default="v0",
        choices=list(GRADING_PROMPTS.keys()),
        help="Variante del prompt a evaluar (default: v0)",
    )
    args = parser.parse_args()
    evaluate(variant=args.variant)
