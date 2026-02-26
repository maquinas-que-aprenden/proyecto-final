"""conftest.py — Configuración global de pytest para NormaBot.

Añade la raíz del proyecto al sys.path para que los imports del estilo
``from src.classifier.main import predict_risk`` funcionen sin necesidad
de instalar el paquete en modo editable.

pytest carga este archivo automáticamente antes de ejecutar cualquier test.
"""

import os
import sys
from pathlib import Path

# Inserta la raíz del proyecto al principio de sys.path.
# Path(__file__).parent  →  tests/
# .parent                →  proyecto-final/  (raíz del repo)
sys.path.insert(0, str(Path(__file__).parent.parent))

# Desactiva Langfuse en tests: los @observe en predict_risk, retrieve, etc.
# no envían trazas durante pytest (evita dependencia de keys en CI).
os.environ.setdefault("LANGFUSE_ENABLED", "false")
