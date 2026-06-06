from __future__ import annotations

import pandas as pd


def numeric_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "value" not in df.columns:
        return pd.DataFrame()
    return df[["value"]].describe().T


def missing_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    missing = df.isna().sum().reset_index()
    missing.columns = ["column", "missing_count"]
    missing["missing_rate"] = missing["missing_count"] / len(df)
    return missing.sort_values("missing_count", ascending=False)


def aggregate_for_chart(df: pd.DataFrame, x: str, y: str, color: str | None, agg: str) -> pd.DataFrame:
    if df.empty or x not in df.columns or y not in df.columns:
        return pd.DataFrame()
    group_columns = [x]
    if color and color in df.columns and color != x:
        group_columns.append(color)
    if agg == "mean":
        result = df.groupby(group_columns, dropna=False)[y].mean().reset_index()
    elif agg == "median":
        result = df.groupby(group_columns, dropna=False)[y].median().reset_index()
    else:
        result = df.groupby(group_columns, dropna=False)[y].sum().reset_index()
    return result.sort_values(group_columns)
