from __future__ import annotations

import pandas as pd


def concat_safe(dfs: list[pd.DataFrame]) -> pd.DataFrame:
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)


def concat_aligned(dfs: list[pd.DataFrame]) -> pd.DataFrame:
    if not dfs:
        return pd.DataFrame()
    columns: list[str] = []
    for df in dfs:
        for column in df.columns:
            if column not in columns:
                columns.append(column)
    aligned = [df.reindex(columns=columns) for df in dfs]
    return pd.concat(aligned, ignore_index=True)


def concat_common_columns(dfs: list[pd.DataFrame]) -> pd.DataFrame:
    if not dfs:
        return pd.DataFrame()
    common = set(dfs[0].columns)
    for df in dfs[1:]:
        common &= set(df.columns)
    ordered = [column for column in dfs[0].columns if column in common]
    return pd.concat([df[ordered] for df in dfs], ignore_index=True)


def join_dataframes(dfs: list[pd.DataFrame], mode: str) -> pd.DataFrame:
    if mode == "共通列のみ残す":
        return concat_common_columns(dfs)
    if mode == "全列を残して欠損を許容する":
        return concat_aligned(dfs)
    # "そのまま縦結合（Safe）" およびその他
    return concat_safe(dfs)
