"""Back-translation ES → EN → ES para aumentación del dataset.

Usa Google Translate via deep-translator (ya en requirements/ml.txt).
El round-trip introduce variación léxica natural sin alterar el significado.
"""

from __future__ import annotations

import logging

from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)


def back_translate(text: str, via: str = "en") -> str | None:
    """Traduce text de español a ``via`` y de vuelta a español.

    Parameters
    ----------
    text : str
        Texto en español.
    via : str
        Idioma intermedio (por defecto inglés).

    Returns
    -------
    str | None
        Texto retraducido al español.
        ``""``   → traducción exitosa pero sin variación léxica respecto al original.
        ``None`` → error en la llamada al traductor (distinguible de sin-variación).
    """
    try:
        en = GoogleTranslator(source="es", target=via).translate(text)
        es = GoogleTranslator(source=via, target="es").translate(en)
        return es if es and es != text else ""  # "" = sin variación léxica
    except Exception:
        logger.exception("Error en back-translation para '%s...'", text[:40])
        return None  # None = error, distinguible de "" (sin variación)
