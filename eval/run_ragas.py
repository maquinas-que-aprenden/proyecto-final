"""
Umbrales (KPIs del proyecto):
    faithfulness      >= 0.80
    answer_relevancy  >= 0.85

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

from helpers import (
    load_dataset,
    get_agent_answers,
    build_ragas_dataset,
    run_ragas,
    log_to_mlflow,
    log_to_langfuse,
    check_thresholds,
    THRESHOLDS,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)


def main(ci_mode: bool = False) -> int:
    """Ejecuta la evaluación RAGAS completa.

    Returns:
        0 si todo OK, 1 si alguna métrica falla el umbral (bloquea CI).
    """
    logger.info("=== NormaBot — Evaluación RAGAS ===")

    # Git SHA para identificar el run en MLflow
    git_sha = os.getenv("GITHUB_SHA", "local")

    # 1. Cargar dataset
    dataset = load_dataset()

    # 2. Obtener respuestas del agente
    rows = get_agent_answers(dataset)

    # 3. Construir dataset RAGAS
    ragas_dataset = build_ragas_dataset(rows)

    # 4. Calcular métricas
    try:
        metrics = run_ragas(ragas_dataset)
    except Exception as e:
        logger.error("Error en la evaluación RAGAS: %s", e)
        if ci_mode:
            return 1
        metrics = {"faithfulness": 0.0, "answer_relevancy": 0.0, "context_precision": 0.0, "context_recall": 0.0}

    # 5. Mostrar resultados
    logger.info("─" * 40)
    logger.info("Resultados RAGAS:")
    for metric, value in metrics.items():
        threshold = THRESHOLDS.get(metric, 0)
        status = "✓" if value >= threshold else "✗"
        logger.info("  %s %-25s %.4f  (umbral: %.2f)", status, metric, value, threshold)
    logger.info("─" * 40)

    # 6. Loguear en MLflow
    try:
        log_to_mlflow(metrics, n_examples=len(rows), git_sha=git_sha)
    except Exception as e:
        logger.warning("No se pudo conectar con MLflow: %s", e)
        if ci_mode:
            logger.warning("Continuando sin MLflow en CI...")

    # 7. Anotar scores en Langfuse
    try:
        log_to_langfuse(metrics, n_examples=len(rows), git_sha=git_sha)
    except Exception as e:
        logger.warning("No se pudo conectar con Langfuse: %s", e)

    # 8. Comprobar umbrales (falla con exit code 1 si --ci)
    failures = check_thresholds(metrics)
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
    args = parser.parse_args()
    sys.exit(main(ci_mode=args.ci))
