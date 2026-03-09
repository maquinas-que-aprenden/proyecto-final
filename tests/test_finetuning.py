"""tests/test_finetuning.py — Tests unitarios del módulo de fine-tuning.

Cubre las funciones puras de src/finetuning/functions.py y
la lógica de parseo/disponibilidad de src/finetuning/grader.py.

Los tests de inferencia real (modelo + GPU) NO están incluidos aquí
porque requieren artefactos de varios GB descargados via DVC.
Los tests de lógica usan mocks para aislar el código de esas deps.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ──────────────────────────────────────────────────────────────
# Helpers compartidos
# ──────────────────────────────────────────────────────────────

def _make_jsonl(path: Path, records: list[dict]) -> Path:
    """Escribe registros en formato JSONL en path y lo devuelve."""
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records),
        encoding="utf-8",
    )
    return path


def _minimal_dataset(n: int = 20) -> list[dict]:
    """Dataset mínimo con ejemplos balanceados relevante/no relevante."""
    half = n // 2
    data = []
    for i in range(half):
        data.append({
            "query": f"¿Qué dice el artículo {i + 1}?",
            "document": f"El artículo {i + 1} regula los sistemas de IA de alto riesgo.",
            "label": "relevante",
        })
    for i in range(n - half):
        data.append({
            "query": "¿Cuál es la definición de IA?",
            "document": f"Receta de cocina número {i + 1}.",
            "label": "no relevante",
        })
    return data


# ──────────────────────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────────────────────

class TestConstants:
    def test_labels_defined(self):
        from src.finetuning.functions import LABEL_RELEVANTE, LABEL_NO_RELEVANTE, LABELS
        assert LABEL_RELEVANTE == "relevante"
        assert LABEL_NO_RELEVANTE == "no relevante"
        assert LABEL_RELEVANTE in LABELS
        assert LABEL_NO_RELEVANTE in LABELS
        assert len(LABELS) == 2

    def test_system_prompt_nonempty(self):
        from src.finetuning.functions import GRADING_SYSTEM_PROMPT
        assert isinstance(GRADING_SYSTEM_PROMPT, str)
        assert len(GRADING_SYSTEM_PROMPT) > 50
        # Debe orientar al modelo sobre su tarea
        assert "relevante" in GRADING_SYSTEM_PROMPT.lower()

    def test_mlflow_experiment_name(self):
        from src.finetuning.functions import MLFLOW_EXPERIMENT_NAME
        assert isinstance(MLFLOW_EXPERIMENT_NAME, str)
        assert MLFLOW_EXPERIMENT_NAME  # no vacío

    def test_grader_labels_match_functions_labels(self):
        """Las constantes de grader.py deben coincidir con functions.py."""
        from src.finetuning import grader
        from src.finetuning import functions
        assert grader.LABEL_RELEVANTE    == functions.LABEL_RELEVANTE
        assert grader.LABEL_NO_RELEVANTE == functions.LABEL_NO_RELEVANTE
        assert grader.GRADING_SYSTEM_PROMPT == functions.GRADING_SYSTEM_PROMPT


# ──────────────────────────────────────────────────────────────
# load_grading_dataset
# ──────────────────────────────────────────────────────────────

class TestLoadGradingDataset:
    def test_carga_jsonl_valido(self, tmp_path):
        from src.finetuning.functions import load_grading_dataset
        records = _minimal_dataset(10)
        f = _make_jsonl(tmp_path / "data.jsonl", records)
        result = load_grading_dataset(f)
        assert len(result) == 10
        assert all("query" in r and "document" in r and "label" in r for r in result)

    def test_error_si_archivo_no_existe(self, tmp_path):
        from src.finetuning.functions import load_grading_dataset
        with pytest.raises(AssertionError, match="Dataset no encontrado"):
            load_grading_dataset(tmp_path / "no_existe.jsonl")

    def test_ignora_lineas_vacias(self, tmp_path):
        from src.finetuning.functions import load_grading_dataset
        records = _minimal_dataset(4)
        content = "\n".join(json.dumps(r) for r in records) + "\n\n\n"
        f = tmp_path / "data.jsonl"
        f.write_text(content, encoding="utf-8")
        result = load_grading_dataset(f)
        assert len(result) == 4

    def test_conteo_etiquetas_correcto(self, tmp_path):
        from src.finetuning.functions import load_grading_dataset, LABEL_RELEVANTE, LABEL_NO_RELEVANTE
        records = _minimal_dataset(20)  # 10 de cada
        f = _make_jsonl(tmp_path / "data.jsonl", records)
        result = load_grading_dataset(f)
        n_rel = sum(1 for r in result if r["label"] == LABEL_RELEVANTE)
        n_no  = sum(1 for r in result if r["label"] == LABEL_NO_RELEVANTE)
        assert n_rel == 10
        assert n_no  == 10


# ──────────────────────────────────────────────────────────────
# split_dataset
# ──────────────────────────────────────────────────────────────

class TestSplitDataset:
    def test_proporciones_aproximadas(self):
        from src.finetuning.functions import split_dataset
        data = _minimal_dataset(100)
        train, val, test = split_dataset(data, test_size=0.30, val_ratio=0.50, seed=42)
        # 70 / 15 / 15 aproximado
        assert len(train) == 70
        assert len(val)   == 15
        assert len(test)  == 15

    def test_sin_solapamiento(self):
        from src.finetuning.functions import split_dataset
        data = _minimal_dataset(60)
        train, val, test = split_dataset(data, seed=42)
        ids_train = {id(e) for e in train}
        ids_val   = {id(e) for e in val}
        ids_test  = {id(e) for e in test}
        assert not ids_train & ids_val
        assert not ids_train & ids_test
        assert not ids_val   & ids_test

    def test_total_conservado(self):
        from src.finetuning.functions import split_dataset
        data = _minimal_dataset(80)
        train, val, test = split_dataset(data, seed=42)
        assert len(train) + len(val) + len(test) == 80

    def test_estratificacion_balanceada(self):
        from src.finetuning.functions import split_dataset, LABEL_RELEVANTE
        data = _minimal_dataset(100)
        train, val, test = split_dataset(data, test_size=0.30, val_ratio=0.50, seed=42)
        for split, name in [(train, "train"), (val, "val"), (test, "test")]:
            ratio = sum(1 for e in split if e["label"] == LABEL_RELEVANTE) / len(split)
            # Con estratificación debería estar entre 40% y 60%
            assert 0.40 <= ratio <= 0.60, f"Ratio en {name} fuera de rango: {ratio:.2f}"

    def test_reproducibilidad_con_misma_seed(self):
        from src.finetuning.functions import split_dataset
        data = _minimal_dataset(60)
        train1, val1, test1 = split_dataset(data, seed=42)
        train2, val2, test2 = split_dataset(data, seed=42)
        assert [e["query"] for e in train1] == [e["query"] for e in train2]


# ──────────────────────────────────────────────────────────────
# build_grading_messages
# ──────────────────────────────────────────────────────────────

class TestBuildGradingMessages:
    def test_estructura_basica(self):
        from src.finetuning.functions import build_grading_messages, GRADING_SYSTEM_PROMPT
        msgs = build_grading_messages("¿Qué es el EU AI Act?", "Documento de prueba.")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        assert msgs[0]["content"] == GRADING_SYSTEM_PROMPT

    def test_query_y_document_en_user(self):
        from src.finetuning.functions import build_grading_messages
        query = "¿Qué prácticas están prohibidas?"
        doc   = "El artículo 5 prohíbe la manipulación subliminal."
        msgs  = build_grading_messages(query, doc)
        user_content = msgs[1]["content"]
        assert query in user_content
        assert doc   in user_content

    def test_mensajes_son_dicts(self):
        from src.finetuning.functions import build_grading_messages
        msgs = build_grading_messages("q", "d")
        assert all(isinstance(m, dict) for m in msgs)
        assert all("role" in m and "content" in m for m in msgs)

    def test_query_vacia_no_falla(self):
        from src.finetuning.functions import build_grading_messages
        msgs = build_grading_messages("", "documento")
        assert len(msgs) == 2

    def test_documento_vacio_no_falla(self):
        from src.finetuning.functions import build_grading_messages
        msgs = build_grading_messages("query", "")
        assert len(msgs) == 2


# ──────────────────────────────────────────────────────────────
# format_training_prompt (con tokenizer mock)
# ──────────────────────────────────────────────────────────────

class TestFormatTrainingPrompt:
    @pytest.fixture
    def mock_tokenizer(self):
        tok = MagicMock()
        tok.eos_token = "</s>"
        tok.apply_chat_template.return_value = "[CHAT_TEMPLATE]"
        return tok

    def test_incluye_label_y_eos(self, mock_tokenizer):
        from src.finetuning.functions import format_training_prompt
        example = {"query": "q", "document": "d", "label": "relevante"}
        result  = format_training_prompt(example, mock_tokenizer)
        assert result.endswith("relevante</s>")

    def test_incluye_template(self, mock_tokenizer):
        from src.finetuning.functions import format_training_prompt
        example = {"query": "q", "document": "d", "label": "no relevante"}
        result  = format_training_prompt(example, mock_tokenizer)
        assert "[CHAT_TEMPLATE]" in result

    def test_apply_chat_template_llamado_con_add_generation_prompt(self, mock_tokenizer):
        from src.finetuning.functions import format_training_prompt
        example = {"query": "q", "document": "d", "label": "relevante"}
        format_training_prompt(example, mock_tokenizer)
        call_kwargs = mock_tokenizer.apply_chat_template.call_args
        assert call_kwargs.kwargs.get("add_generation_prompt") is True


# ──────────────────────────────────────────────────────────────
# predict_relevance en functions.py (con model+tokenizer mock)
# ──────────────────────────────────────────────────────────────

class TestPredictRelevanceFunctions:
    """Prueba la lógica de parseo de la respuesta sin cargar el modelo real."""

    @pytest.fixture
    def mock_model_and_tokenizer(self):
        tok = MagicMock()
        tok.eos_token_id = 2
        tok.apply_chat_template.return_value = "[prompt]"
        # tokenizer() devuelve un objeto con input_ids de forma (1, 5)
        import torch
        tok.return_value = {"input_ids": torch.zeros(1, 5, dtype=torch.long)}
        tok.return_value = MagicMock()
        tok.return_value.__getitem__ = lambda self, k: MagicMock()

        model = MagicMock()
        model.device = "cpu"
        return model, tok

    def _setup_generation(self, tok, model, raw_response: str):
        """Configura mocks para que predict_relevance devuelva raw_response."""
        import torch
        input_ids = torch.zeros(1, 5, dtype=torch.long)
        inputs_mock = MagicMock()
        inputs_mock.__getitem__ = lambda s, k: input_ids if k == "input_ids" else MagicMock()
        inputs_mock.to.return_value = inputs_mock
        tok.return_value = inputs_mock

        # outputs[0][5:] → decoded como raw_response
        generated = torch.zeros(1, 7, dtype=torch.long)
        model.generate.return_value = generated
        tok.decode.return_value = raw_response
        return tok, model

    def test_respuesta_relevante(self):
        from src.finetuning.functions import predict_relevance, LABEL_RELEVANTE
        import torch
        model, tok = MagicMock(), MagicMock()
        model.device = "cpu"
        tok.eos_token_id = 2
        tok.apply_chat_template.return_value = "[p]"
        inputs = MagicMock()
        inputs.to.return_value = inputs
        inputs.__getitem__ = lambda s, k: torch.zeros(1, 5, dtype=torch.long)
        tok.return_value = inputs
        model.generate.return_value = torch.zeros(1, 7, dtype=torch.long)
        tok.decode.return_value = "relevante"
        result = predict_relevance("q", "d", model, tok)
        assert result == LABEL_RELEVANTE

    def test_respuesta_no_relevante_explicita(self):
        from src.finetuning.functions import predict_relevance, LABEL_NO_RELEVANTE
        import torch
        model, tok = MagicMock(), MagicMock()
        model.device = "cpu"
        tok.eos_token_id = 2
        tok.apply_chat_template.return_value = "[p]"
        inputs = MagicMock()
        inputs.to.return_value = inputs
        inputs.__getitem__ = lambda s, k: torch.zeros(1, 5, dtype=torch.long)
        tok.return_value = inputs
        model.generate.return_value = torch.zeros(1, 7, dtype=torch.long)
        tok.decode.return_value = "no relevante"
        result = predict_relevance("q", "d", model, tok)
        assert result == LABEL_NO_RELEVANTE

    def test_respuesta_no_es_relevante(self):
        from src.finetuning.functions import predict_relevance, LABEL_NO_RELEVANTE
        import torch
        model, tok = MagicMock(), MagicMock()
        model.device = "cpu"
        tok.eos_token_id = 2
        tok.apply_chat_template.return_value = "[p]"
        inputs = MagicMock()
        inputs.to.return_value = inputs
        inputs.__getitem__ = lambda s, k: torch.zeros(1, 5, dtype=torch.long)
        tok.return_value = inputs
        model.generate.return_value = torch.zeros(1, 7, dtype=torch.long)
        tok.decode.return_value = "no es relevante para esta consulta"
        result = predict_relevance("q", "d", model, tok)
        assert result == LABEL_NO_RELEVANTE

    def test_respuesta_inesperada_es_conservadora(self):
        """Respuesta ambigua → no relevante (descarta documento)."""
        from src.finetuning.functions import predict_relevance, LABEL_NO_RELEVANTE
        import torch
        model, tok = MagicMock(), MagicMock()
        model.device = "cpu"
        tok.eos_token_id = 2
        tok.apply_chat_template.return_value = "[p]"
        inputs = MagicMock()
        inputs.to.return_value = inputs
        inputs.__getitem__ = lambda s, k: torch.zeros(1, 5, dtype=torch.long)
        tok.return_value = inputs
        model.generate.return_value = torch.zeros(1, 7, dtype=torch.long)
        tok.decode.return_value = "no lo sé"
        result = predict_relevance("q", "d", model, tok)
        assert result == LABEL_NO_RELEVANTE

    def test_respuesta_mixta_prioriza_no_relevante(self):
        """'no relevante' debe tener prioridad sobre 'relevante' al parsear."""
        from src.finetuning.functions import predict_relevance, LABEL_NO_RELEVANTE
        import torch
        model, tok = MagicMock(), MagicMock()
        model.device = "cpu"
        tok.eos_token_id = 2
        tok.apply_chat_template.return_value = "[p]"
        inputs = MagicMock()
        inputs.to.return_value = inputs
        inputs.__getitem__ = lambda s, k: torch.zeros(1, 5, dtype=torch.long)
        tok.return_value = inputs
        model.generate.return_value = torch.zeros(1, 7, dtype=torch.long)
        # "no relevante" contiene "relevante" también — la lógica debe manejar esto
        tok.decode.return_value = "no relevante"
        result = predict_relevance("q", "d", model, tok)
        assert result == LABEL_NO_RELEVANTE


# ──────────────────────────────────────────────────────────────
# print_comparison
# ──────────────────────────────────────────────────────────────

class TestPrintComparison:
    def test_devuelve_mejora_correcta(self, capsys):
        from src.finetuning.functions import print_comparison
        mejora_acc, mejora_f1 = print_comparison(0.80, 0.79, 0.90, 0.91)
        assert abs(mejora_acc - 0.10) < 1e-9
        assert abs(mejora_f1  - 0.12) < 1e-9

    def test_mejora_negativa(self, capsys):
        from src.finetuning.functions import print_comparison
        mejora_acc, mejora_f1 = print_comparison(0.90, 0.90, 0.85, 0.85)
        assert mejora_f1 < 0
        out = capsys.readouterr().out
        assert "no mejoro" in out.lower() or "delta" in out.lower()

    def test_mejora_cero(self, capsys):
        from src.finetuning.functions import print_comparison
        mejora_acc, mejora_f1 = print_comparison(0.85, 0.85, 0.85, 0.85)
        assert mejora_acc == 0.0
        assert mejora_f1  == 0.0

    def test_imprime_tabla(self, capsys):
        from src.finetuning.functions import print_comparison
        print_comparison(0.80, 0.79, 0.90, 0.91)
        out = capsys.readouterr().out
        assert "Accuracy" in out or "accuracy" in out.lower()
        assert "F1" in out or "f1" in out.lower()


# ──────────────────────────────────────────────────────────────
# get_mlflow_password
# ──────────────────────────────────────────────────────────────

class TestGetMlflowPassword:
    def test_lee_desde_env(self, monkeypatch):
        from src.finetuning.functions import get_mlflow_password
        monkeypatch.setenv("MLFLOW_PASSWORD", "mi_password_segura")
        assert get_mlflow_password() == "mi_password_segura"

    def test_lanza_error_si_no_hay_password(self, monkeypatch):
        from src.finetuning.functions import get_mlflow_password
        monkeypatch.delenv("MLFLOW_PASSWORD", raising=False)
        with pytest.raises(EnvironmentError, match="MLFLOW_PASSWORD"):
            get_mlflow_password()


# ──────────────────────────────────────────────────────────────
# grader.is_available
# ──────────────────────────────────────────────────────────────

class TestGraderIsAvailable:
    def test_false_si_no_existe_adapter(self, tmp_path):
        """is_available() debe devolver False si el directorio del adaptador no existe."""
        import src.finetuning.grader as grader_module
        original_path = grader_module._ADAPTER_PATH
        try:
            grader_module._ADAPTER_PATH = tmp_path / "modelo_inexistente"
            assert grader_module.is_available() is False
        finally:
            grader_module._ADAPTER_PATH = original_path

    def test_false_si_directorio_existe_pero_sin_safetensors(self, tmp_path):
        import src.finetuning.grader as grader_module
        original_path = grader_module._ADAPTER_PATH
        try:
            grader_module._ADAPTER_PATH = tmp_path
            # Directorio existe pero sin adapter_model.safetensors
            (tmp_path / "adapter_config.json").write_text("{}")
            assert grader_module.is_available() is False
        finally:
            grader_module._ADAPTER_PATH = original_path

    def test_true_si_safetensors_existe(self, tmp_path):
        import src.finetuning.grader as grader_module
        original_path = grader_module._ADAPTER_PATH
        try:
            grader_module._ADAPTER_PATH = tmp_path
            (tmp_path / "adapter_model.safetensors").write_bytes(b"\x00")
            assert grader_module.is_available() is True
        finally:
            grader_module._ADAPTER_PATH = original_path


# ──────────────────────────────────────────────────────────────
# grader.predict_relevance — parseo de respuestas (mock _load_model)
# ──────────────────────────────────────────────────────────────

class TestGraderPredictRelevanceParsing:
    """Prueba la lógica de parseo del grader.py sin cargar el modelo real.

    Se mockea _load_model para que devuelva un tokenizer y modelo falsos
    cuya salida de decode() es controlable.
    """

    def _make_mock_pair(self, decoded_response: str):
        """Crea (tokenizer_mock, model_mock) que decodifica decoded_response."""
        import torch

        tok = MagicMock()
        tok.eos_token_id = 2
        tok.apply_chat_template.return_value = "[prompt]"

        inputs_mock = MagicMock()
        inputs_mock.to.return_value = inputs_mock
        input_ids = torch.zeros(1, 5, dtype=torch.long)
        inputs_mock.__getitem__ = lambda s, k: input_ids
        tok.return_value = inputs_mock

        model = MagicMock()
        model.device = "cpu"
        model.generate.return_value = torch.zeros(1, 7, dtype=torch.long)
        tok.decode.return_value = decoded_response

        return tok, model

    def test_respuesta_relevante(self):
        from src.finetuning.grader import predict_relevance, LABEL_RELEVANTE
        tok, model = self._make_mock_pair("relevante")
        with patch("src.finetuning.grader._load_model", return_value=(tok, model)):
            result = predict_relevance("¿Cuáles son los riesgos?", "Documento relevante.")
        assert result == LABEL_RELEVANTE

    def test_respuesta_no_relevante(self):
        from src.finetuning.grader import predict_relevance, LABEL_NO_RELEVANTE
        tok, model = self._make_mock_pair("no relevante")
        with patch("src.finetuning.grader._load_model", return_value=(tok, model)):
            result = predict_relevance("¿Cuáles son los riesgos?", "Receta de tortilla.")
        assert result == LABEL_NO_RELEVANTE

    def test_respuesta_no_es_relevante(self):
        from src.finetuning.grader import predict_relevance, LABEL_NO_RELEVANTE
        tok, model = self._make_mock_pair("no es relevante para esta consulta")
        with patch("src.finetuning.grader._load_model", return_value=(tok, model)):
            result = predict_relevance("q", "d")
        assert result == LABEL_NO_RELEVANTE

    def test_respuesta_ambigua_es_conservadora(self):
        """Respuesta inesperada → LABEL_NO_RELEVANTE (descarta documento)."""
        from src.finetuning.grader import predict_relevance, LABEL_NO_RELEVANTE
        tok, model = self._make_mock_pair("lo siento, no entiendo la pregunta")
        with patch("src.finetuning.grader._load_model", return_value=(tok, model)):
            result = predict_relevance("q", "d")
        assert result == LABEL_NO_RELEVANTE

    def test_respuesta_en_mayusculas_normalizada(self):
        """La respuesta en mayúsculas se normaliza con .lower() antes de parsear."""
        from src.finetuning.grader import predict_relevance, LABEL_RELEVANTE
        tok, model = self._make_mock_pair("RELEVANTE")
        with patch("src.finetuning.grader._load_model", return_value=(tok, model)):
            result = predict_relevance("q", "d")
        assert result == LABEL_RELEVANTE

    def test_respuesta_no_relevante_con_texto_extra(self):
        """Texto extra tras 'no relevante' sigue siendo detectado."""
        from src.finetuning.grader import predict_relevance, LABEL_NO_RELEVANTE
        tok, model = self._make_mock_pair("no relevante para esta consulta sobre normativa.")
        with patch("src.finetuning.grader._load_model", return_value=(tok, model)):
            result = predict_relevance("q", "d")
        assert result == LABEL_NO_RELEVANTE


# ──────────────────────────────────────────────────────────────
# grader._load_model — FileNotFoundError si el adaptador no existe
# ──────────────────────────────────────────────────────────────

class TestGraderLoadModelErrors:
    def test_error_si_no_adapter_y_sin_model_en_cache(self, tmp_path):
        """_load_model lanza FileNotFoundError si _ADAPTER_PATH no existe."""
        import src.finetuning.grader as grader_module

        original_path  = grader_module._ADAPTER_PATH
        original_model = grader_module._model
        original_tok   = grader_module._tokenizer

        # Resetear singleton para forzar re-carga
        grader_module._model     = None
        grader_module._tokenizer = None
        grader_module._ADAPTER_PATH = tmp_path / "no_existe"

        try:
            with pytest.raises(FileNotFoundError, match="Adaptador LoRA no encontrado"):
                grader_module._load_model()
        finally:
            grader_module._ADAPTER_PATH = original_path
            grader_module._model        = original_model
            grader_module._tokenizer    = original_tok

    def test_import_error_si_faltan_dependencias(self, tmp_path):
        """_load_model lanza ImportError si transformers/peft no están instalados."""
        import src.finetuning.grader as grader_module
        import builtins

        original_path  = grader_module._ADAPTER_PATH
        original_model = grader_module._model
        original_tok   = grader_module._tokenizer

        grader_module._model     = None
        grader_module._tokenizer = None
        # Apuntar a un path que sí existe (para no fallar en FileNotFoundError)
        grader_module._ADAPTER_PATH = tmp_path
        (tmp_path / "adapter_model.safetensors").write_bytes(b"\x00")

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name in ("transformers", "peft"):
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)

        try:
            with patch("builtins.__import__", side_effect=mock_import):
                with pytest.raises(ImportError, match="Faltan dependencias"):
                    grader_module._load_model()
        finally:
            grader_module._ADAPTER_PATH = original_path
            grader_module._model        = original_model
            grader_module._tokenizer    = original_tok


# ──────────────────────────────────────────────────────────────
# Validación de estructura del dataset JSONL
# ──────────────────────────────────────────────────────────────

class TestDatasetStructure:
    """Valida que el dataset generado (si existe) tenga la estructura correcta."""

    DATASET_PATH = (
        Path(__file__).parent.parent
        / "data/processed/grading_dataset.jsonl"
    )

    @pytest.mark.skipif(
        not (
            Path(__file__).parent.parent
            / "data/processed/grading_dataset.jsonl"
        ).exists(),
        reason="grading_dataset.jsonl no disponible (requiere dvc pull)",
    )
    def test_estructura_campos_obligatorios(self):
        from src.finetuning.functions import LABELS
        records = [
            json.loads(line)
            for line in self.DATASET_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(records) > 0, "Dataset vacío"
        for i, r in enumerate(records):
            assert "query"    in r, f"Fila {i}: falta 'query'"
            assert "document" in r, f"Fila {i}: falta 'document'"
            assert "label"    in r, f"Fila {i}: falta 'label'"
            assert r["label"] in LABELS, f"Fila {i}: label inválido '{r['label']}'"

    @pytest.mark.skipif(
        not (
            Path(__file__).parent.parent
            / "data/processed/grading_dataset.jsonl"
        ).exists(),
        reason="grading_dataset.jsonl no disponible (requiere dvc pull)",
    )
    def test_campos_no_vacios(self):
        records = [
            json.loads(line)
            for line in self.DATASET_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for i, r in enumerate(records):
            assert r["query"].strip(),    f"Fila {i}: query vacía"
            assert r["document"].strip(), f"Fila {i}: document vacío"
            assert r["label"].strip(),    f"Fila {i}: label vacío"
