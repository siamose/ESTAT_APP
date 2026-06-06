from __future__ import annotations

from typing import Any

import pandas as pd

from .estat_client import ensure_list, get_nested


def text_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        if "$" in value:
            return str(value["$"])
        if "@name" in value:
            return str(value["@name"])
        return " / ".join(str(v) for v in value.values() if not isinstance(v, (dict, list)))
    return str(value)


def parse_catalog_df(payload: dict[str, Any]) -> pd.DataFrame:
    table_infos = ensure_list(
        get_nested(payload, "GET_STATS_LIST", "DATALIST_INF", "TABLE_INF", default=[])
    )
    rows: list[dict[str, Any]] = []
    for table in table_infos:
        if not isinstance(table, dict):
            continue
        rows.append(
            {
                "statsDataId": table.get("@id") or table.get("id"),
                "調査名": text_value(table.get("STAT_NAME")),
                "政府統計コード": text_value(table.get("GOV_ORG")),
                "表題": text_value(table.get("TITLE")),
                "調査年月": text_value(table.get("SURVEY_DATE")),
                "公開日": text_value(table.get("OPEN_DATE")),
                "総件数": text_value(table.get("OVERALL_TOTAL_NUMBER")),
            }
        )
    return pd.DataFrame(rows)
