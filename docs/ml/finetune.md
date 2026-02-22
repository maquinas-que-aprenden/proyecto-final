# Fine-tuning QLoRA — Clasificador de riesgo IA

## Justificación de QLoRA frente a fine-tuning completo

El fine-tuning completo de un LLM de 7B parámetros requiere decenas de GB de VRAM y días de cómputo.
QLoRA (_Quantized Low-Rank Adaptation_) resuelve esto con dos técnicas combinadas:

- **Cuantización 4-bit (bitsandbytes)**: el modelo base se carga en precisión NF4, reduciendo el uso de VRAM de ~14 GB (fp16) a ~4 GB, sin pérdida significativa de calidad.
- **LoRA**: en lugar de actualizar todos los pesos, se añaden matrices de rango bajo (_rank-decomposition_) solo en capas de atención seleccionadas. El número de parámetros entrenables pasa de ~7B a ~4M (<0.1%), lo que permite ejecutar el entrenamiento en una T4 de 16 GB.

Esto hace viable el fine-tuning en el free tier de Colab, sin infraestructura dedicada.

## Modelo base

| Opción | Parámetros | VRAM necesaria | Razón |
|--------|-----------|----------------|-------|
| `mistralai/Mistral-7B-v0.1` | 7B | ~6 GB (4-bit) | Mejor rendimiento general en clasificación de texto en español |
| `meta-llama/Llama-3.2-3B-Instruct` | 3B | ~3 GB (4-bit) | Alternativa si hay problemas de VRAM |

**Seleccionado**: `mistralai/Mistral-7B-v0.1`. Aunque no está afinado específicamente para instrucciones, su rendimiento base en comprensión de texto en español es superior al de Llama 3.2 3B. El fine-tuning sobre nuestro dataset de instrucciones corregirá el formato de salida.

## Configuración de cuantización (QLoRA)

```python
BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",          # Normal Float 4: mejor que int4 para pesos de LLMs
    bnb_4bit_use_double_quant=True,      # Cuantización adicional de las constantes de cuantización (~0.4 GB extra)
    bnb_4bit_compute_dtype=torch.float16,
)
```

## Configuración LoRA

```python
LoraConfig(
    r=16,                                # Rango de las matrices de adaptación
    lora_alpha=32,                       # Escalado: alpha/r = 2 (valor estándar)
    target_modules=["q_proj", "v_proj"], # Capas de atención de Mistral
    lora_dropout=0.05,
    bias="none",
)
```

- `r=16` equilibra capacidad expresiva y eficiencia. Valores menores (8) reducen parámetros pero pueden limitar la adaptación al dominio; valores mayores (32, 64) aumentan el coste sin mejora proporcional en datasets pequeños.
- Solo se adaptan `q_proj` y `v_proj` (matrices query y value de atención) porque concentran la mayor parte del conocimiento contextual del modelo.

## Hiperparámetros de entrenamiento

| Parámetro | Valor | Justificación |
|-----------|-------|---------------|
| `num_train_epochs` | 3 | Suficiente para datasets < 1000 muestras sin sobreajuste |
| `per_device_train_batch_size` | 4 | Máximo viable en T4 con secuencias de 512 tokens |
| `gradient_accumulation_steps` | 4 | Batch efectivo = 16, simula batch mayor sin más VRAM |
| `learning_rate` | 2e-4 | Estándar para LoRA; más alto que en fine-tuning completo |
| `lr_scheduler_type` | cosine | Decaimiento suave, evita caídas bruscas de LR |
| `warmup_ratio` | 0.03 | Estabiliza los primeros pasos de entrenamiento |
| `optim` | paged_adamw_8bit | AdamW cuantizado a 8-bit, reduce VRAM del optimizador |
| `max_seq_length` | 512 | Las muestras del dataset tienen ~100-150 tokens; 512 da margen |

## Formato del dataset de instrucción

Cada muestra del dataset se convierte al siguiente formato antes del fine-tuning:

```
### Instrucción:
Clasifica el siguiente sistema de IA según el Reglamento de Inteligencia Artificial de la UE
en una de estas categorías: inaceptable, alto_riesgo, riesgo_limitado, riesgo_minimo.

### Descripción:
Sistema de puntuación social que clasifica a ciudadanos según su historial de pagos,
multas y comportamiento en redes para restringir su acceso a transporte público.

### Clasificación:
inaceptable
```

El split es 80% train / 20% test, estratificado por clase. Los archivos se guardan en formato JSONL en `src/classifier/data/finetune/`.

## Entorno de ejecución

- **Plataforma**: Google Colab (notebook `12_finetune_qlora.ipynb`)
- **GPU**: T4 16 GB VRAM (free tier)
- **Tiempo estimado**: ~30-45 min para 3 épocas con 400 muestras de entrenamiento
- **Artefacto de salida**: pesos del adaptador LoRA en `src/classifier/model/qlora_adapter/`

## Comparativa con el modelo baseline

| Modelo | Params entrenables | VRAM | F1-macro test |
|--------|--------------------|------|---------------|
| LogReg + TF-IDF (baseline) | N/A | N/A | 0.9053 |
| QLoRA Mistral-7B | ~4M (0.06%) | ~8 GB | pendiente |

El objetivo del fine-tuning es explorar si un LLM con comprensión semántica profunda puede superar al baseline clásico, especialmente en casos límite donde el contexto semántico es determinante para la clasificación correcta bajo el EU AI Act.
