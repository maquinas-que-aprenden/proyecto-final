"""observability/langfuse_compat.py — Import opcional de langfuse decorators.

Centraliza el patron try/except para que los modulos no lo dupliquen.
Si langfuse esta instalado, exporta observe y langfuse_context reales.
Si no, exporta no-ops transparentes.
"""

try:
    from langfuse.decorators import observe, langfuse_context
except ImportError:
    def observe(name=None):  # type: ignore[misc]
        def decorator(func):
            return func
        return decorator

    class _NoOpLangfuse:
        def update_current_observation(self, **kwargs): pass
        def score_current_trace(self, **kwargs): pass

    langfuse_context = _NoOpLangfuse()  # type: ignore[assignment]

__all__ = ["observe", "langfuse_context"]
