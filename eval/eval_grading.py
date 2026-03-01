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

    # v1 — Few-shot: 2 ejemplos (1 relevante, 1 irrelevante) para guiar al modelo
    "v1": (
        "Tu tarea es decidir si un documento contiene información útil para responder una pregunta.\n\n"
        "Ejemplos:\n\n"
        "Pregunta: ¿Qué prácticas de IA están prohibidas?\n"
        "Documento: Artículo 5. Quedan prohibidas las siguientes prácticas de IA: sistemas que utilicen "
        "técnicas subliminales para alterar el comportamiento de una persona.\n"
        "Respuesta: si\n\n"
        "Pregunta: ¿Qué prácticas de IA están prohibidas?\n"
        "Documento: Artículo 9. Se establecerá un sistema de gestión de riesgos en relación con los "
        "sistemas de IA de alto riesgo.\n"
        "Respuesta: no\n\n"
        "Ahora evalúa:\n\n"
        "Pregunta: {query}\n"
        "Documento: {document}\n\n"
        'Responde solo con "si" o "no":'
    ),

    # v2 — Chain of Thought: el modelo razona antes de decidir
    "v2": (
        "Dado el siguiente documento y la pregunta, determina si el documento contiene "
        "información útil para responder la pregunta.\n\n"
        "Documento: {document}\n"
        "Pregunta: {query}\n\n"
        "Primero identifica de qué trata el documento en una frase. "
        "Luego decide si esa información ayuda a responder la pregunta. "
        'Termina tu respuesta con "Veredicto: si" o "Veredicto: no".'
    ),
}


def get_llm(num_predict: int = 10):
    """Devuelve el LLM de grading (Ollama Qwen 2.5 3B).

    num_predict=10 es suficiente para respuestas directas (si/no).
    Para Chain of Thought se necesitan más tokens para el razonamiento.
    """
    from langchain_ollama import ChatOllama
    return ChatOllama(model="qwen2.5:3b", temperature=0, num_predict=num_predict)


def predict_label(llm, prompt_template: str, query: str, document: str) -> str:
    """Devuelve 'si' o 'no' según el prompt de grading.

    Soporta respuestas directas ("si"/"no") y respuestas con veredicto
    al final ("Veredicto: si") como las que genera la v2 Chain of Thought.
    """
    prompt = prompt_template.format(document=document, query=query)
    response = llm.invoke(prompt)
    answer = response.content.strip().lower()

    # v2 responde con "veredicto: si/no" al final
    if "veredicto:" in answer:
        verdict = answer.split("veredicto:")[-1].strip()
        return "si" if verdict.startswith("si") or verdict.startswith("sí") else "no"

    return "si" if answer.startswith("si") or answer.startswith("sí") else "no"


def evaluate(variant: str = "v0") -> dict:
    """Corre el prompt indicado contra el test set y calcula métricas."""
    prompt_template = GRADING_PROMPTS[variant]

    with open(TEST_SET_PATH, encoding="utf-8") as f:
        test_set = json.load(f)

    logger.info("Cargando Ollama...")
    # v2 necesita más tokens para generar el razonamiento antes del veredicto
    num_predict = 150 if variant == "v2" else 10
    llm = get_llm(num_predict=num_predict)

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
        help="Variante del prompt a evaluar: v0 (baseline), v1 (few-shot), v2 (chain of thought)",
    )
    args = parser.parse_args()
    evaluate(variant=args.variant)
