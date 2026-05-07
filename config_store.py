import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Tuple

from enums import QUESTIONS as DEFAULT_QUESTIONS


BASE_DIR = Path(__file__).resolve().parent
RULES_PATH = BASE_DIR / "rules.json"
QUESTIONS_PATH = BASE_DIR / "questions.json"
CF_CONFIG_PATH = BASE_DIR / "cf_config.json"

INPUT_VARIABLES = [
    "genangan_air_terbuka",
    "durasi_genangan_air",
    "keberadaan_jentik",
    "nyamuk_aedes",
    "frekuensi_hujan",
    "intensitas_hujan",
    "mobilitas_penduduk",
    "kepadatan_penduduk",
    "kondisi_lingkungan_sekitar",
]

DERIVED_VALUES = {
    "potensi_perkembangbiakan": ["rendah", "sedang", "tinggi"],
    "iklim": ["mendukung", "kurang_mendukung", "tidak_mendukung"],
    "faktor_eksposur_manusia": ["rentan", "aman"],
    "tingkat_resiko_dbd": ["rendah", "sedang", "tinggi"],
}

ALL_VARIABLES = INPUT_VARIABLES + list(DERIVED_VALUES.keys())

DEFAULT_CF_CONFIG = {
    "threshold": 0.5,
    "rule_cf": {str(i): 1.0 for i in range(1, 50)},
    "user_cf": {
        key: {value: 1.0 for value in question["options"].keys()}
        for key, question in DEFAULT_QUESTIONS.items()
    },
}


def read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return deepcopy(fallback)
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def load_rules_data() -> Dict[str, Any]:
    return read_json(RULES_PATH, {"rules": []})


def save_rules_data(rules_data: Dict[str, Any]) -> None:
    write_json(RULES_PATH, rules_data)


def load_questions() -> Dict[str, Any]:
    return read_json(QUESTIONS_PATH, DEFAULT_QUESTIONS)


def save_questions(questions: Dict[str, Any]) -> None:
    write_json(QUESTIONS_PATH, questions)


def load_cf_config() -> Dict[str, Any]:
    config = read_json(CF_CONFIG_PATH, DEFAULT_CF_CONFIG)
    config.setdefault("threshold", 0.5)
    config.setdefault("rule_cf", {})
    config.setdefault("user_cf", {})
    return config


def save_cf_config(config: Dict[str, Any]) -> None:
    write_json(CF_CONFIG_PATH, config)


def normalize_cf(value: Any) -> float:
    try:
        cf = float(value)
    except (TypeError, ValueError):
        raise ValueError("Nilai CF harus berupa angka.")
    if cf > 1:
        cf = cf / 100
    if cf < 0 or cf > 1:
        raise ValueError("Nilai CF harus berada di rentang 0 sampai 1 atau 0 sampai 100 persen.")
    return round(cf, 4)


def allowed_values_for_attr(attr: str, questions: Dict[str, Any]) -> List[str]:
    if attr in questions:
        return list(questions[attr].get("options", {}).keys())
    return DERIVED_VALUES.get(attr, [])


def validate_questions(questions: Dict[str, Any], rules_data: Dict[str, Any]) -> List[str]:
    errors = []
    for key in INPUT_VARIABLES:
        if key not in questions:
            errors.append(f"Pertanyaan untuk fakta {key} wajib ada.")
            continue
        question = questions[key]
        if not str(question.get("text", "")).strip():
            errors.append(f"Teks pertanyaan {key} tidak boleh kosong.")
        options = question.get("options", {})
        explanations = question.get("explanation", {})
        if not isinstance(options, dict) or not options:
            errors.append(f"Opsi jawaban {key} wajib ada minimal satu.")
            continue
        for value, label in options.items():
            if not str(value).strip():
                errors.append(f"Value opsi pada {key} tidak boleh kosong.")
            if not str(label).strip():
                errors.append(f"Label opsi {key}:{value} tidak boleh kosong.")
            if value not in explanations or not str(explanations.get(value, "")).strip():
                errors.append(f"Deskripsi opsi {key}:{value} wajib diisi.")

    for rule in rules_data.get("rules", []):
        for antecedent in rule.get("antecedents", []):
            attr = antecedent.get("attr")
            value = antecedent.get("value")
            if attr in questions and value not in questions[attr].get("options", {}):
                errors.append(f"Rule {rule.get('id')} memakai opsi {attr}={value} yang tidak ada.")
    return errors


def validate_rule(rule: Dict[str, Any], questions: Dict[str, Any], existing_ids: List[int]) -> Tuple[Dict[str, Any], float]:
    errors = []
    try:
        rule_id = int(rule.get("id"))
    except (TypeError, ValueError):
        errors.append("ID rule harus berupa angka.")
        rule_id = None

    if rule_id is not None and rule_id < 1:
        errors.append("ID rule harus lebih dari 0.")

    try:
        rule_set = int(rule.get("set", 0))
    except (TypeError, ValueError):
        errors.append("Set rule harus berupa angka.")
        rule_set = 0

    antecedents = rule.get("antecedents")
    if not isinstance(antecedents, list) or not antecedents:
        errors.append("Antecedents wajib berupa list dan tidak boleh kosong.")
        antecedents = []

    for idx, antecedent in enumerate(antecedents, start=1):
        attr = antecedent.get("attr")
        value = antecedent.get("value")
        operator = antecedent.get("operator")
        if attr not in ALL_VARIABLES:
            errors.append(f"Antecedent {idx}: attr {attr} tidak dikenal.")
        elif value not in allowed_values_for_attr(attr, questions):
            errors.append(f"Antecedent {idx}: value {attr}={value} tidak valid.")
        if operator not in (None, "", "or"):
            errors.append(f"Antecedent {idx}: operator hanya boleh kosong atau or.")

    consequent = rule.get("consequent")
    if not isinstance(consequent, dict) or not consequent:
        errors.append("Consequent wajib berupa object dan tidak boleh kosong.")
        consequent = {}

    for attr, value in consequent.items():
        if attr not in DERIVED_VALUES:
            errors.append(f"Consequent attr {attr} tidak valid.")
        elif value not in DERIVED_VALUES[attr]:
            errors.append(f"Consequent value {attr}={value} tidak valid.")

    try:
        cf = normalize_cf(rule.get("cf", 1.0))
    except ValueError as exc:
        errors.append(str(exc))
        cf = 1.0

    if errors:
        raise ValueError("; ".join(errors))

    cleaned = {
        "id": rule_id,
        "set": rule_set,
        "antecedents": [
            {
                key: value
                for key, value in antecedent.items()
                if key in {"attr", "value", "operator"} and value not in (None, "")
            }
            for antecedent in antecedents
        ],
        "consequent": consequent,
        "description": str(rule.get("description", "")).strip(),
    }
    return cleaned, cf
