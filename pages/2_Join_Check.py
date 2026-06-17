from __future__ import annotations

import streamlit as st

from src.config import require_api_key
from src.estat_client import EstatApiError, EstatClient
from src.joiner import join_dataframes
from src.metadata import judge_join_type
from src.parser import build_analysis_df, parse_stats_data


st.set_page_config(page_title="Join Check | e-Stat MVP", layout="wide")
st.title("Join判定")

selected_ids = st.session_state.get("selected_stats_ids", [])

if not selected_ids:
    st.info("Search ページで statsDataId を選択するか、手入力で保存してください。")
    st.stop()

try:
    api_key = require_api_key()
except EnvironmentError as e:
    st.error(str(e))
    st.stop()

st.write("選択中の statsDataId")
st.code("\n".join(selected_ids))

limit = st.number_input(
    "各統計表の最大取得件数",
    min_value=100,
    max_value=100000,
    value=10000,
    step=100,
    key="fetch_limit",
    help="MVPでは大量データ取得を避けるため上限を指定できます。",
)
collect_all_pages = st.checkbox("NEXT_KEYで全ページ取得する", value=False)

btn_col1, btn_col2 = st.columns([3, 2])
with btn_col1:
    run_button = st.button("データ取得とJoin判定を実行", type="primary")
with btn_col2:
    if st.button("10万件にセット"):
        st.session_state["fetch_limit"] = 100000
        st.rerun()

if run_button:
    client = EstatClient(api_key)
    meta_dfs = {}
    analysis_dfs = []
    raw_values = {}
    raw_meta = {}

    progress = st.progress(0)
    for index, stats_data_id in enumerate(selected_ids, start=1):
        try:
            payload = client.get_stats_data(
                stats_data_id,
                limit=int(limit),
                collect_all_pages=collect_all_pages,
            )
            values_df, meta_df, table_meta = parse_stats_data(payload, stats_data_id)
            analysis_df = build_analysis_df(values_df, meta_df, table_meta)
            meta_dfs[stats_data_id] = meta_df
            analysis_dfs.append(analysis_df)
            raw_values[stats_data_id] = values_df
            raw_meta[stats_data_id] = meta_df
        except EstatApiError as exc:
            st.error(f"{stats_data_id} API エラー: {exc}")
        except Exception as exc:
            st.error(f"{stats_data_id} の取得に失敗しました: {exc}")
        progress.progress(index / len(selected_ids))

    join_status, detail_df = judge_join_type(meta_dfs)
    st.session_state["join_status"] = join_status
    st.session_state["join_detail_df"] = detail_df
    st.session_state["analysis_dfs"] = analysis_dfs
    st.session_state["raw_values"] = raw_values
    st.session_state["raw_meta"] = raw_meta

join_status = st.session_state.get("join_status")
detail_df = st.session_state.get("join_detail_df")
analysis_dfs = st.session_state.get("analysis_dfs", [])

if join_status and detail_df is not None:
    if join_status == "Safe Join":
        st.success("Safe Join: メタ情報の構造が一致しています。")
    elif join_status == "Warning Join":
        st.warning("Warning Join: 軸構造は近いですが、分類コードや名称に差分があります。")
    else:
        st.error("Cannot Join: 同一項目として扱うには危険な差分があります。")

    st.dataframe(detail_df, use_container_width=True, hide_index=True)

    mode_options = ["そのまま縦結合（Safe）", "全列を残して欠損を許容する", "共通列のみ残す"]
    mode_default = 0 if join_status == "Safe Join" else 1
    mode = st.radio("結合モード", mode_options, index=mode_default, horizontal=True)

    if st.button("結合DataFrameを作成", type="primary"):
        joined_df = join_dataframes(analysis_dfs, mode)
        st.session_state["analysis_df"] = joined_df
        st.success(f"結合済みDataFrameを作成しました。{len(joined_df):,} 行")
        st.dataframe(joined_df.head(100), use_container_width=True, hide_index=True)

raw_meta = st.session_state.get("raw_meta", {})
if raw_meta:
    with st.expander("メタ情報プレビュー"):
        for stats_data_id, meta_df in raw_meta.items():
            st.caption(stats_data_id)
            st.dataframe(meta_df.head(50), use_container_width=True, hide_index=True)
