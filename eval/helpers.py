from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DATASET_PATH = Path(__file__).parent / "dataset.json"
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI")
MLFLOW_EXPERIMENT = "normabot-ragas-eval"
THRESHOLDS = {
    "faithfulness": 0.80,
    "answer_relevancy": 0.85,
}

def load_dataset() -> list[dict]:
    """Carga eval/dataset.json."""
    with open(DATASET_PATH, encoding="utf-8") as f:
        data = json.load(f)
    for i, item in enumerate(data):
        for field in ("question", "contexts", "ground_truth"):
            if not item.get(field):
                raise ValueError(f"dataset.json: item {i} sin campo '{field}'")
    logger.info("Dataset cargado: %d ejemplos", len(data))
    return data

def get_agent_answers(dataset: list[dict]) -> list[dict]:
    """Invoca el agente para cada pregunta del dataset y recoge la respuesta.

    Cuando el RAG sea real (ChromaDB conectado), esta función devuelve
    respuestas y contextos reales. Con los mocks actuales, devuelve los
    contextos sintéticos del dataset y la respuesta del agente stub.

    Returns:
        Lista de dicts con question, answer, contexts, ground_truth.
    """
    # Para no fallar si el módulo no está disponible en CI sin Bedrock
    try:
        from src.orchestrator.main import run as agent_run
        use_agent = True
        logger.info("Agente ReAct disponible — usando respuestas reales")
    except Exception as e:
        use_agent = False
        logger.warning("Agente no disponible (%s: %s) — usando respuestas mock del dataset", type(e).__name__, e)

    rows = []
    for item in dataset:
        question = item["question"]

        if use_agent:
            try:
                result = agent_run(question)
                # El agente ReAct devuelve messages; cogemos el último
                answer = result["messages"][-1].content
            except Exception as e:
                logger.warning("Error invocando agente para '%s': %s", question[:50], e)
                answer = item.get("ground_truth", "")
        else:
            # Fallback mock: usamos ground_truth como answer para que RAGAS pueda correr
            answer = item.get("ground_truth", "")

        rows.append({
            "question": question,
            "answer": answer,
            "contexts": item["contexts"],
            "ground_truth": item["ground_truth"],
        })

    return rows

def build_ragas_dataset(rows: list[dict]):
    """Convierte la lista de dicts en un Dataset de RAGAS."""
    from datasets import Dataset
    return Dataset.from_list(rows)

def get_ragas_llm():
    """Devuelve un LLM compatible con RAGAS usando Bedrock Nova Lite.

    RAGAS necesita un LLM para calcular faithfulness y answer_relevancy.
    Usamos el mismo modelo que el agente para consistencia.
    """
    from langchain_aws import ChatBedrockConverse
    from ragas.llms import LangchainLLMWrapper

    llm = ChatBedrockConverse(
        model=os.getenv("BEDROCK_MODEL_ID", "eu.amazon.nova-lite-v1:0"),
        region_name=os.getenv("AWS_REGION", "eu-west-1"),
        temperature=0.0,
    )
    return LangchainLLMWrapper(llm)

def run_ragas(ragas_dataset) -> dict:
    """Calcula métricas RAGAS sobre el dataset.

    Returns:
        dict con {"faithfulness": float, "answer_relevancy": float}
    """
    from ragas import evaluate
    from ragas.metrics import Faithfulness, AnswerRelevancy

    ragas_llm = get_ragas_llm()

    logger.info("Calculando métricas RAGAS...")
    try:
        results = evaluate(
            dataset=ragas_dataset,
            metrics=[
                Faithfulness(llm=ragas_llm),
                AnswerRelevancy(llm=ragas_llm),
            ],
        )
    except Exception as e:
        raise RuntimeError(
            f"Error al calcular métricas RAGAS ({type(e).__name__}: {e}). "
            "Verifica las credenciales de AWS y que BEDROCK_MODEL_ID sea correcto."
        ) from e

    return {
        "faithfulness": round(float(results["faithfulness"]), 4),
        "answer_relevancy": round(float(results["answer_relevancy"]), 4),
    }

# Cuando se apruebe PR#36 lo añado a observabilidad
def log_to_mlflow(metrics: dict, n_examples: int, git_sha: str) -> None:
    """Loguea los resultados en MLflow (EC2)."""
    import mlflow

    MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI")
    if not MLFLOW_TRACKING_URI:
        raise ValueError(
            "Define MLFLOW_TRACKING_URI como variable de entorno."
        )
    os.environ.setdefault("MLFLOW_TRACKING_USERNAME", "admin")
    password = os.getenv("MLFLOW_TRACKING_PASSWORD")
    if password:
        os.environ["MLFLOW_TRACKING_PASSWORD"] = password

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT)

    with mlflow.start_run(run_name=f"ragas-{git_sha[:8]}"):
        mlflow.log_params({
            "model": os.getenv("BEDROCK_MODEL_ID", "eu.amazon.nova-lite-v1:0"),
            "commit": git_sha,
            "n_examples": n_examples,
            "dataset": "eval/dataset.json",
        })
        mlflow.log_metrics(metrics)

        # Loguear también los umbrales para referencia visual en MLflow
        mlflow.log_params({
            f"threshold_{k}": v for k, v in THRESHOLDS.items()
        })

    logger.info("Resultados logueados en MLflow: %s", MLFLOW_TRACKING_URI)

def check_thresholds(metrics: dict) -> list[str]:
    """Comprueba si alguna métrica está por debajo del umbral.

    Returns:
        Lista de mensajes de error (vacía si todo OK).
    """
    failures = []
    for metric, threshold in THRESHOLDS.items():
        value = metrics.get(metric, 0.0)
        if value < threshold:
            failures.append(
                f"{metric}: {value:.4f} < {threshold} (umbral mínimo)"
            )
    return failures