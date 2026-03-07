# Auditoría 03-02-2026

## Scope / Cambios auditados

- Commits auditados: rama `develop`, commits desde `6137e2e` hasta `1a85e81`
- PRs revisados: pipeline BERT (PR #bert-pipeline), correcciones ruff (PR #lint-fixes), ajustes data pipeline (PR #data-pipeline)
- Módulos revisados: `src/classifier/`, `src/rag/`, `src/finetuning/`, `data/`

## Tests

- **Suite**: pytest · directorio `tests/`
- **Resultado**: Todos los tests PASSING: 89/89
- **Cobertura**: clasificador de riesgo, pipeline RAG, orquestador (smoke tests)

## Estado del módulo de fine-tuning

- Modelos afectados: `Qwen/Qwen2.5-3B-Instruct` + adaptador LoRA QLoRA (r=8, alpha=16)
- Artefactos de entrenamiento: `src/finetuning/output/qwen-grader-lora/adapter_final/` (adapter_model.safetensors, adapter_config.json, tokenizer)
- Checkpoints intermedios: checkpoint-28 (epoch 1), checkpoint-56 (epoch 2), checkpoint-84 (epoch 3)
- Métricas finales: Accuracy=0.9062, F1-macro=0.9057 (mejora +0.0557 sobre baseline)
- Acciones pendientes: integración en `src/rag/main.py` validada; pendiente merge+GGUF para Ollama producción

## Desbloqueadores P0: RESUELTOS
