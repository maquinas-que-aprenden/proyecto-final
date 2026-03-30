"""_calibrated_model.py — Clase wrapper para XGBoost con calibración isotónica.

Definida en módulo propio para que joblib pueda deserializarla correctamente
independientemente de cómo se ejecute el script de calibración.
"""

from __future__ import annotations

import numpy as np


class IsotonicCalibratedXGB:
    """Wrapper de XGBoost con calibración isotónica one-vs-rest.

    Implementa la misma interfaz que XGBClassifier para que main.py
    pueda cargarlo sin cambios: predict(), predict_proba(), classes_,
    n_features_in_, feature_importances_, get_booster().
    """

    def __init__(self, xgb_model, calibrators: list, classes_: np.ndarray):
        self._xgb = xgb_model
        self._calibrators = calibrators
        self.classes_ = classes_
        self.n_features_in_ = xgb_model.n_features_in_
        self.feature_importances_ = xgb_model.feature_importances_

    def get_booster(self):
        """Devuelve el booster XGBoost original (usado para SHAP en main.py)."""
        return self._xgb.get_booster()

    def predict_proba(self, X) -> np.ndarray:
        raw = self._xgb.predict_proba(X)
        calibrated = np.column_stack([
            self._calibrators[i].predict(raw[:, i])
            for i in range(len(self._calibrators))
        ])
        totals = calibrated.sum(axis=1, keepdims=True)
        totals = np.where(totals == 0, 1, totals)
        return calibrated / totals

    def predict(self, X) -> np.ndarray:
        proba = self.predict_proba(X)
        return self.classes_[np.argmax(proba, axis=1)]
