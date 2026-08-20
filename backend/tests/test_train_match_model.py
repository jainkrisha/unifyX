import importlib.util
import json
from pathlib import Path

import numpy as np
import recordlinkage
from recordlinkage.datasets import load_febrl4
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split


def build_features_and_labels():
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
    row_ids = np.arange(len(candidate_pairs))
    return np.asarray(features), labels, row_ids


def test_train_test_split_has_no_overlap_and_preserves_all_rows():
    X, y, row_ids = build_features_and_labels()
    X_train, X_test, y_train, y_test, train_ids, test_ids = train_test_split(
        X,
        y,
        row_ids,
        test_size=0.3,
        random_state=42,
        stratify=y,
    )

    assert len(train_ids) + len(test_ids) == len(row_ids)
    assert set(train_ids).isdisjoint(set(test_ids))
    assert set(train_ids).union(set(test_ids)) == set(row_ids)

    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    assert len(y_pred) == len(y_test)


def test_model_has_strong_holdout_validation_metrics():
    X, y, _ = build_features_and_labels()
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.3,
        random_state=42,
        stratify=y,
    )

    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()

    assert accuracy >= 0.99
    assert precision >= 0.99
    assert recall >= 0.99
    assert f1 >= 0.99
    assert fp <= 2
    assert fn <= 10

    coef = model.coef_[0]
    assert coef[0] > 0
    assert coef[1] > 0
    assert coef[2] > 0
    assert coef[3] > 0
    assert coef[4] > 0


def test_training_script_generates_valid_match_weights(tmp_path):
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "train_match_model.py"
    spec = importlib.util.spec_from_file_location("train_match_model", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    output_path = tmp_path / "match_weights.json"
    weights = module.train_match_model(output_path)

    assert output_path.exists()
    assert set(weights.keys()) == {
        "pan_match",
        "name_similarity",
        "surname_similarity",
        "dob_match",
        "address_similarity",
        "intercept",
    }

    with output_path.open("r", encoding="utf-8") as fh:
        saved = json.load(fh)

    assert saved == weights
    assert all(np.isfinite(list(weights.values())))
    assert weights["name_similarity"] > 0
    assert weights["surname_similarity"] > 0
    assert weights["dob_match"] > 0
    assert weights["address_similarity"] > 0
    assert weights["pan_match"] > 0
