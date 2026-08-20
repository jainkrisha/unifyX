from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import recordlinkage
from recordlinkage.datasets import load_febrl4
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split


def train_match_model(output_path: Path) -> dict[str, float]:
    """Train a simple probabilistic matching model and persist its coefficients."""
    df_a, df_b, true_links = load_febrl4(return_links=True)

    indexer = recordlinkage.Index()
    indexer.block("postcode")
    candidate_pairs = indexer.index(df_a, df_b)

    compare = recordlinkage.Compare()
    compare.string("given_name", "given_name", method="jarowinkler", label="name_sim")
    compare.string("surname", "surname", method="jarowinkler", label="surname_sim")
    compare.exact("date_of_birth", "date_of_birth", label="dob_match")
    compare.string("address_1", "address_1", method="jarowinkler", label="addr_sim")
    compare.exact("soc_sec_id", "soc_sec_id", label="ssn_match")

    features = compare.compute(candidate_pairs, df_a, df_b)
    labels = np.asarray(candidate_pairs.isin(true_links), dtype=int)

    X_train, X_test, y_train, y_test = train_test_split(
        np.asarray(features),
        labels,
        test_size=0.3,
        random_state=42,
        stratify=labels,
    )

    validation_model = LogisticRegression(max_iter=1000, class_weight="balanced")
    validation_model.fit(X_train, y_train)

    y_pred = validation_model.predict(X_test)
    print("\nClassification report:\n")
    print(classification_report(y_test, y_pred))
    print("\nConfusion matrix (rows=actual, cols=predicted):")
    print(confusion_matrix(y_test, y_pred))
    tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
    print(f"False positives: {fp}, False negatives: {fn}")
    print("\nCoefficient dict:\n")
    print(dict(zip(features.columns, validation_model.coef_[0])))

    final_model = LogisticRegression(max_iter=1000, class_weight="balanced")
    final_model.fit(np.asarray(features), labels)

    weights_config = {
        "pan_match": float(final_model.coef_[0][4]),
        "name_similarity": float(final_model.coef_[0][0]),
        "surname_similarity": float(final_model.coef_[0][1]),
        "dob_match": float(final_model.coef_[0][2]),
        "address_similarity": float(final_model.coef_[0][3]),
        "intercept": float(final_model.intercept_[0]),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(weights_config, indent=2), encoding="utf-8")

    print("\nWeights JSON:\n")
    print(json.dumps(weights_config, indent=2))
    return weights_config


if __name__ == "__main__":
    backend_root = Path(__file__).resolve().parents[1]
    train_match_model(backend_root / "match_weights.json")
