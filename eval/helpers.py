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
# Métricas del retriever (Phase A): sólo necesitan {question, contexts, ground_truth}.
THRESHOLDS_RETRIEVER = {
    "context_precision": 0.70,
    "context_recall": 0.70,
}
# Métricas E2E (Phase B): necesitan la respuesta generada por el agente.
THRESHOLDS_E2E = {
    "faithfulness": 0.80,
    # answer_relevancy excluida: Nova Lite no sigue el prompt de RAGAS
    # (devuelve JSON incompleto sin el campo "question"), lo que produce NaN siempre.
}
# Umbrales combinados para check_thresholds() y logging.
THRESHOLDS = {**THRESHOLDS_RETRIEVER, **THRESHOLDS_E2E}

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

def get_retriever_rows(dataset: list[dict]) -> list[dict]:
    """Recupera y clasifica documentos para cada pregunta sin invocar al agente.

    Produce las filas de Phase A: {question, contexts, ground_truth}.
    No requiere credenciales de Bedrock.

    Returns:
        Lista de dicts con question, contexts, ground_truth.
    """
    try:
        from src.rag.main import retrieve, grade
    except ImportError as exc:
        # Sin el módulo RAG no podemos evaluar el retriever en absoluto.
        # Usar contextos estáticos del dataset contaminaría Context Precision/Recall
        # con datos gold, invalidando Phase A por completo.
        raise RuntimeError(
            "Módulo src.rag.main no disponible. "
            "Instala las dependencias de RAG antes de ejecutar la evaluación del retriever."
        ) from exc

    total = len(dataset)
    rows = []
    for idx, item in enumerate(dataset, 1):
        question = item["question"]
        try:
            docs = retrieve(question)
            relevant = grade(question, docs)
            # Lista vacía si grade() no clasifica ningún doc como relevante:
            # RAGAS puntuará precision=0 / recall=0, que refleja correctamente
            # el resultado del retriever. No usar item["contexts"] como fallback
            # porque contaminaría las métricas con datos gold.
            contexts = [d["doc"] for d in relevant]
            logger.info(
                "[%d/%d] %d/%d docs relevantes — %s",
                idx, total, len(relevant), len(docs), question[:80],
            )
        except Exception as exc:
            # No usar contextos estáticos como fallback: contaminarían las métricas
            # del retriever con datos gold y harían que Phase A fuera engañosa.
            raise RuntimeError(
                f"Error en retrieval para '{question[:80]}': {exc}"
            ) from exc

        rows.append({
            "question": question,
            "contexts": contexts,
            "ground_truth": item["ground_truth"],
        })

    return rows


def get_agent_answers(
    dataset: list[dict],
    retriever_rows: list[dict] | None = None,
) -> list[dict]:
    """Invoca el agente para cada pregunta del dataset y recoge la respuesta.

    Args:
        dataset: Ejemplos de eval/dataset.json.
        retriever_rows: Filas de Phase A con contextos ya recuperados. Si se
            proporciona, se reutilizan esos contextos para que Faithfulness se
            evalúe sobre los mismos documentos que Context Precision/Recall.

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

    # Indexar retriever_rows por pregunta para evitar alineación posicional frágil:
    # la caché podría tener distinto orden o longitud si el dataset cambió.
    retriever_index: dict[str, list[str]] = {}
    if retriever_rows is not None:
        for row in retriever_rows:
            retriever_index[row["question"]] = row["contexts"]

    total = len(dataset)
    rows = []
    for idx, item in enumerate(dataset, 1):
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

        # Reutilizar contextos de Phase A (lookup por pregunta) para garantizar que
        # Faithfulness se evalúa sobre los mismos documentos que Context Precision/Recall.
        if question in retriever_index:
            contexts = retriever_index[question]
        else:
            if retriever_rows is not None:
                logger.warning(
                    "Pregunta no encontrada en retriever_rows — regenerando contextos: '%s'",
                    question[:50],
                )
            # Fallback: recuperar contextos en línea si no hay Phase A disponible.
            contexts = item["contexts"]  # contextos estáticos del dataset
            if use_retriever:
                try:
                    docs = retrieve(question)
                    relevant = grade(question, docs)
                    if relevant:
                        contexts = [d["doc"] for d in relevant]
                except Exception:
                    logger.exception("Error en retrieval para '%s' — usando contextos estáticos", question[:50])

        source = "agente" if use_agent else "mock"
        logger.info(
            "[%d/%d] respuesta=%d chars, contextos=%d (%s) — %s",
            idx, total, len(answer), len(contexts), source, question[:80],
        )
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

    # 2. Desenvuelve {"properties": {...}, "type": "object", ...} → {...}
    # Nova Lite confunde el formato con JSON Schema y añade "type", "title",
    # "required", etc. La señal inequívoca es type=="object" + properties dict,
    # independientemente de cuántas claves extra tenga el wrapper.
    try:
        data = json.loads(text)
        if (
            isinstance(data, dict)
            and isinstance(data.get("properties"), dict)
            and data.get("type") == "object"
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

def run_ragas_retriever(ragas_dataset) -> dict:
    """Evalúa las métricas del retriever (Phase A): Context Precision y Context Recall.

    El dataset sólo necesita {question, contexts, ground_truth}; no se usa 'answer'.

    Returns:
        Dict con context_precision y context_recall (nanmean sobre todos los ejemplos).
    """
    from ragas import evaluate
    from ragas.metrics import ContextPrecision, ContextRecall

    ragas_llm = get_ragas_llm()

    logger.info("Phase A — calculando métricas del retriever (Context Precision, Context Recall)...")

    # Nota: ContextRecall depende de la calidad del ground_truth. Si el ground_truth
    # es incompleto o impreciso, el score puede ser engañoso aunque el retriever
    # recupere documentos correctos. Revisar los ejemplos del dataset si ContextRecall
    # da resultados inesperadamente bajos con un retriever aparentemente bueno.
    metrics = [
        ContextPrecision(llm=ragas_llm),
        ContextRecall(llm=ragas_llm),
    ]

    column_map = {
        "user_input": "question",
        "retrieved_contexts": "contexts",
        "reference": "ground_truth",
        # "response" no incluido: ContextPrecision/ContextRecall no lo usan.
    }

    from ragas import RunConfig

    try:
        results = evaluate(
            dataset=ragas_dataset,
            metrics=metrics,
            column_map=column_map,
            run_config=RunConfig(timeout=120, max_retries=3, max_workers=2),
        )
    except Exception as e:
        raise RuntimeError(f"Fallo crítico en Bedrock/Ragas (Phase A): {e}")

    questions = ragas_dataset["question"]
    for i, (q, cp, cr) in enumerate(
        zip(questions, results["context_precision"], results["context_recall"]), 1
    ):
        cp_s = f"{cp:.3f}" if not np.isnan(cp) else " NaN"
        cr_s = f"{cr:.3f}" if not np.isnan(cr) else " NaN"
        logger.info("  [%d] prec=%-5s  rec=%-5s  %s", i, cp_s, cr_s, q[:80])

    scores = {
        "context_precision": round(float(np.nanmean(results["context_precision"])), 4),
        "context_recall": round(float(np.nanmean(results["context_recall"])), 4),
    }
    nan_metrics = [k for k, v in scores.items() if np.isnan(v)]
    if nan_metrics:
        logger.warning("Métricas con NaN (Phase A): %s — se registran como NaN", nan_metrics)
    return scores


def run_ragas_e2e(ragas_dataset) -> dict:
    """Evalúa las métricas E2E (Phase B): Faithfulness.

    El dataset necesita {question, answer, contexts, ground_truth}.
    Los contextos deben ser los mismos que se usaron en Phase A para que
    Faithfulness y Context Precision/Recall sean comparables.

    Returns:
        Dict con faithfulness (nanmean sobre todos los ejemplos).
    """
    from ragas import evaluate
    from ragas.metrics import Faithfulness

    ragas_llm = get_ragas_llm()

    logger.info("Phase B — calculando métricas E2E (Faithfulness)...")

    # AnswerRelevancy excluida: Nova Lite no sigue el prompt de RAGAS para esta métrica,
    # El output parser falla tras reintentos (fix_output_format), produciendo NaN en todos los ejemplos.
    # No es parcheable con _fix_nova_json; requiere cambio de LLM.
    metrics = [Faithfulness(llm=ragas_llm)]

    column_map = {
        "user_input": "question",
        "response": "answer",
        "retrieved_contexts": "contexts",
        "reference": "ground_truth",
    }

    from ragas import RunConfig

    try:
        results = evaluate(
            dataset=ragas_dataset,
            metrics=metrics,
            column_map=column_map,
            run_config=RunConfig(timeout=120, max_retries=3, max_workers=2),
        )
    except Exception as e:
        raise RuntimeError(f"Fallo crítico en Bedrock/Ragas (Phase B): {e}")

    questions = ragas_dataset["question"]
    for i, (q, f) in enumerate(zip(questions, results["faithfulness"]), 1):
        f_s = f"{f:.3f}" if not np.isnan(f) else " NaN"
        logger.info("  [%d] faith=%-5s  %s", i, f_s, q[:80])

    scores = {
        "faithfulness": round(float(np.nanmean(results["faithfulness"])), 4),
    }
    nan_metrics = [k for k, v in scores.items() if np.isnan(v)]
    if nan_metrics:
        logger.warning("Métricas con NaN (Phase B): %s — se registran como NaN", nan_metrics)
    return scores

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


def save_answers_cache(rows: list[dict], git_sha: str, suffix: str = "") -> Path:
    """Guarda filas en caché para evitar re-ejecutar el retriever o el agente.

    Args:
        suffix: Etiqueta que distingue la caché de Phase A ("retriever") de
            la de Phase B ("e2e"). Deja vacío para compatibilidad con código
            anterior que no usa el parámetro.
    """
    tag = f"_{suffix}" if suffix else ""
    cache_path = Path(__file__).parent / f"answers_cache_{git_sha[:8]}{tag}.json"
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({"git_sha": git_sha, "rows": rows}, f, ensure_ascii=False, indent=2)
    logger.info("Caché guardada en %s", cache_path)
    return cache_path


def load_answers_cache(git_sha: str, suffix: str = "") -> list[dict] | None:
    """Carga caché si existe y coincide el SHA. Devuelve None si no hay caché.

    Args:
        suffix: Debe coincidir con el usado en save_answers_cache()
            ("retriever" para Phase A, "e2e" para Phase B).
    """
    tag = f"_{suffix}" if suffix else ""
    cache_path = Path(__file__).parent / f"answers_cache_{git_sha[:8]}{tag}.json"
    if not cache_path.exists():
        return None
    with open(cache_path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("git_sha") != git_sha:
        logger.warning("Caché obsoleta (SHA distinto) — ignorando")
        return None
    logger.info("Caché cargada: %d filas (SHA: %s, suffix=%r)", len(data["rows"]), git_sha[:8], suffix)
    return data["rows"]


def check_thresholds(metrics: dict) -> list[str]:
    """Comprueba si alguna métrica está por debajo del umbral.

    Returns:
        Lista de mensajes de error (vacía si todo OK).
    """
    failures = []
    for metric, threshold in THRESHOLDS.items():
        if metric not in metrics:
            # Métrica no producida en esta ejecución (p.ej. faithfulness con --retriever-only).
            continue
        value = metrics[metric]
        if np.isnan(value):
            failures.append(f"{metric}: NaN (métrica no calculada correctamente)")
        elif value < threshold:
            failures.append(f"{metric}: {value:.4f} < {threshold} (umbral mínimo)")
    return failures