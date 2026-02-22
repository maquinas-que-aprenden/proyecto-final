# Estructura del módulo clasificador — `src/classifier/`

Reorganización realizada en el Día 8. El módulo se divide en dos pipelines independientes según el dataset usado, con código compartido en el nivel raíz.

---

## Árbol de carpetas

```
src/classifier/
│
├── functions.py                      ← Pipeline compartido (1200+ líneas)
├── feature.py                        ← Extracción de features (TF-IDF, NER, manual)
├── main.py                           ← API de inferencia (train / predict)
├── mlflow_stub.py                    ← Stub local para desarrollo sin servidor MLflow
├── .env                              ← Variables de entorno (GROQ_API_KEY, MLFLOW_URI...)
│
├── classifier_dataset_artificial/    ← Pipeline con dataset sintético (~300 muestras)
│   ├── datasets/
│   │   ├── dataset_riesgo.csv        ← Dataset original (elaboración propia, 300 muestras)
│   │   └── dataset_riesgo_limpio.csv ← Dataset tras limpieza inicial
│   ├── data/
│   │   ├── processed/
│   │   │   ├── train.csv             ← 70 % (210 muestras), estratificado
│   │   │   ├── validation.csv        ← 15 % (45 muestras)
│   │   │   └── test.csv              ← 15 % (45 muestras)
│   │   └── finetune/
│   │       ├── train.jsonl           ← Formato instrucción para QLoRA (80 %)
│   │       └── test.jsonl            ← Formato instrucción para QLoRA (20 %)
│   ├── model/
│   │   ├── mejor_modelo.joblib
│   │   ├── mejor_modelo_tfidf.joblib
│   │   ├── label_encoder.joblib
│   │   ├── model_metadata.json
│   │   ├── shap_beeswarm_*.png
│   │   └── shap_waterfall_*.png
│   ├── 1_analisis_exploratorio.ipynb
│   ├── 2_preprocesado y división.ipynb
│   ├── 3_entrenamiento.ipynb         ← Exp 0: LogReg + TF-IDF
│   ├── 4_metricas.ipynb
│   ├── 5_entrenamiento_v2.ipynb      ← Exp 1: LogReg + TF-IDF + features manuales
│   ├── 6_metricas_v2.ipynb
│   ├── 7_entrenamiento_v3.ipynb      ← Exp 2: XGBoost + Grid Search + k-fold
│   ├── 8_comparativa_final.ipynb
│   ├── 9_shap_explicabilidad.ipynb
│   ├── 10_modelo_final_y_registro.ipynb
│   ├── 11_preparacion_dataset_finetune.ipynb
│   └── 12_finetune_qlora.ipynb       ← Ejecutar en Google Colab T4
│
└── classifier_dataset_real/          ← Pipeline con dataset real (EU AI Act)
    ├── datasets/
    │   ├── eu_ai_act_flagged_es.csv
    │   └── eu_ai_act_flagged_es_limpio.csv
    ├── data/
    │   ├── processed/
    │   │   ├── train.csv
    │   │   ├── validation.csv
    │   │   └── test.csv
    │   └── finetune/
    │       ├── train.jsonl
    │       └── test.jsonl
    ├── model/
    │   ├── mejor_modelo.joblib
    │   ├── mejor_modelo_tfidf.joblib
    │   ├── ohe_encoder.joblib         ← Encoder adicional para features del dataset real
    │   ├── model_metadata.json
    │   ├── shap_beeswarm_*.png
    │   ├── shap_waterfall_*.png
    │   ├── qlora_adapter/             ← Adaptador LoRA entrenado
    │   │   ├── adapter_config.json
    │   │   ├── adapter_model.safetensors
    │   │   └── tokenizer*
    │   └── qlora_checkpoints/
    │       ├── checkpoint-100/
    │       └── checkpoint-180/
    ├── 0_traducir_dataset.ipynb       ← Traducción del dataset al español
    ├── 1_analisis_exploratorio.ipynb
    ├── 2_preprocesado y división.ipynb
    ├── 3_entrenamiento.ipynb
    ├── 4_metricas.ipynb
    ├── 5_entrenamiento_v2.ipynb
    ├── 6_metricas_v2.ipynb
    ├── 7_entrenamiento_v3.ipynb
    ├── 8_comparativa_final.ipynb
    ├── 9_shap_explicabilidad.ipynb
    ├── 10_modelo_final_y_registro.ipynb
    ├── 11_preparacion_dataset_finetune.ipynb
    └── 12_finetune_qlora.ipynb
```

---

## Diferencias entre los dos pipelines

| Aspecto | `classifier_dataset_artificial` | `classifier_dataset_real` |
|---------|:--------------------------------:|:-------------------------:|
| Dataset | `dataset_riesgo.csv` (300 muestras, elaboración propia) | `eu_ai_act_flagged_es.csv` (dataset real del EU AI Act) |
| Notebook 0 | No existe | `0_traducir_dataset.ipynb` (traducción ES) |
| Encoder adicional | No | `ohe_encoder.joblib` |
| Checkpoints QLoRA | No | `qlora_checkpoints/checkpoint-{100,180}/` |
| Mejor F1-macro test | 0.9530 (Exp 0 LogReg) | Ver `10_modelo_final_y_registro.ipynb` |

---

## Código compartido

`functions.py`, `feature.py`, `main.py`, `mlflow_stub.py` y `.env` son comunes a ambos pipelines y viven en `src/classifier/`.

Para que los notebooks los encuentren al importar, todos incluyen en su primera celda:

```python
import sys, os
sys.path.insert(0, os.path.abspath('..'))
```

### Funciones principales de `functions.py`

| Función | Propósito |
|---------|-----------|
| `limpiar_texto(text)` | Limpieza básica (puntuación, stopwords) |
| `limpiar_texto_preprocess(text)` | Limpieza + lematización spaCy |
| `extraer_entidades(df, col)` | NER con `es_core_news_lg` |
| `crear_tfidf(X_train, X_val, X_test)` | Ajuste y transformación TF-IDF |
| `crear_features_manuales(X_texts)` | Features de dominio (longitud, NER, keywords) |
| `combinar_features(X_tfidf, X_manual)` | `scipy.sparse.hstack` TF-IDF + manuales |
| `split_dataset(df, test_size, val_size)` | Split estratificado 70/15/15 |
| `entrenar_xgboost(X, y, params)` | XGBClassifier con evaluación en val |
| `grid_search_cv(modelo, param_grid, X, y)` | GridSearchCV con StratifiedKFold(k=5) |
| `explicar_con_shap(modelo, X_bg, X_exp)` | SHAP LinearExplainer / TreeExplainer |
| `plot_shap_summary(...)` | Beeswarm plot top-20 features por clase |
| `plot_shap_waterfall(...)` | Waterfall plot de predicciones individuales |
| `guardar_pipeline_completo(...)` | Serializa modelo + TF-IDF + metadata |
| `registrar_modelo_en_registry(...)` | Registra en MLflow Model Registry |
| `log_mlflow_safe(...)` | Helper con try/except para todos los notebooks |

---

## Razón de la separación en dos carpetas

El dataset sintético (`dataset_riesgo.csv`) fue el primer enfoque: elaboración propia de ~300 descripciones etiquetadas manualmente. El dataset real (`eu_ai_act_flagged_es.csv`) proviene del EU AI Act oficial, con etiquetado basado en los anexos del reglamento, y es más representativo del dominio.

Mantener los dos pipelines en paralelo permite:
- Comparar el impacto del dataset en las métricas finales
- Conservar el pipeline sintético como referencia de desarrollo
- Iterar sobre el dataset real sin alterar el baseline establecido
