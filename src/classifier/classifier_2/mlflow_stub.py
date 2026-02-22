"""classifier/mlflow.py — MLflow Tracking
Hello world: simula loguear un experimento de entrenamiento.
"""


def log_experiment(params: dict, metrics: dict) -> dict:
    # TODO: reemplazar con mlflow.set_experiment() + mlflow.start_run() + mlflow.log_params/metrics
    return {
        "experiment": "normabot-classifier",
        "run_id": "abc123def456",
        "params": params,
        "metrics": metrics,
        "tracking_uri": "file:///mlruns",
    }


if __name__ == "__main__":
    result = log_experiment(
        params={"model": "XGBClassifier", "n_estimators": 50, "max_depth": 3, "tfidf_max_features": 50},
        metrics={"f1_macro": 0.82, "accuracy": 0.85, "precision_macro": 0.80, "recall_macro": 0.84},
    )
    print(f"Experiment: {result['experiment']}")
    print(f"Run ID:     {result['run_id']}")
    print(f"URI:        {result['tracking_uri']}")
    print(f"Params:     {result['params']}")
    print(f"Metrics:    {result['metrics']}")
    print("Dashboard:  mlflow ui")

    print("\n✓ classifier/mlflow.py OK")
