#!/usr/bin/env python3
"""Generate practice data for the pharmacy prior-authorization system (seed 42)."""

import json
import os

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    patients_dir = os.path.join(data_dir, "patients")

    os.makedirs(patients_dir, exist_ok=True)

    # --- Formulary (10 drugs) ---
    formulary = [
        {
            "drug_id": "DRUG001",
            "drug_name": "Metformin XR",
            "step_therapy_required": False,
            "step_therapy_prior_drugs": [],
            "quantity_limit_30d": 60,
            "exception_diagnoses": []
        },
        {
            "drug_id": "DRUG002",
            "drug_name": "Glipizide",
            "step_therapy_required": False,
            "step_therapy_prior_drugs": [],
            "quantity_limit_30d": 30,
            "exception_diagnoses": []
        },
        {
            "drug_id": "DRUG003",
            "drug_name": "Insulin Glargine",
            "step_therapy_required": True,
            "step_therapy_prior_drugs": ["DRUG001", "DRUG002"],
            "quantity_limit_30d": 30,
            "exception_diagnoses": ["E11.9"]
        },
        {
            "drug_id": "DRUG004",
            "drug_name": "Lisinopril",
            "step_therapy_required": False,
            "step_therapy_prior_drugs": [],
            "quantity_limit_30d": 30,
            "exception_diagnoses": []
        },
        {
            "drug_id": "DRUG005",
            "drug_name": "Amlodipine",
            "step_therapy_required": True,
            "step_therapy_prior_drugs": ["DRUG004"],
            "quantity_limit_30d": 60,
            "exception_diagnoses": []
        },
        {
            "drug_id": "DRUG006",
            "drug_name": "Atorvastatin",
            "step_therapy_required": False,
            "step_therapy_prior_drugs": [],
            "quantity_limit_30d": 30,
            "exception_diagnoses": ["E78.5"]
        },
        {
            "drug_id": "DRUG007",
            "drug_name": "Rosuvastatin",
            "step_therapy_required": True,
            "step_therapy_prior_drugs": ["DRUG006"],
            "quantity_limit_30d": 45,
            "exception_diagnoses": ["E78.0"]
        },
        {
            "drug_id": "DRUG008",
            "drug_name": "Omeprazole",
            "step_therapy_required": False,
            "step_therapy_prior_drugs": [],
            "quantity_limit_30d": 60,
            "exception_diagnoses": ["K21.0"]
        },
        {
            "drug_id": "DRUG009",
            "drug_name": "Esomeprazole",
            "step_therapy_required": True,
            "step_therapy_prior_drugs": ["DRUG008"],
            "quantity_limit_30d": 30,
            "exception_diagnoses": ["K21.0", "G43.9"]
        },
        {
            "drug_id": "DRUG010",
            "drug_name": "Sumatriptan",
            "step_therapy_required": False,
            "step_therapy_prior_drugs": [],
            "quantity_limit_30d": 12,
            "exception_diagnoses": ["G43.9"]
        }
    ]

    # --- Prescriber data (20 patients) ---
    prescriber = [
        {"patient_id": "PAT001", "medications": []},
        {"patient_id": "PAT002", "medications": [{"drug_id": "DRUG006", "outcome": "active"}]},
        {"patient_id": "PAT003", "medications": []},
        {"patient_id": "PAT004", "medications": [{"drug_id": "DRUG002", "outcome": "active"}]},
        {"patient_id": "PAT005", "medications": [{"drug_id": "DRUG004", "outcome": "active"}]},
        {"patient_id": "PAT006", "medications": [{"drug_id": "DRUG001", "outcome": "active"}]},
        {"patient_id": "PAT007", "medications": [
            {"drug_id": "DRUG001", "outcome": "failed"},
            {"drug_id": "DRUG004", "outcome": "active"}
        ]},
        {"patient_id": "PAT008", "medications": [
            {"drug_id": "DRUG008", "outcome": "failed"}
        ]},
        {"patient_id": "PAT009", "medications": [
            {"drug_id": "DRUG006", "outcome": "failed"},
            {"drug_id": "DRUG002", "outcome": "active"}
        ]},
        {"patient_id": "PAT010", "medications": [
            {"drug_id": "DRUG001", "outcome": "active"}
        ]},
        {"patient_id": "PAT011", "medications": [
            {"drug_id": "DRUG004", "outcome": "active"}
        ]},
        {"patient_id": "PAT012", "medications": []},
        {"patient_id": "PAT013", "medications": [
            {"drug_id": "DRUG004", "outcome": "active"}
        ]},
        {"patient_id": "PAT014", "medications": [
            {"drug_id": "DRUG008", "outcome": "active"}
        ]},
        {"patient_id": "PAT015", "medications": [
            {"drug_id": "DRUG004", "outcome": "active"}
        ]},
        {"patient_id": "PAT016", "medications": [
            {"drug_id": "DRUG008", "outcome": "failed"},
            {"drug_id": "DRUG004", "outcome": "active"}
        ]},
        {"patient_id": "PAT017", "medications": [
            {"drug_id": "DRUG006", "outcome": "active"}
        ]},
        {"patient_id": "PAT018", "medications": [
            {"drug_id": "DRUG001", "outcome": "active"}
        ]},
        {"patient_id": "PAT019", "medications": [
            {"drug_id": "DRUG006", "outcome": "active"}
        ]},
        {"patient_id": "PAT020", "medications": [
            {"drug_id": "DRUG008", "outcome": "failed"},
            {"drug_id": "DRUG001", "outcome": "active"}
        ]}
    ]

    # --- Payer data (20 patients) ---
    payer = [
        {"patient_id": "PAT001", "plan_tier": "tier1"},
        {"patient_id": "PAT002", "plan_tier": "tier2"},
        {"patient_id": "PAT003", "plan_tier": "tier3"},
        {"patient_id": "PAT004", "plan_tier": "tier1"},
        {"patient_id": "PAT005", "plan_tier": "tier2"},
        {"patient_id": "PAT006", "plan_tier": "tier3"},
        {"patient_id": "PAT007", "plan_tier": "tier1"},
        {"patient_id": "PAT008", "plan_tier": "tier2"},
        {"patient_id": "PAT009", "plan_tier": "tier3"},
        {"patient_id": "PAT010", "plan_tier": "tier1"},
        {"patient_id": "PAT011", "plan_tier": "tier2"},
        {"patient_id": "PAT012", "plan_tier": "tier3"},
        {"patient_id": "PAT013", "plan_tier": "tier1"},
        {"patient_id": "PAT014", "plan_tier": "tier2"},
        {"patient_id": "PAT015", "plan_tier": "tier3"},
        {"patient_id": "PAT016", "plan_tier": "tier1"},
        {"patient_id": "PAT017", "plan_tier": "tier2"},
        {"patient_id": "PAT018", "plan_tier": "tier3"},
        {"patient_id": "PAT019", "plan_tier": "tier1"},
        {"patient_id": "PAT020", "plan_tier": "tier2"}
    ]

    # --- Patient demographics (20 patients) ---
    patients = [
        {"patient_id": "PAT001", "first_name": "Alice", "last_name": "Anderson", "date_of_birth": "1955-03-14", "gender": "F"},
        {"patient_id": "PAT002", "first_name": "Bob", "last_name": "Baker", "date_of_birth": "1962-07-22", "gender": "M"},
        {"patient_id": "PAT003", "first_name": "Carol", "last_name": "Chen", "date_of_birth": "1948-11-03", "gender": "F"},
        {"patient_id": "PAT004", "first_name": "David", "last_name": "Davis", "date_of_birth": "1970-05-18", "gender": "M"},
        {"patient_id": "PAT005", "first_name": "Emily", "last_name": "Evans", "date_of_birth": "1983-09-27", "gender": "F"},
        {"patient_id": "PAT006", "first_name": "Frank", "last_name": "Fischer", "date_of_birth": "1958-01-12", "gender": "M"},
        {"patient_id": "PAT007", "first_name": "Grace", "last_name": "Garcia", "date_of_birth": "1990-04-05", "gender": "F"},
        {"patient_id": "PAT008", "first_name": "Henry", "last_name": "Harris", "date_of_birth": "1975-08-30", "gender": "M"},
        {"patient_id": "PAT009", "first_name": "Irene", "last_name": "Irving", "date_of_birth": "1967-12-21", "gender": "F"},
        {"patient_id": "PAT010", "first_name": "James", "last_name": "Johnson", "date_of_birth": "1988-06-08", "gender": "M"},
        {"patient_id": "PAT011", "first_name": "Karen", "last_name": "Kim", "date_of_birth": "1953-02-14", "gender": "F"},
        {"patient_id": "PAT012", "first_name": "Leo", "last_name": "Lee", "date_of_birth": "1979-10-25", "gender": "M"},
        {"patient_id": "PAT013", "first_name": "Maria", "last_name": "Martinez", "date_of_birth": "1992-03-31", "gender": "F"},
        {"patient_id": "PAT014", "first_name": "Nathan", "last_name": "Nguyen", "date_of_birth": "1964-07-17", "gender": "M"},
        {"patient_id": "PAT015", "first_name": "Olivia", "last_name": "Olson", "date_of_birth": "1981-11-09", "gender": "F"},
        {"patient_id": "PAT016", "first_name": "Paul", "last_name": "Patel", "date_of_birth": "1956-05-23", "gender": "M"},
        {"patient_id": "PAT017", "first_name": "Quinn", "last_name": "Quigley", "date_of_birth": "1973-09-06", "gender": "M"},
        {"patient_id": "PAT018", "first_name": "Rachel", "last_name": "Roberts", "date_of_birth": "1986-01-28", "gender": "F"},
        {"patient_id": "PAT019", "first_name": "Samuel", "last_name": "Smith", "date_of_birth": "1949-04-11", "gender": "M"},
        {"patient_id": "PAT020", "first_name": "Teresa", "last_name": "Torres", "date_of_birth": "1971-08-19", "gender": "F"}
    ]

    # --- Queue cases (20 cases, covering all quirk-matrix levels) ---
    queue = [
        # CASE001: ST met via queue, Q within, no conflict
        {
            "case_id": "CASE001",
            "drug_id": "DRUG003",
            "patient_id": "PAT001",
            "requested_quantity": 25,
            "diagnosis_code": "E10.9",
            "prior_drugs": [{"drug_id": "DRUG001", "outcome": "failed"}],
            "notes": ""
        },
        # CASE002: ST not required, Q within, no conflict
        {
            "case_id": "CASE002",
            "drug_id": "DRUG001",
            "patient_id": "PAT002",
            "requested_quantity": 45,
            "diagnosis_code": "E11.0",
            "prior_drugs": [],
            "notes": ""
        },
        # CASE003: ST met via queue, Q within, no conflict
        {
            "case_id": "CASE003",
            "drug_id": "DRUG005",
            "patient_id": "PAT003",
            "requested_quantity": 45,
            "diagnosis_code": "I10.0",
            "prior_drugs": [{"drug_id": "DRUG004", "outcome": "failed"}],
            "notes": ""
        },
        # CASE004: ST not required, Q at limit, no conflict
        {
            "case_id": "CASE004",
            "drug_id": "DRUG002",
            "patient_id": "PAT004",
            "requested_quantity": 30,
            "diagnosis_code": "E11.9",
            "prior_drugs": [],
            "notes": ""
        },
        # CASE005: ST not required, Q at limit, no conflict
        {
            "case_id": "CASE005",
            "drug_id": "DRUG004",
            "patient_id": "PAT005",
            "requested_quantity": 30,
            "diagnosis_code": "I10.0",
            "prior_drugs": [],
            "notes": ""
        },
        # CASE006: ST not required, Q at limit, no conflict
        {
            "case_id": "CASE006",
            "drug_id": "DRUG008",
            "patient_id": "PAT006",
            "requested_quantity": 60,
            "diagnosis_code": "K21.0",
            "prior_drugs": [],
            "notes": ""
        },
        # CASE007: ST met via prescriber, Q within, no conflict
        {
            "case_id": "CASE007",
            "drug_id": "DRUG003",
            "patient_id": "PAT007",
            "requested_quantity": 25,
            "diagnosis_code": "E10.9",
            "prior_drugs": [],
            "notes": ""
        },
        # CASE008: ST met via prescriber, Q within, stale note
        {
            "case_id": "CASE008",
            "drug_id": "DRUG009",
            "patient_id": "PAT008",
            "requested_quantity": 25,
            "diagnosis_code": "R12",
            "prior_drugs": [],
            "notes": "Previously tried DRUG008 without success"
        },
        # CASE009: ST met via prescriber, Q within, note contradicts formulary
        {
            "case_id": "CASE009",
            "drug_id": "DRUG007",
            "patient_id": "PAT009",
            "requested_quantity": 30,
            "diagnosis_code": "E78.0",
            "prior_drugs": [],
            "notes": "Step therapy not required per specialist - patient cannot tolerate prior alternatives"
        },
        # CASE010: ST met via queue, Q within, stale note
        {
            "case_id": "CASE010",
            "drug_id": "DRUG003",
            "patient_id": "PAT010",
            "requested_quantity": 20,
            "diagnosis_code": "E10.9",
            "prior_drugs": [{"drug_id": "DRUG002", "outcome": "failed"}],
            "notes": "Patient previously tried DRUG005 without improvement"
        },
        # CASE011: ST not required, Q within, note contradicts formulary
        {
            "case_id": "CASE011",
            "drug_id": "DRUG002",
            "patient_id": "PAT011",
            "requested_quantity": 20,
            "diagnosis_code": "E11.9",
            "prior_drugs": [],
            "notes": "Step therapy requirement met - previously on DRUG001"
        },
        # CASE012: ST not required, Q over, no exception
        {
            "case_id": "CASE012",
            "drug_id": "DRUG004",
            "patient_id": "PAT012",
            "requested_quantity": 45,
            "diagnosis_code": "I10.0",
            "prior_drugs": [],
            "notes": ""
        },
        # CASE013: ST not met, Q within, no conflict
        {
            "case_id": "CASE013",
            "drug_id": "DRUG003",
            "patient_id": "PAT013",
            "requested_quantity": 25,
            "diagnosis_code": "E10.9",
            "prior_drugs": [],
            "notes": ""
        },
        # CASE014: ST not required, Q over, note contradicts formulary (note claims exception)
        {
            "case_id": "CASE014",
            "drug_id": "DRUG001",
            "patient_id": "PAT014",
            "requested_quantity": 80,
            "diagnosis_code": "E11.0",
            "prior_drugs": [],
            "notes": "Quantity exception approved by payer representative on 2024-01-15"
        },
        # CASE015: ST not required, Q over with exception, no conflict
        {
            "case_id": "CASE015",
            "drug_id": "DRUG006",
            "patient_id": "PAT015",
            "requested_quantity": 45,
            "diagnosis_code": "E78.5",
            "prior_drugs": [],
            "notes": ""
        },
        # CASE016: ST met via prescriber, Q over with exception, no conflict (reason-code precedence test)
        {
            "case_id": "CASE016",
            "drug_id": "DRUG009",
            "patient_id": "PAT016",
            "requested_quantity": 40,
            "diagnosis_code": "K21.0",
            "prior_drugs": [],
            "notes": ""
        },
        # CASE017: ST not met, Q over, no conflict (procedure order: ST checked first)
        {
            "case_id": "CASE017",
            "drug_id": "DRUG005",
            "patient_id": "PAT017",
            "requested_quantity": 70,
            "diagnosis_code": "I10.0",
            "prior_drugs": [],
            "notes": ""
        },
        # CASE018: ST met via queue, Q over with exception, no conflict
        {
            "case_id": "CASE018",
            "drug_id": "DRUG007",
            "patient_id": "PAT018",
            "requested_quantity": 50,
            "diagnosis_code": "E78.0",
            "prior_drugs": [{"drug_id": "DRUG006", "outcome": "failed"}],
            "notes": ""
        },
        # CASE019: ST not met, Q within, note contradicts formulary
        {
            "case_id": "CASE019",
            "drug_id": "DRUG005",
            "patient_id": "PAT019",
            "requested_quantity": 40,
            "diagnosis_code": "I10.0",
            "prior_drugs": [],
            "notes": "No step therapy required - patient has tried alternatives"
        },
        # CASE020: ST met via prescriber, Q over with exception, stale note
        {
            "case_id": "CASE020",
            "drug_id": "DRUG009",
            "patient_id": "PAT020",
            "requested_quantity": 35,
            "diagnosis_code": "G43.9",
            "prior_drugs": [],
            "notes": "Patient has not tried prior alternatives"
        }
    ]

    # Write formulary
    with open(os.path.join(data_dir, "formulary.json"), "w") as f:
        json.dump(formulary, f, indent=2)

    # Write prescriber
    with open(os.path.join(data_dir, "prescriber.json"), "w") as f:
        json.dump(prescriber, f, indent=2)

    # Write payer
    with open(os.path.join(data_dir, "payer.json"), "w") as f:
        json.dump(payer, f, indent=2)

    # Write empty submissions file
    with open(os.path.join(data_dir, "submissions.jsonl"), "w") as f:
        pass

    # Write patient demographic files
    for patient in patients:
        filepath = os.path.join(patients_dir, f"{patient['patient_id']}.json")
        with open(filepath, "w") as f:
            json.dump(patient, f, indent=2)

    # Write queue
    with open(os.path.join(base_dir, "queue.json"), "w") as f:
        json.dump(queue, f, indent=2)

    print(f"Generated {len(formulary)} drugs, {len(patients)} patients, {len(queue)} queue cases")


if __name__ == "__main__":
    main()
