"""Therapeutic category display configuration, copied from alz_kb/drugs.py."""

THERAPEUTIC_CATEGORIES = [
    # --- specific therapeutic classes: what the drug is actually FOR
    "Blood Glucose Lowering Agents", "Antihypertensive Agents",
    "Hypolipidemic Agents", "Anticholesteremic Agents", "Lipid Regulating Agents",
    "Antineoplastic Agents", "Immunosuppressive Agents",
    "Anti-Inflammatory Agents", "Antirheumatic Agents",
    "Antidepressive Agents", "Antipsychotic Agents", "Anti-Anxiety Agents",
    "Anticonvulsants", "Hypnotics and Sedatives", "Analgesics",
    "Anti-Bacterial Agents", "Antiviral Agents", "Antifungal Agents",
    "Anticoagulants", "Platelet Aggregation Inhibitors", "Diuretics",
    "Agents Acting on the Renin-Angiotensin System", "Vasodilator Agents",
    "Bronchodilator Agents", "Antiemetics", "Anti-Ulcer Agents",
    "Gastric Acid Lowering Agents", "Vaccines",
    # --- mid-level system classes
    "Cardiovascular Agents", "Central Nervous System Agents", "Hematologic Agents",
    "Dermatologic Agents", "Gastrointestinal Agents", "Respiratory System Agents",
    # --- broad ATC anatomical buckets: the fallback, least informative
    "Alimentary Tract and Metabolism", "Blood and Blood Forming Organs",
    "Cardiovascular System", "Dermatologicals", "Genito Urinary System and Sex Hormones",
    "Antiinfectives for Systemic Use", "Antineoplastic and Immunomodulating Agents",
    "Musculo-Skeletal System", "Nervous System", "Respiratory System", "Sensory Organs",
    "Systemic Hormonal Preparations, Excl. Sex Hormones and Insulins",
    "Antiparasitic Products, Insecticides and Repellents",
]
