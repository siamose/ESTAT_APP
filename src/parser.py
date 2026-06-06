from __future__ import annotations

from typing import Any

import pandas as pd

from .estat_client import ensure_list, get_nested
from .catalog import text_value


def parse_stats_data(payload: dict[str, Any], stats_data_id: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    statistical_data = get_nested(payload, "GET_STATS_DATA", "STATISTICAL_DATA", default={})
    table_info = statistical_data.get("TABLE_INF", {}) if isinstance(statistical_data, dict) else {}
    resolved_stats_id = (
        stats_data_id
        or table_info.get("@id")
        or table_info.get("id")
        or get_nested(payload, "GET_STATS_DATA", "PARAMETER", "STATS_DATA_ID")
    )
    values_df = parse_values_df(payload, resolved_stats_id)
    meta_df = parse_meta_df(payload, resolved_stats_id)
    table_meta = {
        "statsDataId": resolved_stats_id,
        "survey_date": text_value(table_info.get("SURVEY_DATE")),
        "table_title": text_value(table_info.get("TITLE")),
    }
    return values_df, meta_df, table_meta


def parse_values_df(payload: dict[str, Any], stats_data_id: str | None = None) -> pd.DataFrame:
    values = ensure_list(
        get_nested(
            payload,
            "GET_STATS_DATA",
            "STATISTICAL_DATA",
            "DATA_INF",
            "VALUE",
            default=[],
        )
    )
    rows: list[dict[str, Any]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        row = {"statsDataId": stats_data_id}
        for key, value in item.items():
            if key == "$":
                row["value"] = value
            else:
                row[key] = value
        rows.append(row)

    df = pd.DataFrame(rows)
    if "value" in df.columns:
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


def parse_meta_df(payload: dict[str, Any], stats_data_id: str | None = None) -> pd.DataFrame:
    class_objs = ensure_list(
        get_nested(
            payload,
            "GET_STATS_DATA",
            "STATISTICAL_DATA",
            "CLASS_INF",
            "CLASS_OBJ",
            default=[],
        )
    )
    rows: list[dict[str, Any]] = []
    for class_obj in class_objs:
        if not isinstance(class_obj, dict):
            continue
        axis_id = str(class_obj.get("@id") or class_obj.get("id") or "")
        axis_name = class_obj.get("@name") or class_obj.get("name") or axis_id
        classes = ensure_list(class_obj.get("CLASS"))
        for klass in classes:
            if not isinstance(klass, dict):
                continue
            rows.append(
                {
                    "statsDataId": stats_data_id,
                    "axis_id": axis_id,
                    "axis_name": axis_name,
                    "code": klass.get("@code") or klass.get("code"),
                    "name": klass.get("@name") or klass.get("name"),
                    "level": klass.get("@level") or klass.get("level"),
                    "unit": klass.get("@unit") or klass.get("unit"),
                    "parent_code": klass.get("@parentCode")
                    or klass.get("@parent_code")
                    or klass.get("parent_code"),
                }
            )
    return pd.DataFrame(rows)


def add_label_columns(values_df: pd.DataFrame, meta_df: pd.DataFrame) -> pd.DataFrame:
    analysis_df = values_df.copy()
    if values_df.empty or meta_df.empty:
        return analysis_df

    for axis_id in sorted(meta_df["axis_id"].dropna().unique()):
        code_column = f"@{axis_id}"
        label_column = f"{axis_id}_label"
        if code_column not in analysis_df.columns:
            continue
        axis_meta = meta_df[meta_df["axis_id"] == axis_id]
        mapping = dict(zip(axis_meta["code"].astype(str), axis_meta["name"]))
        analysis_df[label_column] = analysis_df[code_column].astype(str).map(mapping)

    if "@unit" in analysis_df.columns and "unit" not in analysis_df.columns:
        analysis_df["unit"] = analysis_df["@unit"]
    return analysis_df


def build_analysis_df(values_df: pd.DataFrame, meta_df: pd.DataFrame, table_meta: dict[str, Any]) -> pd.DataFrame:
    analysis_df = add_label_columns(values_df, meta_df)
    for key in ["survey_date", "table_title"]:
        if key not in analysis_df.columns:
            analysis_df[key] = table_meta.get(key)
    preferred = [
        "statsDataId",
        "survey_date",
        "table_title",
        "time_label",
        "area_label",
        "cat01_label",
        "cat02_label",
        "cat03_label",
        "value",
        "unit",
    ]
    existing = [column for column in preferred if column in analysis_df.columns]
    remaining = [column for column in analysis_df.columns if column not in existing]
    return analysis_df[existing + remaining]
