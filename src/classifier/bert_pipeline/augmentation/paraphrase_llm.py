"""Paráfrasis de textos usando AWS Bedrock (Nova Lite) para aumentación del dataset.

Mantiene el nivel de riesgo EU AI Act intacto — solo varía el vocabulario y
la estructura de la oración para reducir la dependencia léxica del clasificador.
"""

from __future__ import annotations

import logging
import os

import boto3

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "bedrock-runtime",
            region_name=os.getenv("AWS_REGION", "eu-west-1"),
        )
    return _client


def paraphrase(text: str, n: int = 3, label: str = "") -> list[str]:
    """Genera n paráfrasis de text usando Bedrock Nova Lite.

    Parameters
    ----------
    text : str
        Descripción original del sistema de IA.
    n : int
        Número de paráfrasis a generar.
    label : str
        Etiqueta de riesgo del ejemplo (se incluye en el prompt como ancla).

    Returns
    -------
    list[str]
        Lista de hasta n paráfrasis. En caso de error devuelve el texto original repetido.
    """
    label_hint = f" (categoría EU AI Act: {label})" if label else ""
    prompt = (
        f"Reescribe el siguiente texto de {n} formas diferentes{label_hint}.\n\n"
        "Reglas estrictas:\n"
        "- Mantén exactamente el mismo tipo de sistema de IA y sus funcionalidades\n"
        "- NO cambies las características que determinan el nivel de riesgo\n"
        "- Usa vocabulario y estructura sintáctica distintos al original\n"
        "- Escribe en español\n"
        "- Longitud similar al original\n\n"
        f"Devuelve ÚNICAMENTE las {n} reescrituras, una por línea, sin numeración "
        "ni explicaciones adicionales.\n\n"
        f"Texto original: {text}"
    )

    model_id = os.getenv("BEDROCK_MODEL_ID", "eu.amazon.nova-lite-v1:0")

    try:
        response = _get_client().converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 1024, "temperature": 0.8},
        )
        raw = response["output"]["message"]["content"][0]["text"]
        lines = [line.strip() for line in raw.strip().splitlines() if line.strip()]
        # Filtrar líneas que sean idénticas al original o demasiado cortas
        valid = [ln for ln in lines if ln != text and len(ln) > 20]
        return valid[:n]
    except Exception as e:
        logger.warning("Error en paráfrasis LLM para '%s...': %s", text[:40], e)
        return []
