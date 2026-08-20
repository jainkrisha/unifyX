"""Seed configuration entries into the database."""
import json
import os
from pathlib import Path
from sqlalchemy.orm import Session
from .db.session import SessionLocal
from .db.models import ConfigEntry, ConfigCategoryEnum


def load_match_weights():
    """Load match weights from match_weights.json or return defaults."""
    weights_file = Path(__file__).parent.parent / "match_weights.json"
    if weights_file.exists():
        try:
            with open(weights_file) as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load match_weights.json: {e}")
    
    # Default weights if file doesn't exist
    return {
        "pan_match": 2.5,
        "name_similarity": 1.8,
        "surname_similarity": 1.8,
        "dob_match": 2.0,
        "address_similarity": 1.2,
        "intercept": -0.5
    }


def seed_config(db: Session):
    """Seed all configuration entries into the database."""
    
    # Load match weights
    match_weights = load_match_weights()
    
    config_entries = [
        # MATCH_WEIGHTS
        {
            "category": ConfigCategoryEnum.MATCH_WEIGHTS,
            "key": "fuzzy_match_v1",
            "value": {
                "pan_match": match_weights.get("pan_match", 2.5),
                "name_similarity": match_weights.get("name_similarity", 1.8),
                "surname_similarity": match_weights.get("surname_similarity", 1.8),
                "dob_match": match_weights.get("dob_match", 2.0),
                "address_similarity": match_weights.get("address_similarity", 1.2),
                "mobile_match": match_weights.get("mobile_match", 2.0),
                "email_match": match_weights.get("email_match", 1.5),
                "intercept": match_weights.get("intercept", -0.5)
            }
        },
        
        # THRESHOLDS
        {
            "category": ConfigCategoryEnum.THRESHOLDS,
            "key": "auto_merge",
            "value": {
                "min_confidence": 0.90
            }
        },
        {
            "category": ConfigCategoryEnum.THRESHOLDS,
            "key": "manual_review",
            "value": {
                "min_confidence": 0.60,
                "max_confidence": 0.90
            }
        },
        
        # SOURCE_PRECEDENCE
        {
            "category": ConfigCategoryEnum.SOURCE_PRECEDENCE,
            "key": "conflict_resolution_order",
            "value": {
                "mobile": ["WEALTH", "LOANS", "INSURANCE", "MF", "EQUITY"],
                "email": ["EQUITY", "MF", "INSURANCE", "LOANS", "WEALTH"],
                "name": ["EQUITY", "MF", "INSURANCE", "LOANS", "WEALTH"],
                "address": ["WEALTH", "LOANS", "INSURANCE", "MF", "EQUITY"],
                "dob": ["EQUITY", "MF", "INSURANCE", "LOANS", "WEALTH"]
            }
        },
        
        # ELIGIBILITY_RULES
        {
            "category": ConfigCategoryEnum.ELIGIBILITY_RULES,
            "key": "insurance_cross_sell",
            "value": {
                "requires": ["EQUITY", "MF"],
                "excludes": ["INSURANCE"],
                "min_relationship_value": 500000
            }
        },
        {
            "category": ConfigCategoryEnum.ELIGIBILITY_RULES,
            "key": "wealth_advisory_cross_sell",
            "value": {
                "requires": ["LOANS"],
                "excludes": ["WEALTH"],
                "min_relationship_value": 2000000
            }
        },
        
        # SCORING_WEIGHTS
        {
            "category": ConfigCategoryEnum.SCORING_WEIGHTS,
            "key": "opportunity_score_v1",
            "value": {
                "w1": 0.5,  # potential_value_norm
                "w2": 0.3,  # relationship_strength_norm
                "w3": 0.2,  # recency_engagement_norm
                "min_score": 40
            }
        },
        
        # NORMALIZATION_RULES
        {
            "category": ConfigCategoryEnum.NORMALIZATION_RULES,
            "key": "mobile",
            "value": {
                "strip_country_code": True,
                "target_length": 10,
                "remove_spaces": True,
                "remove_dashes": True
            }
        },
        {
            "category": ConfigCategoryEnum.NORMALIZATION_RULES,
            "key": "email",
            "value": {
                "lowercase": True,
                "trim_whitespace": True
            }
        },
        {
            "category": ConfigCategoryEnum.NORMALIZATION_RULES,
            "key": "name",
            "value": {
                "title_case": True,
                "trim_whitespace": True,
                "remove_extra_spaces": True
            }
        },
    ]
    
    for entry_data in config_entries:
        # Check if entry already exists
        existing = db.query(ConfigEntry).filter(
            ConfigEntry.category == entry_data["category"],
            ConfigEntry.key == entry_data["key"]
        ).first()
        
        if not existing:
            entry = ConfigEntry(**entry_data)
            db.add(entry)
            print(f"Added: {entry_data['category'].value}/{entry_data['key']}")
        else:
            print(f"Skipped (already exists): {entry_data['category'].value}/{entry_data['key']}")
    
    db.commit()
    print("Configuration seeding complete!")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_config(db)
    finally:
        db.close()
