"""finetuning/grader.py — Wrapper de inferencia para el RAG Grader fine-tuneado.

Carga el adaptador LoRA (QLoRA) sobre Qwen2.5-3B-Instruct y expone
predict_relevance() para el pipeline RAG de NormaBot.

Uso:
    from src.finetuning.grader import predict_relevance

    resultado = predict_relevance(query="...", document="...")
    # → "relevante" | "no relevante"
"""

from __future__ import annotations

import logging
from pathlib import Path

import torch

logger = logging.getLogger(__name__)

# Ruta al adaptador LoRA, relativa a la raíz del repo.
_ADAPTER_PATH = Path(__file__).parent / "model"

# Modelo base sobre el que se aplica el adaptador.
_BASE_MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"

LABEL_RELEVANTE    = "relevante"
LABEL_NO_RELEVANTE = "no relevante"

GRADING_SYSTEM_PROMPT = (
    "Eres un asistente especializado en normativa de inteligencia artificial. "
    "Tu tarea es determinar si un documento contiene información útil para responder "
    "una consulta sobre regulación de IA (EU AI Act, BOE, normativa española). "
    "Responde únicamente con 'relevante' o 'no relevante', sin explicación adicional."
)

# Singletons — se inicializan en la primera llamada.
_tokenizer = None
_model     = None


def _load_model():
    """Carga el tokenizador y el modelo con el adaptador LoRA (lazy, una vez)."""
    global _tokenizer, _model
    if _model is not None:
        return _tokenizer, _model

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import PeftModel
    except ImportError as exc:
        raise ImportError(
            "Faltan dependencias para el RAG Grader fine-tuneado.\n"
            "Instala con: pip install transformers peft bitsandbytes accelerate"
        ) from exc

    if not _ADAPTER_PATH.exists():
        raise FileNotFoundError(
            f"Adaptador LoRA no encontrado en {_ADAPTER_PATH.resolve()}.\n"
            "Descárgalo con: dvc pull src/finetuning/model/adapter_model.safetensors.dvc"
        )

    logger.info("Cargando tokenizador desde %s", _ADAPTER_PATH)
    tokenizer = AutoTokenizer.from_pretrained(str(_ADAPTER_PATH), trust_remote_code=True)
    tokenizer.pad_token    = tokenizer.eos_token
    tokenizer.padding_side = "right"

    use_gpu = torch.cuda.is_available()

    if use_gpu:
        logger.info("GPU detectada — cargando modelo en 4-bit NF4 (QLoRA)")
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
        base = AutoModelForCausalLM.from_pretrained(
            _BASE_MODEL_ID,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
        )
    else:
        logger.warning(
            "Sin GPU — cargando modelo en float32 (CPU). "
            "El grading sera significativamente más lento."
        )
        base = AutoModelForCausalLM.from_pretrained(
            _BASE_MODEL_ID,
            device_map="cpu",
            torch_dtype=torch.float32,
            trust_remote_code=True,
        )

    logger.info("Aplicando adaptador LoRA desde %s", _ADAPTER_PATH)
    model = PeftModel.from_pretrained(base, str(_ADAPTER_PATH))
    model.eval()

    _tokenizer = tokenizer
    _model     = model
    logger.info("RAG Grader fine-tuneado listo (dispositivo: %s)", next(model.parameters()).device)
    return _tokenizer, _model


def predict_relevance(query: str, document: str, max_new_tokens: int = 12) -> str:
    """Predice si un documento es relevante para responder una consulta.

    Args:
        query:          Consulta del usuario sobre normativa de IA.
        document:       Texto del documento recuperado por el retriever.
        max_new_tokens: Tokens máximos a generar (la respuesta es muy corta).

    Returns:
        "relevante" o "no relevante".
    """
    tokenizer, model = _load_model()

    messages = [
        {"role": "system", "content": GRADING_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Consulta: {query}\n\n"
                f"Documento: {document}\n\n"
                "¿Es este documento relevante para responder la consulta?"
            ),
        },
    ]
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )

    generated_ids = outputs[0][inputs["input_ids"].shape[1]:]
    response = tokenizer.decode(generated_ids, skip_special_tokens=True).strip().lower()

    if "no relevante" in response or "no es relevante" in response:
        return LABEL_NO_RELEVANTE
    if "relevante" in response:
        return LABEL_RELEVANTE

    # Respuesta inesperada — conservador: descartar documento.
    logger.warning("Respuesta inesperada del grader: %r — descartando documento", response)
    return LABEL_NO_RELEVANTE


def is_available() -> bool:
    """Comprueba si el adaptador LoRA está presente en disco."""
    safetensors = _ADAPTER_PATH / "adapter_model.safetensors"
    return safetensors.exists()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if not is_available():
        print("AVISO: adapter_model.safetensors no encontrado.")
        print("Ejecuta: dvc pull src/finetuning/model/adapter_model.safetensors.dvc")
    else:
        query    = "¿Qué prácticas de IA están prohibidas por el EU AI Act?"
        document = (
            "El artículo 5 del EU AI Act prohíbe sistemas de IA que utilicen "
            "técnicas subliminales para manipular el comportamiento de las personas "
            "de forma que pueda causarles daño."
        )
        resultado = predict_relevance(query, document)
        print(f"Query:     {query}")
        print(f"Documento: {document[:80]}...")
        print(f"Resultado: {resultado}")
        print("\n✓ grader.py OK")
