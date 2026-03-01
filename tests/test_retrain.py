"""test_retrain.py — Tests unitarios e integración del pipeline de reentrenamiento.

¿Qué se prueba?
===============
1. Helpers puros (sin I/O ni modelo):
   - ``_limpiar_texto``: tokenización, stopwords, entradas inválidas
   - ``_cargar_jsonl``: parseo del formato JSONL con cabeceras ``### Descripción:``
   - ``_crear_features_manuales``: forma del array de salida y detección de keywords

2. Integración ligera de ``main()``:
   - Escribe ficheros de datos sintéticos en ``tmp_path``
   - Monkeyparchea rutas y ``XGBClassifier`` con un stub (evita entrenamiento real)
   - Verifica que se generan los 4 artefactos .joblib + ``mejor_modelo_seleccion.json``
   - Verifica que el JSON contiene las claves esperadas

¿Cómo ejecutar?
===============
    pytest tests/test_retrain.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers de datos sintéticos
# ---------------------------------------------------------------------------

_LABELS = ["alto_riesgo", "inaceptable", "riesgo_limitado", "riesgo_minimo"]

_TRAIN_DESCRIPTIONS = {
    "alto_riesgo": [
        "sistema de scoring crediticio para préstamos bancarios",
        "herramienta de selección de candidatos para empleo",
        "sistema de diagnóstico médico asistido",
        "evaluación de solvencia para concesión de hipotecas",
        "predicción de recidiva para decisiones judiciales",
    ],
    "inaceptable": [
        "sistema de puntuación social de ciudadanos impuesto por el gobierno",
        "reconocimiento facial en espacios públicos en tiempo real",
        "manipulación subliminal de comportamiento de usuarios",
        "vigilancia biométrica masiva en transporte público",
        "sistema de inferencia de ideología política de ciudadanos",
    ],
    "riesgo_limitado": [
        "chatbot de atención al cliente para consultas frecuentes",
        "asistente de redacción de textos corporativos",
        "sistema de recomendación de contenidos con transparencia",
        "chatbot de soporte técnico para software empresarial",
        "asistente virtual de información turística",
    ],
    "riesgo_minimo": [
        "filtro de spam para correo electrónico corporativo",
        "sistema de recomendación de recetas de cocina",
        "juego de estrategia con IA para entretenimiento",
        "sensor industrial de detección de averías en maquinaria",
        "herramienta de gestión de logística y almacén",
    ],
}


def _make_jsonl(descriptions: dict[str, list[str]], path: Path) -> None:
    """Escribe fichero JSONL en el formato que consume _cargar_jsonl."""
    lines = []
    for label, texts in descriptions.items():
        for text in texts:
            lines.append(json.dumps({
                "text": f"### Descripción: {text} ### Clasificación: {label}",
                "etiqueta": label,
            }, ensure_ascii=False))
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Grupo 1: Unit tests de _limpiar_texto
# ---------------------------------------------------------------------------

class TestLimpiarTexto:
    """Tokenización básica sin spaCy."""

    def test_elimina_stopwords(self):
        from src.classifier.retrain import _limpiar_texto
        result = _limpiar_texto("El sistema de scoring crediticio para los bancos")
        assert "el" not in result.split()
        assert "los" not in result.split()
        assert "para" not in result.split()

    def test_conserva_palabras_relevantes(self):
        from src.classifier.retrain import _limpiar_texto
        result = _limpiar_texto("scoring crediticio préstamos bancarios")
        assert "scoring" in result
        assert "crediticio" in result

    def test_entrada_vacia(self):
        from src.classifier.retrain import _limpiar_texto
        assert _limpiar_texto("") == ""

    def test_entrada_none(self):
        from src.classifier.retrain import _limpiar_texto
        assert _limpiar_texto(None) == ""  # type: ignore[arg-type]

    def test_elimina_palabras_cortas(self):
        from src.classifier.retrain import _limpiar_texto
        # Palabras < 3 chars no deben aparecer
        result = _limpiar_texto("IA es un sistema de riesgo")
        tokens = result.split()
        assert all(len(t) >= 3 for t in tokens)


# ---------------------------------------------------------------------------
# Grupo 2: Unit tests de _cargar_jsonl
# ---------------------------------------------------------------------------

class TestCargarJsonl:
    """Parseo del formato JSONL con extracción de descripción."""

    def test_carga_una_linea(self, tmp_path):
        from src.classifier.retrain import _cargar_jsonl
        p = tmp_path / "data.jsonl"
        p.write_text(
            '{"text": "### Descripción: Sistema de scoring ### Clasificación: alto_riesgo",'
            ' "etiqueta": "alto_riesgo"}\n',
            encoding="utf-8",
        )
        df = _cargar_jsonl(p)
        assert len(df) == 1
        assert df.iloc[0]["etiqueta"] == "alto_riesgo"
        assert "scoring" in df.iloc[0]["descripcion"]

    def test_ignora_lineas_vacias(self, tmp_path):
        from src.classifier.retrain import _cargar_jsonl
        p = tmp_path / "data.jsonl"
        p.write_text(
            '{"text": "### Descripción: Chatbot ### Clasificación: riesgo_limitado", "etiqueta": "riesgo_limitado"}\n'
            "\n"
            '{"text": "### Descripción: Filtro spam ### Clasificación: riesgo_minimo", "etiqueta": "riesgo_minimo"}\n',
            encoding="utf-8",
        )
        df = _cargar_jsonl(p)
        assert len(df) == 2

    def test_extrae_descripcion_desde_cabecera(self, tmp_path):
        from src.classifier.retrain import _cargar_jsonl
        p = tmp_path / "data.jsonl"
        p.write_text(
            '{"text": "### Descripción: Sistema de diagnóstico médico ### Clasificación: alto_riesgo",'
            ' "etiqueta": "alto_riesgo"}\n',
            encoding="utf-8",
        )
        df = _cargar_jsonl(p)
        assert "diagnóstico" in df.iloc[0]["descripcion"]
        assert "Clasificación" not in df.iloc[0]["descripcion"]


# ---------------------------------------------------------------------------
# Grupo 3: Unit tests de _crear_features_manuales
# ---------------------------------------------------------------------------

class TestCrearFeaturesManuales:
    """Forma del array y detección de keywords por clase."""

    def test_forma_correcta(self):
        from src.classifier.retrain import _crear_features_manuales, _KEYWORDS_DOMINIO
        texts = pd.Series(["scoring crediticio préstamo", "chatbot filtro spam"])
        result = _crear_features_manuales(texts)
        # 2 features base (num_palabras, num_chars) + n grupos keywords + 1 supervisión
        expected_cols = 2 + len(_KEYWORDS_DOMINIO) + 1
        assert result.shape == (2, expected_cols)

    def test_keywords_alto_riesgo_detectadas(self):
        from src.classifier.retrain import _crear_features_manuales
        texts = pd.Series(["solvencia préstamo crediticio"])
        result = _crear_features_manuales(texts)
        # index 3: kw_alto_riesgo (después de num_palabras, num_chars, kw_inaceptable)
        assert result[0, 3] >= 2  # solvencia + crediticio (o préstamo)

    def test_texto_vacio_no_lanza(self):
        from src.classifier.retrain import _crear_features_manuales
        texts = pd.Series([""])
        result = _crear_features_manuales(texts)
        assert result.shape[0] == 1
        assert result[0, 0] == 0  # num_palabras = 0


# ---------------------------------------------------------------------------
# Grupo 4: Integración de main()
# ---------------------------------------------------------------------------

class _FakeXGB:
    """Stub de XGBClassifier: no entrena, predice siempre la clase 0."""

    def __init__(self, **kwargs):
        pass

    def fit(self, X, y, sample_weight=None):
        self._n_classes = len(set(y))
        return self

    def predict(self, X):
        n = X.shape[0] if hasattr(X, "shape") else len(X)
        return np.zeros(n, dtype=int)


def _xgboost_disponible() -> bool:
    try:
        import xgboost  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _xgboost_disponible(), reason="xgboost no instalado en este entorno")
class TestMainIntegracion:
    """Ejecuta main() con datos sintéticos y stub del modelo XGBoost."""

    @pytest.fixture()
    def retrain_env(self, tmp_path, monkeypatch):
        """Prepara ficheros y monkeypatches para una ejecución aislada de main()."""
        import src.classifier.retrain as retrain

        # Estructura de directorios
        data_dir = tmp_path / "data" / "finetune"
        data_dir.mkdir(parents=True)
        aug_dir = tmp_path / "data"
        model_dir = tmp_path / "model"

        # train.jsonl — 5 ejemplos por clase
        _make_jsonl(_TRAIN_DESCRIPTIONS, data_dir / "train.jsonl")

        # test.jsonl — 2 ejemplos por clase
        test_descriptions = {k: v[:2] for k, v in _TRAIN_DESCRIPTIONS.items()}
        _make_jsonl(test_descriptions, data_dir / "test.jsonl")

        # annex3_aumentacion.csv
        pd.DataFrame({
            "descripcion": [
                "scoring crediticio para préstamos bancarios",
                "reconocimiento facial biométrico en espacio público",
            ],
            "etiqueta": ["alto_riesgo", "inaceptable"],
        }).to_csv(aug_dir / "annex3_aumentacion.csv", index=False)

        monkeypatch.setattr(retrain, "_TRAIN_JSONL", data_dir / "train.jsonl")
        monkeypatch.setattr(retrain, "_TEST_JSONL", data_dir / "test.jsonl")
        monkeypatch.setattr(retrain, "_AUGMENT_CSV", aug_dir / "annex3_aumentacion.csv")
        monkeypatch.setattr(retrain, "_MODEL_DIR", model_dir)
        monkeypatch.setattr(retrain, "XGBClassifier", _FakeXGB)

        return model_dir

    def test_artefactos_creados(self, retrain_env):
        """main() debe escribir los 4 .joblib cuando el modelo mejora."""
        import src.classifier.retrain as retrain
        model_dir = retrain_env

        retrain.main(force_promote=True)

        assert (model_dir / "modelo_xgboost.joblib").exists()
        assert (model_dir / "tfidf_vectorizer.joblib").exists()
        assert (model_dir / "svd_transformer.joblib").exists()
        assert (model_dir / "label_encoder.joblib").exists()

    def test_json_contiene_claves_esperadas(self, retrain_env):
        """mejor_modelo_seleccion.json debe tener las claves clave para predict_risk."""
        import src.classifier.retrain as retrain
        model_dir = retrain_env

        retrain.main(force_promote=True)

        meta = json.loads((model_dir / "mejor_modelo_seleccion.json").read_text(encoding="utf-8"))
        for key in ("test_f1_macro", "augmented", "augmented_examples",
                    "model_file", "needs_manual_features"):
            assert key in meta, f"Clave '{key}' ausente en mejor_modelo_seleccion.json"
        assert meta["augmented"] is True
        assert meta["augmented_examples"] == 2

    def test_no_promover_si_f1_no_mejora(self, retrain_env):
        """Si el F1 previo es mayor, no se deben sobreescribir los artefactos."""
        import src.classifier.retrain as retrain
        model_dir = retrain_env

        # Primera ejecución (fuerza promoción para tener un baseline alto)
        seleccion_path = model_dir / "mejor_modelo_seleccion.json"
        model_dir.mkdir(parents=True, exist_ok=True)
        seleccion_path.write_text(
            json.dumps({"test_f1_macro": 0.99}), encoding="utf-8"
        )

        retrain.main(force_promote=False)

        # El JSON no debe haber sido actualizado (f1 del stub < 0.99)
        meta = json.loads(seleccion_path.read_text(encoding="utf-8"))
        assert meta["test_f1_macro"] == 0.99
