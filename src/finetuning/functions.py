"""
Funciones auxiliares para el fine-tuning de Qwen 2.5 3B-Instruct
en la tarea de clasificación de relevancia RAG (NormaBot).

Uso en Colab:
    import sys
    sys.path.insert(0, "/content")
    from functions import *
"""

import os
import json
import torch
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, f1_score, accuracy_score

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ──────────────────────────────────────────────────────────────
# Constantes del dominio
# ──────────────────────────────────────────────────────────────

LABEL_RELEVANTE    = "relevante"
LABEL_NO_RELEVANTE = "no relevante"
LABELS             = [LABEL_RELEVANTE, LABEL_NO_RELEVANTE]

GRADING_SYSTEM_PROMPT = (
    "Eres un asistente especializado en normativa de inteligencia artificial. "
    "Tu tarea es determinar si un documento contiene información útil para responder "
    "una consulta sobre regulación de IA (EU AI Act, BOE, normativa española). "
    "Responde únicamente con 'relevante' o 'no relevante', sin explicación adicional."
)

MLFLOW_EXPERIMENT_NAME = "rag_grader_relevancia"


# ──────────────────────────────────────────────────────────────
# Entorno
# ──────────────────────────────────────────────────────────────

def check_gpu() -> None:
    """Imprime información del entorno GPU disponible."""
    print(f"PyTorch:          {torch.__version__}")
    print(f"CUDA disponible:  {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU:              {torch.cuda.get_device_name(0)}")
        total_vram = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"VRAM total:       {total_vram:.1f} GB")
    else:
        print("Sin GPU — el entrenamiento sera extremadamente lento.")
        print("  Ejecuta en Google Colab (Runtime -> Change runtime type -> T4 GPU).")


# ──────────────────────────────────────────────────────────────
# Dataset
# ──────────────────────────────────────────────────────────────

def load_grading_dataset(path: Path) -> list[dict]:
    """
    Carga el dataset de grading desde un archivo JSONL y muestra estadísticas.
    Lanza AssertionError si el archivo no existe.
    """
    assert path.exists(), (
        f"Dataset no encontrado en {path.resolve()}\n"
        "Genera el dataset ejecutando desde la raiz del repo:\n"
        "  python data/generate_grading_dataset.py"
    )
    with open(path, "r", encoding="utf-8") as f:
        data = [json.loads(line) for line in f if line.strip()]

    n_rel = sum(1 for ex in data if ex["label"] == LABEL_RELEVANTE)
    n_no  = len(data) - n_rel

    print(f"Dataset cargado: {path.resolve()}")
    print(f"  Total ejemplos:  {len(data)}")
    print(f"  Relevantes:      {n_rel} ({n_rel / len(data) * 100:.1f}%)")
    print(f"  No relevantes:   {n_no} ({n_no / len(data) * 100:.1f}%)")
    print()
    print("Muestra:")
    print(json.dumps(data[0], ensure_ascii=False, indent=2))
    return data


def split_dataset(
    data: list[dict],
    test_size: float = 0.30,
    val_ratio: float = 0.50,
    seed: int = 42,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    División estratificada train / val / test (70 / 15 / 15 por defecto).
    Devuelve (train_data, val_data, test_data).
    """
    labels_all = [ex["label"] for ex in data]
    train_data, temp = train_test_split(
        data, test_size=test_size, random_state=seed, stratify=labels_all
    )
    labels_temp = [ex["label"] for ex in temp]
    val_data, test_data = train_test_split(
        temp, test_size=val_ratio, random_state=seed, stratify=labels_temp
    )
    print("Split del dataset:")
    print(f"  Train: {len(train_data)} ejemplos")
    print(f"  Val:   {len(val_data)} ejemplos")
    print(f"  Test:  {len(test_data)} ejemplos")
    return train_data, val_data, test_data


def show_split_stats(data: list[dict], name: str) -> None:
    """Muestra distribución de etiquetas y estadísticas de longitud de un split."""
    df = pd.DataFrame(data)
    print(f"\n{'='*55}")
    print(f"  {name} ({len(df)} ejemplos)")
    print(f"{'='*55}")
    print(df["label"].value_counts().to_string())
    print(f"  Longitud media query:    {df['query'].str.len().mean():.0f} chars")
    print(f"  Longitud media document: {df['document'].str.len().mean():.0f} chars")


# ──────────────────────────────────────────────────────────────
# Prompt
# ──────────────────────────────────────────────────────────────

def build_grading_messages(query: str, document: str) -> list[dict]:
    """Construye los mensajes en formato chat para el modelo de grading."""
    return [
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


def format_training_prompt(example: dict, tokenizer) -> str:
    """
    Convierte un ejemplo del dataset en el texto completo de entrenamiento,
    incluyendo la respuesta del assistant y el token de fin de secuencia.
    """
    messages = build_grading_messages(example["query"], example["document"])
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    text += example["label"] + tokenizer.eos_token
    return text


def examples_to_hf_dataset(examples: list[dict], tokenizer):
    """Convierte la lista de ejemplos a un Dataset de HuggingFace con columna 'text'."""
    from datasets import Dataset
    records = [{"text": format_training_prompt(ex, tokenizer)} for ex in examples]
    return Dataset.from_list(records)


# ──────────────────────────────────────────────────────────────
# Modelo
# ──────────────────────────────────────────────────────────────

def load_tokenizer(model_id: str):
    """Carga y configura el tokenizador de Qwen 2.5. Padding side: right."""
    from transformers import AutoTokenizer
    print("Cargando tokenizador...")
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    tokenizer.pad_token    = tokenizer.eos_token
    tokenizer.padding_side = "right"
    print(f"Tokenizador listo. Vocabulario: {tokenizer.vocab_size:,} tokens")
    return tokenizer


def load_model_4bit(model_id: str, for_training: bool = False):
    """
    Carga el modelo base en cuantización 4-bit NF4 (QLoRA).
    - for_training=False  → modo evaluación, model.eval()
    - for_training=True   → modo entrenamiento, use_cache=False
    """
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    label = "entrenamiento (QLoRA)" if for_training else "evaluacion (4-bit)"
    print(f"Cargando {model_id} en 4-bit NF4 ({label})...")
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    if for_training:
        model.config.use_cache      = False
        model.config.pretraining_tp = 1
    else:
        model.eval()
    print(f"Modelo cargado. Dispositivo: {model.device}")
    return model


def build_peft_model(model, lora_r: int = 8, lora_alpha: int = 16, lora_dropout: float = 0.05):
    """
    Aplica LoRA al modelo base cuantizado para QLoRA fine-tuning.
    Devuelve (peft_model, lora_config).
    """
    from peft import prepare_model_for_kbit_training, LoraConfig, get_peft_model, TaskType

    model = prepare_model_for_kbit_training(model)
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        bias="none",
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",  # atencion multi-cabeza
            "gate_proj", "up_proj", "down_proj",       # feedforward SwiGLU
        ],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    return model, lora_config


def get_training_args(output_dir: str, num_epochs: int = 3, max_seq_len: int = 512):
    """
    Devuelve SFTConfig optimizado para QLoRA en GPU con >= 8 GB VRAM.
    Batch efectivo = 4 (per_device) x 4 (grad_accum) = 16.
    Usa SFTConfig (trl >= 0.12) en lugar de TrainingArguments para incluir
    los parámetros SFT-específicos (max_seq_length, dataset_text_field, packing).
    """
    from trl import SFTConfig

    args = SFTConfig(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        lr_scheduler_type="cosine",
        warmup_ratio=0.1,
        fp16=True,
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        report_to="none",
        seed=42,
        optim="paged_adamw_8bit",
        dataloader_pin_memory=False,
        # Parámetros SFT-específicos (movidos de SFTTrainer a SFTConfig en trl >= 0.12)
        max_seq_length=max_seq_len,
        dataset_text_field="text",
        packing=False,
    )
    print("TrainingArguments configurados:")
    print(f"  Epochs:         {args.num_train_epochs}")
    print(f"  Batch efectivo: {args.per_device_train_batch_size} x "
          f"{args.gradient_accumulation_steps} = "
          f"{args.per_device_train_batch_size * args.gradient_accumulation_steps}")
    print(f"  Learning rate:  {args.learning_rate}")
    print(f"  LR scheduler:   {args.lr_scheduler_type}")
    print(f"  Optimizador:    {args.optim}")
    return args


def run_training(model, training_args, train_dataset, val_dataset, tokenizer,
                 max_seq_len: int = 512):
    """
    Lanza el SFTTrainer (Supervised Fine-Tuning) y devuelve train_result.
    Imprime el número estimado de pasos antes de comenzar.
    Nota: training_args debe ser SFTConfig (incluye max_seq_length, dataset_text_field, packing).
    En trl >= 0.12, SFTTrainer ya no acepta esos kwargs directamente.
    """
    from trl import SFTTrainer

    trainer = SFTTrainer(
        model=model,
        args=training_args,          # SFTConfig con parámetros SFT incluidos
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        processing_class=tokenizer,  # 'tokenizer' renombrado a 'processing_class' en trl >= 0.12
    )
    steps = (
        len(train_dataset)
        // (training_args.per_device_train_batch_size * training_args.gradient_accumulation_steps)
        * training_args.num_train_epochs
    )
    print(f"Iniciando entrenamiento QLoRA... ({steps} pasos estimados)")
    result = trainer.train()
    print(f"\nEntrenamiento completado.")
    print(f"  Loss final:    {result.training_loss:.4f}")
    print(f"  Tiempo total:  {result.metrics.get('train_runtime', 0):.1f}s")
    return result


def save_adapter(model, tokenizer, adapter_path: str, metadata: dict) -> None:
    """Guarda el adaptador LoRA y un JSON de metadatos en adapter_path."""
    os.makedirs(adapter_path, exist_ok=True)
    model.save_pretrained(adapter_path)
    tokenizer.save_pretrained(adapter_path)
    print(f"Adaptador LoRA guardado en: {adapter_path}")

    meta_path = f"{adapter_path}/model_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"Metadatos guardados en: {meta_path}")


# ──────────────────────────────────────────────────────────────
# Evaluación
# ──────────────────────────────────────────────────────────────

def predict_relevance(
    query: str, document: str, model, tokenizer, max_new_tokens: int = 12
) -> str:
    """
    Predice si un documento es relevante para una consulta.
    Devuelve LABEL_RELEVANTE o LABEL_NO_RELEVANTE.
    Compatible con modelo base y modelo fine-tuneado (PEFT).
    """
    messages = build_grading_messages(query, document)
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
    elif "relevante" in response:
        return LABEL_RELEVANTE
    # Respuesta inesperada: conservador → no relevante
    return LABEL_NO_RELEVANTE


def evaluate_model(
    data: list[dict], model, tokenizer, name: str = "Modelo"
) -> tuple[float, float]:
    """
    Evalúa un modelo sobre el conjunto de datos dado.
    Imprime accuracy, F1-macro y classification_report.
    Devuelve (accuracy, f1_macro).
    """
    print(f"Evaluando {name} en {len(data)} ejemplos...")
    preds, true_labels = [], []

    for i, example in enumerate(data):
        pred = predict_relevance(example["query"], example["document"], model, tokenizer)
        preds.append(pred)
        true_labels.append(example["label"])
        if (i + 1) % 5 == 0:
            print(f"  {i + 1}/{len(data)} completados")

    acc = accuracy_score(true_labels, preds)
    f1  = f1_score(true_labels, preds, average="macro", zero_division=0)

    print(f"\n{'='*55}")
    print(f"{name}")
    print(f"{'='*55}")
    print(f"Accuracy:  {acc:.4f}")
    print(f"F1-macro:  {f1:.4f}")
    print()
    print(classification_report(true_labels, preds, labels=LABELS, zero_division=0))
    return acc, f1


def print_comparison(
    baseline_acc: float, baseline_f1: float,
    finetuned_acc: float, finetuned_f1: float,
) -> tuple[float, float]:
    """
    Imprime tabla comparativa baseline vs fine-tuned.
    Devuelve (mejora_acc, mejora_f1).
    """
    mejora_acc = finetuned_acc - baseline_acc
    mejora_f1  = finetuned_f1  - baseline_f1

    comparison = pd.DataFrame({
        "Modelo": [
            "Qwen 2.5 3B-Instruct (baseline, prompting)",
            "Qwen 2.5 3B-Instruct + QLoRA (fine-tuned)",
            "Mejora",
        ],
        "Accuracy": [baseline_acc, finetuned_acc, mejora_acc],
        "F1-macro": [baseline_f1,  finetuned_f1,  mejora_f1],
    }).set_index("Modelo").round(4)

    print("\nComparativa de modelos:")
    print(comparison.to_string())

    if mejora_f1 > 0:
        pct = mejora_f1 / (baseline_f1 + 1e-9) * 100
        print(f"\nEl fine-tuning mejora el F1-macro en {mejora_f1:+.4f} ({pct:.1f}% relativo).")
    else:
        print(f"\nEl fine-tuning no mejoro el baseline (Delta F1-macro = {mejora_f1:+.4f}).")
        print("  Posibles causas: dataset pequeno, hiperparametros, prompt no optimo.")

    return mejora_acc, mejora_f1


# ──────────────────────────────────────────────────────────────
# MLflow
# ──────────────────────────────────────────────────────────────

def get_mlflow_password() -> str:
    """
    Obtiene MLFLOW_PASSWORD desde:
    - Colab Secrets (si está en Colab)
    - Variable de entorno / archivo .env (entorno local)
    """
    try:
        from google.colab import userdata  # type: ignore[import]
        password = userdata.get("MLFLOW_PASSWORD")
        if password:
            print("Password obtenida desde Colab Secrets.")
            return password
    except ImportError:
        pass

    password = os.getenv("MLFLOW_PASSWORD")
    if password:
        print("Password obtenida desde variable de entorno local.")
        return password

    raise EnvironmentError(
        "No se encontro MLFLOW_PASSWORD.\n"
        "En Colab: configurar en Colab Secrets.\n"
        "En local: anadir MLFLOW_PASSWORD al archivo .env."
    )


def log_experiment(
    baseline_acc: float,
    baseline_f1: float,
    finetuned_acc: float,
    finetuned_f1: float,
    train_loss: float,
    train_size: int,
    val_size: int,
    test_size: int,
    training_args=None,
    lora_config=None,
    max_seq_len: int = 512,
) -> None:
    """
    Registra parámetros y métricas del experimento en MLflow.
    training_args y lora_config son opcionales — si no se pasan,
    se omiten esos parámetros del registro (útil al ejecutar NB4 standalone).
    """
    import mlflow

    mejora_f1 = finetuned_f1 - baseline_f1

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

    params: dict = {
        "model_id":    "Qwen/Qwen2.5-3B-Instruct",
        "max_seq_len": max_seq_len,
        "train_size":  train_size,
        "val_size":    val_size,
        "test_size":   test_size,
    }
    if lora_config is not None:
        params.update({
            "lora_r":         lora_config.r,
            "lora_alpha":     lora_config.lora_alpha,
            "lora_dropout":   lora_config.lora_dropout,
            "target_modules": ",".join(lora_config.target_modules),
        })
    if training_args is not None:
        params.update({
            "epochs":              training_args.num_train_epochs,
            "learning_rate":       training_args.learning_rate,
            "batch_size_efectivo": (
                training_args.per_device_train_batch_size
                * training_args.gradient_accumulation_steps
            ),
        })

    with mlflow.start_run(run_name="qwen25-3b-qlora-grader") as run:
        mlflow.log_params(params)
        mlflow.log_metrics({
            "baseline_accuracy":  baseline_acc,
            "baseline_f1_macro":  baseline_f1,
            "finetuned_accuracy": finetuned_acc,
            "finetuned_f1_macro": finetuned_f1,
            "mejora_f1_macro":    mejora_f1,
            "train_loss":         train_loss,
        })
        print("Metricas registradas en MLflow.")
        print(f"  Experimento: {MLFLOW_EXPERIMENT_NAME}")
        print(f"  Run ID:      {run.info.run_id}")
        print(f"  URI:         {tracking_uri}")
