from __future__ import annotations

import streamlit as st

from src.config import get_config


st.set_page_config(
    page_title="e-Stat 統計表検索・結合・可視化",
    page_icon="📊",
    layout="wide",
)

config = get_config()

st.title("e-Stat 統計表検索・結合・可視化")
st.caption("複数の statsDataId を取得し、メタ情報に基づいて整形・結合・可視化するMVPです。")

status_col, count_col, port_col = st.columns(3)
with status_col:
    st.metric("APIキー", "設定済み" if config.has_api_key else "未設定")
with count_col:
    selected = st.session_state.get("selected_stats_ids", [])
    st.metric("選択中の統計表", len(selected))
with port_col:
    st.metric("指定ポート", config.streamlit_server_port or "デフォルト")

if not config.has_api_key:
    st.error("eSTAT_API_KEY が未設定です。.env またはOS環境変数に設定してください。")
    st.code("eSTAT_API_KEY=your_estat_api_key\nSTREAMLIT_SERVER_PORT=", language="env")

st.subheader("使い方")
st.markdown(
    """
1. `Search` ページで検索条件または手入力から `statsDataId` を選択する
2. `Join Check` ページでデータ取得、メタ情報比較、結合を実行する
3. `Dashboard` ページで結合済みデータを確認し、グラフ表示やCSV保存を行う
"""
)

st.subheader("MVPで扱う範囲")
st.write(
    "Safe Join / Warning Join / Force Join を使って、構造差分を確認しながら複数統計表を縦方向に結合します。"
)
