from __future__ import annotations

import hashlib
import re
from typing import Any

from ..client import MetaClient

AUDIENCE_FIELDS = "id,name,subtype,approximate_count_lower_bound,approximate_count_upper_bound,delivery_status,operation_status,time_updated"


def list_custom(client: MetaClient, account_id: str, limit: int = 100) -> list[dict[str, Any]]:
    return client.get_all(f"{account_id}/customaudiences", limit=limit, fields=AUDIENCE_FIELDS)


def list_saved(client: MetaClient, account_id: str, limit: int = 100) -> list[dict[str, Any]]:
    return client.get_all(f"{account_id}/saved_audiences", limit=limit,
                          fields="id,name,approximate_count_lower_bound,approximate_count_upper_bound,targeting")


def create_custom(client: MetaClient, account_id: str, name: str, description: str = "") -> dict[str, Any]:
    return client.post(f"{account_id}/customaudiences", name=name, subtype="CUSTOM",
                       description=description, customer_file_source="USER_PROVIDED_ONLY")


def create_lookalike(client: MetaClient, account_id: str, name: str, origin_audience_id: str,
                     country: str, ratio: float = 0.01) -> dict[str, Any]:
    return client.post(f"{account_id}/customaudiences", name=name, subtype="LOOKALIKE",
                       origin_audience_id=origin_audience_id,
                       lookalike_spec={"type": "custom_ratio", "ratio": ratio, "country": country.upper()})


# -- customer list hashing (done locally; raw PII never leaves the machine) --

def _norm_email(v: str) -> str:
    return v.strip().lower()


def _norm_phone(v: str) -> str:
    return re.sub(r"\D", "", v)


def _norm_name(v: str) -> str:
    return re.sub(r"[^a-z]", "", v.strip().lower())


NORMALIZERS = {"EMAIL": _norm_email, "PHONE": _norm_phone, "FN": _norm_name, "LN": _norm_name,
               "CT": _norm_name, "ST": lambda v: v.strip().lower()[:2], "ZIP": lambda v: v.strip().lower(),
               "COUNTRY": lambda v: v.strip().lower()}


def _sha(v: str) -> str:
    return hashlib.sha256(v.encode("utf-8")).hexdigest()


def hash_rows(rows: list[dict[str, str]], schema: list[str]) -> list[list[str]]:
    out = []
    for row in rows:
        hashed = []
        for key in schema:
            raw = (row.get(key) or row.get(key.lower()) or "").strip()
            if not raw:
                hashed.append("")
                continue
            hashed.append(_sha(NORMALIZERS.get(key, lambda x: x.strip().lower())(raw)))
        if any(hashed):
            out.append(hashed)
    return out


def add_users(client: MetaClient, audience_id: str, rows: list[dict[str, str]],
              schema: list[str], batch_size: int = 5000) -> dict[str, Any]:
    schema = [s.upper() for s in schema]
    data = hash_rows(rows, schema)
    total = {"received": 0, "batches": 0}
    for i in range(0, len(data), batch_size):
        chunk = data[i:i + batch_size]
        resp = client.post(f"{audience_id}/users", payload={"schema": schema, "data": chunk})
        total["received"] += resp.get("num_received", len(chunk))
        total["batches"] += 1
    return total
