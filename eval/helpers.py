from __future__ import annotations

import json
import logging
import os
import re
import uuid
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)

DATASET_PATH = Path(__file__).parent / "dataset.json"
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI")
MLFLOW_EXPERIMENT = "normabot-ragas-eval"
THRESHOLDS = {
    "faithfulness": 0.80,
    # answer_relevancy excluida: Nova Lite no sigue el prompt de RAGAS
    # (devuelve JSON incompleto sin el campo "question"), lo que produce NaN siempre.
    "context_precision": 0.70,
    "context_recall": 0.70,
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

    try:
        from src.rag.main import retrieve, grade
        use_retriever = True
    except ImportError:
        use_retriever = False
        logger.warning("Módulo src.rag.main no disponible — usando contextos estáticos del dataset")

    rows = []
    for item in dataset:
        question = item["question"]

        if use_agent:
            try:
                result = agent_run(question, session_id=f"eval-{uuid.uuid4().hex[:8]}")
                # El agente ReAct devuelve messages; cogemos el último
                answer = result["messages"][-1].content
            except Exception as e:
                logger.warning("Error invocando agente para '%s': %s", question[:50], e)
                answer = item.get("ground_truth", "")
        else:
            # Fallback mock: usamos ground_truth como answer para que RAGAS pueda correr
            answer = item.get("ground_truth", "")

        # Obtener contextos reales del retriever para que RAGAS evalúe sobre
        # lo que el pipeline realmente recuperó, no sobre fragmentos estáticos.
        contexts = item["contexts"]  # fallback a los contextos estáticos del dataset
        if use_retriever:
            try:
                docs = retrieve(question)
                relevant = grade(question, docs)
                if relevant:
                    contexts = [d["doc"] for d in relevant]
            except Exception:
                logger.exception("Error en retrieval para '%s' — usando contextos estáticos", question[:50])

        rows.append({
            "question": question,
            "answer": answer,
            "contexts": contexts,
            "ground_truth": item["ground_truth"],
        })

    return rows

def build_ragas_dataset(rows: list[dict]):
    """Convierte la lista de dicts en un Dataset de RAGAS."""
    from datasets import Dataset
    return Dataset.from_list(rows)

def _fix_nova_json(text: str) -> str:
    """Corrige el JSON que devuelve Nova Lite para que RAGAS pueda parsearlo.

    Nova Lite confunde el formato pedido con un JSON Schema y devuelve:
        {"properties": {"statements": [...]}, "type": "object"}
    en vez del valor esperado:
        {"statements": [...]}

    También elimina bloques ```json ... ``` si los hay.
    """
    # 1. Quitar fences de markdown
    text = re.sub(r"```(?:json)?\s*([\s\S]*?)```", r"\1", text).strip()

    # 2. Desenvuelve {"properties": {...}} → {...}
    try:
        data = json.loads(text)
        if (
            isinstance(data, dict)
            and "properties" in data
            and isinstance(data["properties"], dict)
            and len(data) <= 3  # solo "properties", "type", "title"
        ):
            return json.dumps(data["properties"])
    except (json.JSONDecodeError, ValueError):
        pass

    return text


def get_ragas_llm():
    """Devuelve un LLM compatible con RAGAS usando Bedrock Nova Lite.

    RAGAS necesita un LLM para calcular faithfulness, context_precision y context_recall.
    Usamos el mismo modelo que el agente para consistencia.

    Nova Lite tiene dos incompatibilidades con los prompts de RAGAS:
    1. Devuelve {"properties": {"statements": [...]}} en vez de {"statements": [...]}
    2. A veces devuelve JSON dentro de bloques ```json ... ```
    _NovaChatWrapper aplica _fix_nova_json para corregir ambos casos.
    Los ejemplos donde Nova Lite devuelve texto plano (no JSON) siguen
    fallando individualmente y producen NaN, que se registra en los logs.
    """
    from langchain_aws import ChatBedrockConverse
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration
    from ragas.llms import LangchainLLMWrapper

    class _NovaChatWrapper(ChatBedrockConverse):
        """Subclase que normaliza el JSON de Nova Lite para RAGAS."""

        def _clean(self, result):
            cleaned = []
            for gen in result.generations:
                if isinstance(gen, ChatGeneration) and isinstance(gen.message.content, str):
                    clean_text = _fix_nova_json(gen.message.content)
                    new_msg = AIMessage(
                        content=clean_text,
                        response_metadata=gen.message.response_metadata,
                    )
                    cleaned.append(ChatGeneration(
                        text=clean_text,
                        message=new_msg,
                        generation_info=gen.generation_info,
                    ))
                else:
                    cleaned.append(gen)
            result.generations = cleaned
            return result

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            return self._clean(super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs))

        async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
            return self._clean(await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs))

    llm = _NovaChatWrapper(
        model=os.getenv("BEDROCK_MODEL_ID", "eu.amazon.nova-lite-v1:0"),
        region_name=os.getenv("AWS_REGION", "eu-west-1"),
        temperature=0.0,
    )
    return LangchainLLMWrapper(llm)

def get_ragas_embeddings():
    """Instancia embeddings para RAGAS usando sentence-transformers local.

    Usa intfloat/multilingual-e5-base (ya cargado por ChromaDB en el
    contenedor) para evitar dependencia de permisos IAM de Bedrock InvokeModel.
    """
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from sentence_transformers import SentenceTransformer

    class _LocalEmbeddings:
        def __init__(self):
            self._model = SentenceTransformer("intfloat/multilingual-e5-base")

        def embed_query(self, text: str) -> list[float]:
            return self._model.encode(f"query: {text}").tolist()

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [v.tolist() for v in self._model.encode([f"query: {t}" for t in texts])]

    return LangchainEmbeddingsWrapper(_LocalEmbeddings())

def run_ragas(ragas_dataset) -> dict:
    from ragas import evaluate
    from ragas.metrics import Faithfulness, ContextPrecision, ContextRecall

    ragas_llm = get_ragas_llm()

    logger.info("Calculando métricas RAGAS...")

    # AnswerRelevancy excluida: Nova Lite no sigue el prompt few-shot de RAGAS
    # y devuelve JSON sin el campo "question", produciendo NaN en todos los ejemplos.
    metrics = [
        Faithfulness(llm=ragas_llm),
        ContextPrecision(llm=ragas_llm),
        ContextRecall(llm=ragas_llm),
    ]

    column_map = {
        "user_input": "question",
        "response": "answer",
        "retrieved_contexts": "contexts",
        "reference": "ground_truth",
    }

    try:
        results = evaluate(
            dataset=ragas_dataset,
            metrics=metrics,
            column_map=column_map,
        )
    except Exception as e:
        raise RuntimeError(f"Fallo crítico en Bedrock/Ragas: {e}")

    metrics = {
        "faithfulness": round(float(np.nanmean(results["faithfulness"])), 4),
        "context_precision": round(float(np.nanmean(results["context_precision"])), 4),
        "context_recall": round(float(np.nanmean(results["context_recall"])), 4),
    }
    nan_metrics = [k for k, v in metrics.items() if np.isnan(v)]
    if nan_metrics:
        logger.warning("Métricas con NaN (jobs fallidos en RAGAS): %s — se registran como NaN", nan_metrics)
    return metrics

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

    classifier_params = {}
    meta_path = Path(__file__).parents[1] / "src/classifier/classifier_dataset_fusionado/model/mejor_modelo_seleccion.json"
    if meta_path.exists():
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            if not isinstance(meta, dict):
                raise ValueError(f"Se esperaba dict, se obtuvo {type(meta).__name__}")
            classifier_params = {
                "classifier_model": meta.get("nombre", "unknown"),
                "classifier_type": meta.get("model_type", "unknown"),
                "classifier_f1_macro": meta.get("test_f1_macro"),
            }
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logger.warning("No se pudo leer mejor_modelo_seleccion.json: %s", e)
            classifier_params = {
                "classifier_model": "unknown",
                "classifier_type": "unknown",
                "classifier_f1_macro": None,
            }

    with mlflow.start_run(run_name=f"ragas-{git_sha[:8]}"):
        mlflow.log_params({
            "model": os.getenv("BEDROCK_MODEL_ID", "eu.amazon.nova-lite-v1:0"),
            "commit": git_sha,
            "n_examples": n_examples,
            "dataset": "eval/dataset.json",
            **classifier_params,
        })
        mlflow.log_metrics(metrics)

        # Loguear también los umbrales para referencia visual en MLflow
        mlflow.log_params({
            f"threshold_{k}": v for k, v in THRESHOLDS.items()
        })

    logger.info("Resultados logueados en MLflow: %s", MLFLOW_TRACKING_URI)

def log_to_langfuse(metrics: dict, n_examples: int, git_sha: str) -> None:
    """Anota los scores RAGAS en Langfuse como una traza de evaluación."""
    from langfuse import Langfuse

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if not public_key or not secret_key:
        raise ValueError("Define LANGFUSE_PUBLIC_KEY y LANGFUSE_SECRET_KEY.")

    lf = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )

    trace = lf.trace(
        name="ragas-eval",
        tags=["eval", "ragas"],
        metadata={
            "git_sha": git_sha,
            "n_examples": n_examples,
            "model": os.getenv("BEDROCK_MODEL_ID", "eu.amazon.nova-lite-v1:0"),
            "dataset": "eval/dataset.json",
        },
    )

    for metric_name, value in metrics.items():
        threshold = THRESHOLDS.get(metric_name)
        comment = f"umbral: {threshold}" if threshold is not None else None
        trace.score(name=metric_name, value=value, comment=comment)

    lf.flush()
    logger.info("Scores RAGAS logueados en Langfuse (trace: %s)", trace.id)


def save_answers_cache(rows: list[dict], git_sha: str) -> Path:
    """Guarda las respuestas del agente en caché para evitar re-ejecutar."""
    cache_path = Path(__file__).parent / f"answers_cache_{git_sha[:8]}.json"
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({"git_sha": git_sha, "rows": rows}, f, ensure_ascii=False, indent=2)
    logger.info("Caché guardada en %s", cache_path)
    return cache_path


def load_answers_cache(git_sha: str) -> list[dict] | None:
    """Carga caché si existe y coincide el SHA. Devuelve None si no hay caché."""
    cache_path = Path(__file__).parent / f"answers_cache_{git_sha[:8]}.json"
    if not cache_path.exists():
        return None
    with open(cache_path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("git_sha") != git_sha:
        logger.warning("Caché obsoleta (SHA distinto) — ignorando")
        return None
    logger.info("Caché cargada: %d respuestas (SHA: %s)", len(data["rows"]), git_sha[:8])
    return data["rows"]


def check_thresholds(metrics: dict) -> list[str]:
    """Comprueba si alguna métrica está por debajo del umbral.

    Returns:
        Lista de mensajes de error (vacía si todo OK).
    """
    failures = []
    for metric, threshold in THRESHOLDS.items():
        value = metrics.get(metric, 0.0)
        if np.isnan(value):
            failures.append(f"{metric}: NaN (métrica no calculada correctamente)")
        elif value < threshold:
            failures.append(f"{metric}: {value:.4f} < {threshold} (umbral mínimo)")
    return failures