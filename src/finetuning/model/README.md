---
base_model: Qwen/Qwen2.5-3B-Instruct
library_name: peft
language:
  - es
tags:
  - lora
  - qlora
  - rag
  - relevance-grading
  - legal
  - eu-ai-act
license: apache-2.0
---

# NormaBot RAG Grader — Qwen2.5-3B-Instruct + QLoRA

Adaptador LoRA (QLoRA) sobre `Qwen/Qwen2.5-3B-Instruct` fine-tuneado para la
tarea de **clasificación de relevancia RAG** en el dominio de normativa de IA
(EU AI Act, BOE, normativa española).

Componente del sistema [NormaBot](https://github.com/maquinas-que-aprenden/proyecto-final).

---

## Tarea

Dado un par `(consulta, documento)`, el modelo decide si el documento contiene
información útil para responder la consulta sobre regulación de IA.

- **Etiquetas**: `relevante` / `no relevante`
- **Uso en NormaBot**: paso *Grade* del pipeline Corrective RAG
  (Retrieve → **Grade** → Generate)

---

## Resultados de evaluación

| Modelo | Accuracy | F1-macro |
|--------|----------|----------|
| Qwen2.5-3B-Instruct base (prompting) | 0.8500 | 0.8500 |
| **Qwen2.5-3B-Instruct + QLoRA (este modelo)** | **0.8958** | **0.8954** |
| Mejora | +0.0458 | +0.0454 |

Evaluado sobre 96 ejemplos de test (split estratificado, seed=42).

---

## Dataset de entrenamiento

| Split | Ejemplos |
|-------|----------|
| Train | 443 |
| Val   | 95 |
| Test  | 96 |
| **Total** | **634** |

Formato JSONL con campos `query`, `document`, `label`.
Generado a partir del corpus legal indexado en ChromaDB de NormaBot.

---

## Hiperparámetros de entrenamiento

| Parámetro | Valor |
|-----------|-------|
| Método | QLoRA (4-bit NF4) |
| LoRA rank (r) | 8 |
| LoRA alpha | 16 |
| LoRA dropout | 0.05 |
| Target modules | q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj |
| Epochs | 3 |
| Batch efectivo | 16 (4 × 4 grad. accum.) |
| Learning rate | 2e-4 |
| LR scheduler | cosine |
| Optimizador | paged_adamw_8bit |
| Max seq length | 512 |
| Hardware | Google Colab T4 GPU |
| Framework | PEFT 0.13.2 + TRL 0.13.0 |

---

## System prompt usado en entrenamiento

```
Eres un asistente especializado en normativa de inteligencia artificial.
Tu tarea es determinar si un documento contiene información útil para responder
una consulta sobre regulación de IA (EU AI Act, BOE, normativa española).
Responde únicamente con 'relevante' o 'no relevante', sin explicación adicional.
```

---

## Cómo cargar el modelo

```python
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel
import torch

MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"
ADAPTER_PATH = "src/finetuning/model"

# Cuantización 4-bit (requiere GPU con bitsandbytes)
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
)

tokenizer = AutoTokenizer.from_pretrained(ADAPTER_PATH)
base_model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, quantization_config=bnb_config, device_map="auto"
)
model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
model.eval()
```

En NormaBot, usar directamente el wrapper de producción:

```python
from src.finetuning.grader import predict_relevance

resultado = predict_relevance(query="¿Qué sistemas son de alto riesgo?", document="...")
# → "relevante" o "no relevante"
```

---

## Archivos en este directorio

| Archivo | Descripción |
|---------|-------------|
| `adapter_config.json` | Configuración LoRA (PEFT) |
| `adapter_model.safetensors` | Pesos del adaptador (~57 MB, trackeado en DVC) |
| `tokenizer_config.json` | Config del tokenizador |
| `tokenizer.json` | Vocabulario y reglas de tokenización |
| `vocab.json` | Vocabulario BPE |
| `merges.txt` | Reglas de fusión BPE |
| `added_tokens.json` | Tokens especiales añadidos |
| `special_tokens_map.json` | Mapa de tokens especiales |
| `model_metadata.json` | Metadatos del experimento (métricas, dataset) |

> **Nota**: `adapter_model.safetensors` no está en git.
> Descargarlo con: `dvc pull src/finetuning/model/adapter_model.safetensors.dvc`

---

## Limitaciones

- Dataset pequeño (634 ejemplos). El modelo puede no generalizar bien fuera
  del dominio de normativa de IA española/europea.
- Entrenado para responder exclusivamente `relevante` o `no relevante`.
  Respuestas largas o en otro idioma pueden degradar la precisión.
- La cuantización 4-bit requiere una GPU compatible con `bitsandbytes`.
  En CPU, usar el modelo base sin cuantización (más lento).
