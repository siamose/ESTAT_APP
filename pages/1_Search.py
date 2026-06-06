from __future__ import annotations

import difflib

import pandas as pd
import streamlit as st

from src.catalog import parse_catalog_df
from src.config import require_api_key
from src.estat_client import EstatApiError, EstatClient


st.set_page_config(page_title="Search | e-Stat MVP", layout="wide")
st.title("統計表検索")

try:
    api_key = require_api_key()
except EnvironmentError as e:
    st.error(str(e))
    st.stop()

client = EstatClient(api_key)

STATS_CODE_PRESETS: list[tuple[str, str]] = [
    ("", "指定なし（全省庁）"),
    ("00200", "総務省・統計局（全般）"),
    ("00200521", "国勢調査"),
    ("00200531", "労働力調査"),
    ("00200532", "家計調査"),
    ("00200533", "消費者物価指数（CPI）"),
    ("00200561", "経済センサス"),
    ("00400", "厚生労働省（全般）"),
    ("00400001", "人口動態調査"),
    ("00400002", "国民健康・栄養調査"),
    ("00550", "経済産業省（全般）"),
    ("00600", "農林水産省（全般）"),
    ("__manual__", "── 手入力 ──"),
]
PRESET_LABELS = [label for _, label in STATS_CODE_PRESETS]
PRESET_MAP = {label: code for code, label in STATS_CODE_PRESETS}


def title_similarity(title: str, references: list[str]) -> float:
    """選択済みタイトル群との最大類似度を返す。"""
    if not references or not title:
        return 0.0
    return max(
        difflib.SequenceMatcher(None, title, ref).ratio() for ref in references
    )


def sort_by_selection_and_similarity(df: pd.DataFrame) -> pd.DataFrame:
    """選択済み行を先頭に、残りは選択済みタイトルとの類似度順に並べる。"""
    selected_titles = df.loc[df["選択"], "表題"].dropna().tolist()
    unselected = df[~df["選択"]].copy()
    if selected_titles:
        unselected["_sim"] = unselected["表題"].fillna("").apply(
            lambda t: title_similarity(t, selected_titles)
        )
        unselected = unselected.sort_values("_sim", ascending=False).drop(columns=["_sim"])
    return pd.concat([df[df["選択"]], unselected], ignore_index=True)


# ---------- 検索フォーム ----------
with st.form("search_form"):
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        search_word = st.text_input("キーワード", placeholder="人口、雇用、家計 など")
    with col2:
        stats_code_label = st.selectbox("政府統計コード", PRESET_LABELS)
    with col3:
        limit = st.number_input("取得件数", min_value=10, max_value=500, value=100, step=10)

    stats_code_manual = ""
    if stats_code_label == "── 手入力 ──":
        stats_code_manual = st.text_input(
            "コードを直接入力",
            placeholder="例: 00200521（8桁）または 00200（5桁）",
        )

    date_mode = st.radio("調査年月", ["全期間", "期間指定"], horizontal=True)
    survey_date_input = ""
    if date_mode == "期間指定":
        survey_date_input = st.text_input(
            "期間を入力",
            placeholder="例: 202401（単月）/ 2024（年）/ 202301-202412（範囲）",
        )

    submitted = st.form_submit_button("検索")

if stats_code_label == "── 手入力 ──":
    stats_code_value: str | None = stats_code_manual.strip() or None
else:
    raw = PRESET_MAP.get(stats_code_label, "")
    stats_code_value = raw or None

survey_date_value: str | None = (
    survey_date_input.strip() or None if date_mode == "期間指定" else None
)

if submitted:
    try:
        payload = client.search_stats_list(
            search_word=search_word or None,
            stats_code=stats_code_value,
            survey_date=survey_date_value,
            limit=int(limit),
        )
        catalog_df = parse_catalog_df(payload)
        catalog_df.insert(0, "選択", False)
        st.session_state["catalog_df"] = catalog_df
        st.session_state["selected_stats_ids"] = []
        st.session_state["prev_bulk_titles"] = []
    except EstatApiError as exc:
        st.error(f"API エラー: {exc}")
    except Exception as exc:
        st.error(f"検索に失敗しました: {exc}")

# ---------- 結果表示 ----------
catalog_df: pd.DataFrame | None = st.session_state.get("catalog_df")
if catalog_df is not None and not catalog_df.empty:
    st.subheader("検索結果")

    unique_titles = catalog_df["表題"].dropna().unique().tolist()
    bulk_titles: list[str] = st.multiselect(
        "表題で一括選択（選んだ表題の行をまとめてチェック）",
        options=unique_titles,
    )

    # multiselect の差分を検出してチェック状態を同期
    prev_bulk: list[str] = st.session_state.get("prev_bulk_titles", [])
    added = set(bulk_titles) - set(prev_bulk)
    removed = set(prev_bulk) - set(bulk_titles)

    if added or removed:
        df = catalog_df.copy()
        if added:
            df.loc[df["表題"].isin(added), "選択"] = True
        if removed:
            df.loc[df["表題"].isin(removed), "選択"] = False
        st.session_state["catalog_df"] = df
        st.session_state["prev_bulk_titles"] = bulk_titles
        catalog_df = df

    # 選択済み先頭・類似度順にソート
    display_df = sort_by_selection_and_similarity(catalog_df)

    st.caption("左端のチェックボックスで個別に選択・解除できます。選択済み行が先頭に表示されます。")
    edited_df = st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "選択": st.column_config.CheckboxColumn("選択", width="small"),
        },
        disabled=[c for c in display_df.columns if c != "選択"],
        key="catalog_editor",
    )

    # 個別チェック編集をセッションに反映（表示順→元のインデックスで上書き）
    merged = catalog_df.set_index("statsDataId")
    for _, row in edited_df.iterrows():
        sid = row.get("statsDataId")
        if sid and sid in merged.index:
            merged.at[sid, "選択"] = row["選択"]
    st.session_state["catalog_df"] = merged.reset_index()

    selected_ids = (
        edited_df.loc[edited_df["選択"], "statsDataId"]
        .dropna()
        .astype(str)
        .tolist()
    )

    if selected_ids:
        st.success(f"{len(selected_ids)} 件を選択中: {', '.join(selected_ids)}")
        if st.button("選択を保存して Join Check へ進む", type="primary"):
            st.session_state["selected_stats_ids"] = selected_ids
            st.switch_page("pages/2_Join_Check.py")
    else:
        already = st.session_state.get("selected_stats_ids", [])
        if already:
            st.info(f"保存済み: {', '.join(already)}")

elif catalog_df is not None and catalog_df.empty:
    st.info("該当する統計表がありません。")
