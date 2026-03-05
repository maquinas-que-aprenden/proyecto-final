"""classifier/main.py — Servicio de clasificacion de riesgo EU AI Act.

Carga el modelo serializado entrenado en el dataset fusionado y expone
``predict_risk(text) -> dict`` para que el orquestador lo invoque como tool.

Seleccion de modelo: Se entrenaron y evaluaron tres variantes (LogReg,
LogReg+features manuales, XGBoost+SVD) con Grid Search + StratifiedKFold.
Los tres experimentos estan registrados en MLflow. El modelo seleccionado
se determina por ``mejor_modelo_seleccion.json``. Actualmente:
Exp 2 (XGBoost + SVD + GS) con F1-macro test 0.8822.

Pipeline de inferencia: texto → TF-IDF → SVD(100) + 7 keywords → XGBoost.

Artefactos requeridos en ``classifier_dataset_fusionado/model/``:
- mejor_modelo_seleccion.json  (metadatos del experimento ganador)
- modelo_xgboost.joblib        (XGBClassifier seleccionado)
- tfidf_vectorizer.joblib      (TfidfVectorizer, vocab ~3773, bigramas)
- svd_transformer.joblib       (TruncatedSVD, 100 componentes)
- label_encoder.joblib         (LabelEncoder, opcional)
"""

from __future__ import annotations

import json
import logging
import re as _re
import threading
from pathlib import Path

import joblib
import numpy as np
from pydantic import BaseModel, Field
from src.checklist.main import SEVERITY
from src.classifier._constants import (
    KEYWORDS_DOMINIO as _KEYWORDS_DOMINIO,
    PALABRAS_SUPERVISION as _PALABRAS_SUPERVISION,
    RISK_LABELS as _RISK_LABELS,
)
from src.observability.langfuse_compat import observe, langfuse_context

logger = logging.getLogger(__name__)


class _TextInput(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


# Patrones del Anexo III para override determinista post-predicción ML.
# Se compilan una sola vez y se aplican sobre el texto ORIGINAL (sin limpiar).
_ANNEX3_PATTERNS: list | None = None


def _build_annex3_patterns() -> list:
    """Compila los patrones del Anexo III EU AI Act (llamada lazy, una sola vez).

    IMPORTANTE — SINCRONIZACIÓN CON create_normative_features.py:
    Ese módulo define patrones equivalentes para Art. 5.1.a–5.1.e usados al
    enriquecer el dataset de entrenamiento. Si se modifica algún patrón aquí,
    revisar create_normative_features.py para mantener coherencia entre
    entrenamiento e inferencia. Ver [I1] en audit_errores_classifier.md.
    """
    raw = [
        # ALTO RIESGO — Anexo III
        (r"(cv|curr[ií]culum|curricular).{0,60}(screening|selecci[oó]n|filtr|evaluaci[oó]n|clasificaci[oó]n)",
         "alto_riesgo", "Anexo III cat. 4.a"),
        (r"(selecci[oó]n|reclutamiento|contrataci[oó]n).{0,50}(personal|candidat|empleo|trabajador)",
         "alto_riesgo", "Anexo III cat. 4.a"),
        (r"(scoring|puntuaci[oó]n|calificaci[oó]n).{0,40}(creditici|cr[eé]dit|solvencia|pr[eé]stamo|hipoteca)",
         "alto_riesgo", "Anexo III cat. 5.b"),
        (r"concesi[oó]n.{0,40}(pr[eé]stamo|cr[eé]dit|hipoteca)",
         "alto_riesgo", "Anexo III cat. 5.b"),
        (r"(recidiv|reincidenci|reincidente)",
         "alto_riesgo", "Anexo III cat. 6"),
        (r"predicci[oó]n.{0,40}(delito|crimen|criminalidad|peligrosidad)",
         "alto_riesgo", "Anexo III cat. 6"),
        (r"(solicitud|evaluaci[oó]n|decisi[oó]n).{0,40}(asilo|visa|migraci[oó]n|refugiado)",
         "alto_riesgo", "Anexo III cat. 7"),
        (r"admisi[oó]n.{0,40}(universitari|educativ|escolar|academi)",
         "alto_riesgo", "Anexo III cat. 3"),
        (r"(apoyo|asistencia).{0,40}(juez|tribunal|sentencia|resoluc.{0,10}judicial)",
         "alto_riesgo", "Anexo III cat. 8"),
        # INACEPTABLE — Art. 5 EU AI Act
        # Art. 5.1.a — Manipulación subliminal o engañosa
        (r"(manipulaci[oó]n|t[eé]cnica).{0,20}subliminal",
         "inaceptable", "Art. 5.1.a"),
        (r"subliminal.{0,40}(comportamiento|conducta|decisi[oó]n)",
         "inaceptable", "Art. 5.1.a"),
        # Art. 5.1.b — Explotación de vulnerabilidades
        (r"(exploit|explot\w*|explotaci[oó]n|aprovech).{0,30}(vulnerabilidad|discapacidad|menor.{0,10}edad|tercera.{0,10}edad)",
         "inaceptable", "Art. 5.1.b"),
        (r"(menor.{0,15}edad|persona.{0,15}(vulnerabl|discapacidad)).{0,50}(manipul|influenc|coacci|engañ)",
         "inaceptable", "Art. 5.1.b"),
        # Art. 5.1.c — Puntuación social ciudadana por autoridades públicas
        (r"puntuaci[oó]n.{0,30}social.{0,30}ciudadano",
         "inaceptable", "Art. 5.1.c"),
        (r"sistema.{0,20}(cr[eé]dito|scoring).{0,20}social.{0,30}(ciudadano|poblaci[oó]n|persona)",
         "inaceptable", "Art. 5.1.c"),
        # Art. 5.1.d — Identificación biométrica en tiempo real en espacios públicos
        (r"(reconocimiento|identificaci[oó]n).{0,30}(facial|biom[eé]tric).{0,50}(espacio.{0,10}p[uú]blic|tiempo.{0,10}real|calle|multitud)",
         "inaceptable", "Art. 5.1.d"),
        (r"vigilancia.{0,30}biom[eé]tric.{0,30}(masiva|tiempo.{0,10}real|p[uú]blic)",
         "inaceptable", "Art. 5.1.d"),
        # Art. 5.1.e — Perfilado policial predictivo sin indicios concretos
        (r"predicci[oó]n.{0,40}(delito|peligrosidad|criminal).{0,40}(sin.{0,20}indicio|sin.{0,20}prueba|preventiv).{0,20}(policial|penal)",
         "inaceptable", "Art. 5.1.e"),
        (r"perfilado.{0,30}(racial|[eé]tnico|conductual).{0,40}(policial|delictiv|criminal)",
         "inaceptable", "Art. 5.1.e"),
        (r"riesgo.{0,20}delictivo.{0,30}(personalidad|caracter[ií]sticas.{0,20}personal|perfil).{0,30}sin.{0,20}(indicio|hecho|prueba)",
         "inaceptable", "Art. 5.1.e"),
    ]
    return [(_re.compile(p, _re.IGNORECASE | _re.DOTALL), lvl, ref) for p, lvl, ref in raw]


def _annex3_override(text: str, result: dict) -> dict:
    """Post-procesa la predicción ML aplicando reglas deterministas del Anexo III.

    Si el texto encaja con un patrón canónico del Anexo III y la predicción
    difiere, sobrescribe risk_level para garantizar clasificación correcta en
    los casos explícitamente enumerados en la ley, independientemente de la
    confianza del modelo.
    """
    global _ANNEX3_PATTERNS
    if _ANNEX3_PATTERNS is None:
        _ANNEX3_PATTERNS = _build_annex3_patterns()

    best_level: str | None = None
    best_ref: str | None = None
    for pattern, expected_level, legal_ref in _ANNEX3_PATTERNS:
        if pattern.search(text):
            if best_level is None or SEVERITY[expected_level] > SEVERITY[best_level]:
                best_level = expected_level
                best_ref = legal_ref

    if best_level is not None and result["risk_level"] != best_level:
        logger.info(
            "Anexo III override: ML='%s' (%.0f%%) → '%s' [%s]",
            result["risk_level"], result["confidence"] * 100,
            best_level, best_ref,
        )
        overridden = result.copy()
        overridden["risk_level"] = best_level
        overridden["confidence"] = 0.85
        # Recalibrar probabilities para ser coherentes con el nivel final.
        # El nivel sobreescrito recibe 0.85; el resto se reparte equitativamente.
        if result.get("probabilities"):
            keys = set(result["probabilities"].keys()) | {best_level}
            n = len(keys)
            resto = round((1.0 - 0.85) / max(n - 1, 1), 4)
            overridden["probabilities"] = {
                k: (0.85 if k == best_level else resto)
                for k in keys
            }
        overridden["annex3_override"] = True
        overridden["annex3_ref"] = best_ref
        overridden["ml_prediction"] = {
            "risk_level": result["risk_level"],
            "confidence": result["confidence"],
            "probabilities": result.get("probabilities", {}),
        }
        # Los features SHAP corresponden a la predicción ML, no al nivel legal.
        # Se mueven a ml_prediction para no contaminar la explicación del override.
        if "shap_top_features" in overridden:
            overridden["ml_prediction"]["shap_top_features"] = overridden.pop("shap_top_features")
        # La explicación legal prevalece: se establece aquí para que esté disponible
        # tanto cuando se llama predict_risk() como en tests directos de esta función.
        overridden["shap_explanation"] = (
            f"Clasificación determinada por {best_ref} EU AI Act. "
            f"La capa normativa prevalece sobre la predicción del modelo ML."
        )
        return overridden
    return result


# _KEYWORDS_DOMINIO y _PALABRAS_SUPERVISION importados desde _constants (ver bloque _RISK_LABELS arriba)

# Ruta al mejor modelo (dataset fusionado)
_MODEL_DIR = Path(__file__).parent / "classifier_dataset_fusionado" / "model"

# Mapping canónico de etiquetas numéricas → textuales (EU AI Act)
# Fallback cuando el modelo no incluye label_encoder.joblib.
# Fuente de verdad: src/classifier/_constants.py
try:
    from src.classifier._constants import RISK_LABELS as _RISK_LABELS
    from src.classifier._constants import KEYWORDS_DOMINIO as _KEYWORDS_DOMINIO
    from src.classifier._constants import PALABRAS_SUPERVISION as _PALABRAS_SUPERVISION
except ImportError:
    from ._constants import RISK_LABELS as _RISK_LABELS
    from ._constants import KEYWORDS_DOMINIO as _KEYWORDS_DOMINIO
    from ._constants import PALABRAS_SUPERVISION as _PALABRAS_SUPERVISION

# Singletons — se cargan en el primer uso (thread-safe)
_modelo = None
_tfidf = None
_svd = None
_label_encoder = None
_pipeline_type: str = "tfidf_only"  # auto-detectado en _load_artifacts()
_lock = threading.Lock()


def _validate_pipeline(pipeline_type: str, n_features: int) -> None:
    """Valida que los artefactos cargados son coherentes con n_features_in_ del modelo.

    Emite un warning si hay discrepancia — indica que el modelo y los
    artefactos de transformacion provienen de experimentos distintos.
    """
    if pipeline_type == "tfidf_svd_manual":
        n_manual = 2 + len(_KEYWORDS_DOMINIO) + 1  # num_palabras, num_chars, kw por clase, kw_salvaguarda
        expected = _svd.n_components + n_manual
    elif pipeline_type == "tfidf_svd":
        expected = _svd.n_components
    else:  # "tfidf_only"
        expected = len(_tfidf.get_feature_names_out())

    if n_features != expected:
        logger.warning(
            "Pipeline '%s': n_features_in_=%d pero calculado=%d. "
            "El modelo se cargo con artefactos distintos a los actuales.",
            pipeline_type, n_features, expected,
        )


def _load_artifacts():
    """Carga lazy de modelo, TF-IDF y SVD (thread-safe, double-check locking).

    Auto-detecta el tipo de pipeline segun los artefactos presentes en disco
    y la metadata de mejor_modelo_seleccion.json, sin necesidad de configuracion
    manual al cambiar de modelo.
    """
    global _modelo, _tfidf, _svd, _label_encoder, _pipeline_type
    if _modelo is not None and _tfidf is not None:
        return
    with _lock:
        if _modelo is not None and _tfidf is not None:
            return

        needs_manual_features = False
        explicit_pipeline: str | None = None
        meta_path = _MODEL_DIR / "mejor_modelo_seleccion.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("mejor_modelo_seleccion.json ilegible (%s); usando rutas por defecto.", exc)
                meta = {}
            model_file = _MODEL_DIR.parent / meta.get("model_file", "model/modelo_xgboost.joblib")
            tfidf_file = _MODEL_DIR.parent / meta.get("tfidf_file", "model/tfidf_vectorizer.joblib")
            needs_manual_features = meta.get("needs_manual_features", False)
            explicit_pipeline = meta.get("pipeline_type")
            logger.info("Cargando modelo desde metadata: %s", meta.get("nombre", ""))
        else:
            model_file = _MODEL_DIR / "mejor_modelo.joblib"
            tfidf_file = _MODEL_DIR / "mejor_modelo_tfidf.joblib"

        try:
            _modelo = joblib.load(model_file)
            _tfidf = joblib.load(tfidf_file)

            svd_path = _MODEL_DIR / "svd_transformer.joblib"
            if svd_path.exists():
                _svd = joblib.load(svd_path)

            le_path = _MODEL_DIR / "label_encoder.joblib"
            if le_path.exists():
                _label_encoder = joblib.load(le_path)

            # Determinar tipo de pipeline.
            # Se usa "pipeline_type" del JSON si está presente (fuente de verdad).
            # El directorio puede contener artefactos de múltiples experimentos
            # (svd_transformer.joblib existe aunque el modelo activo no lo use),
            # por lo que la auto-detección por presencia de archivos no es fiable.
            if explicit_pipeline in ("tfidf_only", "tfidf_svd", "tfidf_svd_manual"):
                _pipeline_type = explicit_pipeline
            elif _svd is not None and needs_manual_features:
                _pipeline_type = "tfidf_svd_manual"
            elif _svd is not None:
                _pipeline_type = "tfidf_svd"
            else:
                _pipeline_type = "tfidf_only"

        except Exception:
            _modelo = _tfidf = _svd = _label_encoder = None
            _pipeline_type = "tfidf_only"
            raise

        _validate_pipeline(_pipeline_type, _modelo.n_features_in_)
        logger.info(
            "Clasificador cargado: %s (%d features, pipeline=%s) desde %s",
            type(_modelo).__name__,
            _modelo.n_features_in_,
            _pipeline_type,
            _MODEL_DIR,
        )


def _limpiar_texto_fallback(texto: str) -> str:
    """Limpieza basica con regex (misma logica que functions._limpiar_texto_fallback)."""
    import re

    if not texto or not isinstance(texto, str):
        return ""

    _stopwords = {
        "a", "al", "algo", "algunas", "algunos", "ante", "antes", "como",
        "con", "contra", "cual", "cuando", "de", "del", "desde", "donde",
        "durante", "e", "el", "ella", "ellos", "en", "entre", "era", "es",
        "esa", "esas", "ese", "eso", "esos", "esta", "estas", "este", "esto",
        "estos", "fue", "ha", "han", "hasta", "hay", "he", "la", "las", "le",
        "les", "lo", "los", "me", "mi", "mis", "muy", "ni", "no", "nos",
        "o", "os", "otro", "para", "pero", "por", "que", "quien", "quienes",
        "se", "si", "sin", "sobre", "son", "su", "sus", "también", "tanto",
        "te", "todo", "todos", "tu", "tus", "un", "una", "unas", "uno",
        "unos", "ya", "yo",
    }
    tokens = re.findall(r"\b[a-záéíóúüñ]{3,}\b", texto.lower())
    return " ".join(t for t in tokens if t not in _stopwords)


def _limpiar_texto(texto: str) -> str:
    """Limpia texto para inferencia, usando spaCy si esta disponible."""
    try:
        from src.classifier.functions import limpiar_texto
        return limpiar_texto(texto)
    except ImportError:
        return _limpiar_texto_fallback(texto)


def _crear_features_manuales(text: str) -> np.ndarray:
    """Genera las features de keywords para el pipeline XGBoost+SVD.

    El numero de features es dinamico: 2 generales + len(_KEYWORDS_DOMINIO)
    categorias + 1 supervision. Si se añaden categorias al dict, el conteo
    se actualiza automaticamente sin cambiar este codigo.
    """
    words = text.split()
    features = [
        len(words),   # num_palabras
        len(text),    # num_caracteres
    ]
    for keywords in _KEYWORDS_DOMINIO.values():
        features.append(sum(1 for kw in keywords if kw in words))
    features.append(sum(1 for kw in _PALABRAS_SUPERVISION if kw in words))
    return np.array(features, dtype=float).reshape(1, -1)


def _build_features(cleaned_text: str) -> tuple[object, list[str]]:
    """Construye el vector de features para inferencia segun el pipeline cargado.

    No requiere mantenimiento manual al cambiar de modelo: lee el numero de
    features directamente de los artefactos cargados (_tfidf, _svd).
    Si el modelo reentrenado tiene mas vocabulario o mas componentes SVD,
    esta funcion se adapta automaticamente.

    Returns
    -------
    X_final : sparse matrix o np.ndarray con shape (1, n_features_in_)
    feature_names : list[str] con los nombres de cada feature (para explicabilidad)

    Raises
    ------
    ValueError
        Si los artefactos en disco son inconsistentes con el modelo cargado.
        Indica que modelo y transformadores provienen de experimentos distintos.
    """
    X_tfidf = _tfidf.transform([cleaned_text])

    if _pipeline_type == "tfidf_svd_manual":
        X_svd = _svd.transform(X_tfidf)
        X_manual = _crear_features_manuales(cleaned_text)
        X_final = np.hstack([X_svd, X_manual])
        feature_names = (
            [f"svd_{i}" for i in range(_svd.n_components)]
            + ["num_palabras", "num_caracteres"]
            + [f"kw_{c}" for c in _KEYWORDS_DOMINIO]
            + ["kw_salvaguarda"]
        )
    elif _pipeline_type == "tfidf_svd":
        X_final = _svd.transform(X_tfidf)
        feature_names = [f"svd_{i}" for i in range(_svd.n_components)]
    else:  # "tfidf_only"
        X_final = X_tfidf
        feature_names = _tfidf.get_feature_names_out().tolist()

    # Validacion defensiva: artefactos inconsistentes deben fallar rapido,
    # no dar predicciones silenciosamente incorrectas.
    n_expected = _modelo.n_features_in_
    n_actual = X_final.shape[1]
    if n_actual != n_expected:
        raise ValueError(
            f"Feature mismatch para pipeline '{_pipeline_type}': "
            f"modelo espera {n_expected} features, construidas {n_actual}. "
            f"Los artefactos en disco son inconsistentes con el modelo cargado. "
            f"Solucion: re-exportar todos los artefactos del mismo experimento."
        )

    return X_final, feature_names


@observe(name="classifier.predict_risk")
def predict_risk(text: str) -> dict:
    """Clasifica un sistema de IA por nivel de riesgo EU AI Act.

    Parameters
    ----------
    text : str
        Descripcion del sistema de IA en lenguaje natural.

    Returns
    -------
    dict
        risk_level: str (alto_riesgo | inaceptable | riesgo_limitado | riesgo_minimo)
        confidence: float (0-1)
        shap_top_features: list[dict] (top 5 features por contribucion)
        shap_explanation: str (resumen textual)
    """
    _TextInput(text=text)
    _load_artifacts()

    # 1. Limpiar texto (mismo preprocesado que en entrenamiento)
    cleaned = _limpiar_texto(text)

    # 2. Construir features segun el pipeline auto-detectado al cargar
    X_final, feature_names = _build_features(cleaned)

    # 3. Prediccion
    raw_pred = _modelo.predict(X_final)[0]
    proba = _modelo.predict_proba(X_final)[0]
    confidence = float(proba.max())

    # Decodificar etiqueta numerica a string si hay label encoder
    if _label_encoder is not None and not isinstance(raw_pred, str):
        risk_level = _label_encoder.inverse_transform([raw_pred])[0]
        class_names = _label_encoder.inverse_transform(_modelo.classes_)
    else:
        risk_level = _RISK_LABELS.get(str(raw_pred), str(raw_pred))
        class_names = [_RISK_LABELS.get(str(c), str(c)) for c in _modelo.classes_]

    result = {
        "risk_level": risk_level,
        "confidence": confidence,
        "probabilities": {
            str(cls): round(float(p), 4)
            for cls, p in zip(class_names, proba)
        },
    }

    # 4. Explicabilidad — top features por contribucion
    try:
        if hasattr(_modelo, "coef_"):
            # LogReg: contribuciones lineales.
            # Se usa raw_pred (valor numérico original) en lugar de risk_level
            # (string ya decodificado) para evitar ValueError cuando el modelo
            # fue entrenado con LabelEncoder y _modelo.classes_ son integers.
            pred_idx = list(_modelo.classes_).index(raw_pred)
            coefs = _modelo.coef_[pred_idx]
            X_dense = X_final.toarray().flatten() if hasattr(X_final, "toarray") else X_final.flatten()
            contributions = coefs * X_dense
        elif hasattr(_modelo, "feature_importances_"):
            # XGBoost: contribuciones nativas via pred_contribs (sin dependencia shap)
            import xgboost as xgb
            pred_idx = list(_modelo.classes_).index(raw_pred)
            X_dense = X_final.toarray() if hasattr(X_final, "toarray") else X_final
            dm = xgb.DMatrix(X_dense)
            raw_contribs = _modelo.get_booster().predict(dm, pred_contribs=True)
            # Forma: (n_samples, n_features+1) binario
            #        (n_samples, n_classes, n_features+1) multiclase — ultimo col es bias
            if raw_contribs.ndim == 3:
                contributions = raw_contribs[0, pred_idx, :-1].astype(float)
            else:
                contributions = raw_contribs[0, :-1].astype(float)
        else:
            contributions = None

        if contributions is not None:
            top_idx = np.argsort(np.abs(contributions))[::-1][:5]
            shap_top = [
                {"feature": feature_names[i], "contribution": float(contributions[i])}
                for i in top_idx
                if i < len(feature_names) and contributions[i] != 0
            ]
            if shap_top:
                result["shap_top_features"] = shap_top
    except Exception as e:
        logger.warning("No se pudo calcular explicabilidad: %s", e)

    # Capa de override: patrones deterministas del Anexo III tienen precedencia sobre ML
    result = _annex3_override(text, result)

    # shap_explanation con override: ya establecida por _annex3_override().
    # shap_explanation sin override: basada en features del modelo, filtrando
    # componentes SVD y métricas de longitud no interpretables legalmente.
    if result.get("shap_top_features"):
        # Mismos criterios de filtrado que el orquestador (Bug 7):
        # svd_N y métricas de longitud no tienen significado legal para el usuario.
        _NO_INTERPRETAR_EXPL = {"num_palabras", "num_caracteres"}
        legibles = [
            f for f in result["shap_top_features"]
            if not f["feature"].startswith("svd_") and f["feature"] not in _NO_INTERPRETAR_EXPL
        ]
        if legibles:
            top_words = ", ".join(f["feature"] for f in legibles[:3])
            result["shap_explanation"] = (
                f"Factores principales para '{result['risk_level']}': {top_words}."
            )
        elif not result.get("shap_explanation"):
            # Todos los features son SVD u otras métricas internas no interpretables.
            # Se asigna un fallback claro en vez de omitir la explicación por completo.
            result["shap_explanation"] = (
                "No se identificaron factores interpretables específicos."
            )

    try:
        langfuse_context.update_current_observation(
            metadata={
                "risk_level": result["risk_level"],
                "confidence": round(result["confidence"], 4),
                "probabilities": result.get("probabilities", {}),
            },
        )
        langfuse_context.score_current_trace(
            name="classifier_confidence",
            value=result["confidence"],
            comment=result["risk_level"],
        )
    except Exception as e:
        logger.warning(
            "Langfuse no disponible, omitiendo observación (risk_level=%s, confidence=%.4f): %s",
            result["risk_level"],
            result["confidence"],
            e,
        )
    return result


if __name__ == "__main__":
    test_cases = [
        "Sistema de puntuacion social de ciudadanos",
        "Reconocimiento facial en aeropuertos para control de acceso",
        "Chatbot de atencion al cliente para una tienda online",
        "Filtro de spam de email corporativo",
        "Sistema de scoring crediticio para concesion de prestamos bancarios",
    ]
    for desc in test_cases:
        r = predict_risk(desc)
        print(f"  {r['risk_level']:>17} ({r['confidence']:.0%}) <- {desc}")
        if r.get("shap_top_features"):
            top = ", ".join(f["feature"] for f in r["shap_top_features"][:3])
            print(f"                    Factores: {top}")
        print()

    print("classifier/main.py OK")
