from __future__ import annotations

import hashlib

import pandas as pd


SIGNATURE_COLUMNS = ["axis_id", "axis_name", "code", "name", "unit", "parent_code"]


def make_schema_signature(meta_df: pd.DataFrame, ignore_axes: tuple[str, ...] = ("time",)) -> str:
    if meta_df.empty:
        return "empty"
    compare_df = meta_df.copy()
    compare_df = compare_df[~compare_df["axis_id"].isin(ignore_axes)]
    for column in SIGNATURE_COLUMNS:
        if column not in compare_df.columns:
            compare_df[column] = ""
    compare_df = compare_df[SIGNATURE_COLUMNS].fillna("").sort_values(SIGNATURE_COLUMNS)
    raw = compare_df.to_csv(index=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def axis_summary(meta_df: pd.DataFrame) -> str:
    if meta_df.empty:
        return "メタ情報なし"
    grouped = meta_df.groupby(["axis_id", "axis_name"], dropna=False).size().reset_index(name="count")
    return ", ".join(
        f"{row.axis_id}({row.axis_name}):{row.count}" for row in grouped.itertuples(index=False)
    )


def judge_join_type(meta_dfs: dict[str, pd.DataFrame]) -> tuple[str, pd.DataFrame]:
    detail_rows: list[dict[str, object]] = []
    axis_sets: list[set[str]] = []
    signatures: list[str] = []
    units: set[str] = set()

    for stats_data_id, meta_df in meta_dfs.items():
        signature = make_schema_signature(meta_df)
        signatures.append(signature)
        axis_set = set(meta_df["axis_id"].dropna().astype(str)) if not meta_df.empty else set()
        axis_sets.append(axis_set)
        if "unit" in meta_df.columns:
            units.update(
                str(unit)
                for unit in meta_df["unit"].dropna().unique()
                if str(unit).strip()
            )
        detail_rows.append(
            {
                "statsDataId": stats_data_id,
                "schema_signature": signature,
                "axis_summary": axis_summary(meta_df),
                "n_axes": len(axis_set),
                "n_classes": int(len(meta_df)),
            }
        )

    detail_df = pd.DataFrame(detail_rows)
    if not meta_dfs:
        return "Cannot Join", detail_df
    if len(set(signatures)) == 1:
        return "Safe Join", detail_df
    if units and len(units) > 1:
        return "Cannot Join", detail_df
    if axis_sets and all(axis_sets[0] == axis_set for axis_set in axis_sets[1:]):
        return "Warning Join", detail_df
    return "Cannot Join", detail_df
