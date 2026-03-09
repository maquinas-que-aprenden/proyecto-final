"""
Umbrales (KPIs del proyecto):
    faithfulness      >= 0.80   (Phase B — E2E)
    context_precision >= 0.70   (Phase A — retriever)
    context_recall    >= 0.70   (Phase A — retriever)

Variables de entorno necesarias:
    MLFLOW_TRACKING_URI       → http://<ip-mlflow>:5000
    MLFLOW_TRACKING_USERNAME  → tracker
    MLFLOW_TRACKING_PASSWORD  → (credenciales MLflow)
    AWS_REGION                → eu-west-1
    BEDROCK_MODEL_ID          → eu.amazon.nova-lite-v1:0
    AWS_ACCESS_KEY_ID         → (credenciales Bedrock)
    AWS_SECRET_ACCESS_KEY     → (credenciales Bedrock)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

import numpy as np

from helpers import (
    load_dataset,
    get_retriever_rows,
    get_agent_answers,
    build_ragas_dataset,
    run_ragas_retriever,
    run_ragas_e2e,
    log_to_mlflow,
    log_to_langfuse,
    check_thresholds,
    save_answers_cache,
    load_answers_cache,
    THRESHOLDS_RETRIEVER,
    THRESHOLDS_E2E,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)


def main(ci_mode: bool = False, retriever_only: bool = False) -> int:
    """Ejecuta la evaluación RAGAS en dos fases.

    Phase A (retriever): Context Precision + Context Recall.
        No requiere Bedrock — sólo ChromaDB + Ollama.
    Phase B (E2E): Faithfulness.
        Reutiliza los contextos de Phase A para que ambas fases sean comparables.

    Args:
        ci_mode: Si True, falla con exit code 1 si alguna métrica no supera el umbral.
        retriever_only: Si True, salta Phase B. Útil en entornos sin Bedrock.

    Returns:
        0 si todo OK, 1 si alguna métrica falla el umbral (bloquea CI).
    """
    logger.info("=== NormaBot — Evaluación RAGAS ===")

    git_sha = os.getenv("GITHUB_SHA", "local")

    # 1. Cargar dataset
    dataset = load_dataset()

    # ── Phase A: Retriever (Context Precision + Context Recall) ──────────────
    retriever_rows = load_answers_cache(git_sha, suffix="retriever")
    if retriever_rows is None:
        retriever_rows = get_retriever_rows(dataset)
        save_answers_cache(retriever_rows, git_sha, suffix="retriever")

    try:
        retriever_metrics = run_ragas_retriever(build_ragas_dataset(retriever_rows))
    except Exception as e:
        logger.error("Error en Phase A (retriever): %s", e)
        if ci_mode:
            return 1
        retriever_metrics = {"context_precision": float("nan"), "context_recall": float("nan")}

    # ── Phase B: E2E — Faithfulness ──────────────────────────────────────────
    e2e_metrics: dict = {}
    if not retriever_only:
        # Phase B reutiliza los contextos de Phase A para garantizar coherencia:
        # Faithfulness se mide sobre los mismos documentos que Context Precision/Recall.
        e2e_rows = load_answers_cache(git_sha, suffix="e2e")
        if e2e_rows is None:
            e2e_rows = get_agent_answers(dataset, retriever_rows=retriever_rows)
            save_answers_cache(e2e_rows, git_sha, suffix="e2e")

        try:
            e2e_metrics = run_ragas_e2e(build_ragas_dataset(e2e_rows))
        except Exception as e:
            logger.error("Error en Phase B (E2E): %s", e)
            if ci_mode:
                return 1
            e2e_metrics = {"faithfulness": float("nan")}

    # ── Resultados ────────────────────────────────────────────────────────────
    all_metrics = {**retriever_metrics, **e2e_metrics}

    logger.info("─" * 40)
    logger.info("Resultados RAGAS:")
    logger.info("  [Phase A — Retriever]")
    for metric, value in retriever_metrics.items():
        threshold = THRESHOLDS_RETRIEVER.get(metric, 0)
        status = "✓" if value >= threshold else "✗"
        logger.info("    %s %-25s %.4f  (umbral: %.2f)", status, metric, value, threshold)
    if e2e_metrics:
        logger.info("  [Phase B — E2E]")
        for metric, value in e2e_metrics.items():
            threshold = THRESHOLDS_E2E.get(metric, 0)
            status = "✓" if value >= threshold else "✗"
            logger.info("    %s %-25s %.4f  (umbral: %.2f)", status, metric, value, threshold)
    logger.info("─" * 40)

    # ── Observabilidad ────────────────────────────────────────────────────────
    try:
        log_to_mlflow(all_metrics, n_examples=len(dataset), git_sha=git_sha)
    except Exception as e:
        logger.warning("No se pudo conectar con MLflow: %s", e)
        if ci_mode:
            logger.warning("Continuando sin MLflow en CI...")

    try:
        log_to_langfuse(all_metrics, n_examples=len(dataset), git_sha=git_sha)
    except Exception as e:
        logger.warning("No se pudo conectar con Langfuse: %s", e)

    # ── Umbrales ──────────────────────────────────────────────────────────────
    failures = check_thresholds(all_metrics)
    if failures:
        logger.error("Métricas por debajo del umbral:")
        for f in failures:
            logger.error("  ✗ %s", f)
        if ci_mode:
            logger.error("CI bloqueado — corrige el RAG antes de mergear.")
            return 1
        else:
            logger.warning("Ejecución local — no se bloquea, pero revisa el RAG.")

    logger.info("✓ Evaluación completada")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluación RAGAS de NormaBot")
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Modo CI: falla con exit code 1 si alguna métrica no supera el umbral",
    )
    parser.add_argument(
        "--retriever-only",
        action="store_true",
        help="Salta Phase B (Faithfulness). Útil en entornos sin Bedrock.",
    )
    args = parser.parse_args()
    sys.exit(main(ci_mode=args.ci, retriever_only=args.retriever_only))
