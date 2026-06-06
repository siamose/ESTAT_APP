from __future__ import annotations

import io

import plotly.express as px
import streamlit as st

from src.visualizer import aggregate_for_chart, missing_summary, numeric_summary


st.set_page_config(page_title="Dashboard | e-Stat MVP", layout="wide")
st.title("ダッシュボード")

analysis_df = st.session_state.get("analysis_df")

if analysis_df is None:
    st.info("Join Check ページで結合DataFrameを作成してください。")
    st.stop()

st.subheader("データ概要")
col1, col2 = st.columns(2)
with col1:
    st.metric("行数", f"{len(analysis_df):,}")
with col2:
    st.metric("列数", len(analysis_df.columns))

st.subheader("数値サマリー")
num_summary = numeric_summary(analysis_df)
if num_summary.empty:
    st.info("value 列がありません。")
else:
    st.dataframe(num_summary, use_container_width=True)

with st.expander("欠損値サマリー"):
    st.dataframe(missing_summary(analysis_df), use_container_width=True, hide_index=True)

st.subheader("グラフ表示")
label_cols = [c for c in analysis_df.columns if c.endswith("_label") or c in ("survey_date", "statsDataId")]
numeric_cols = [c for c in analysis_df.columns if analysis_df[c].dtype in ("float64", "int64")]

if not label_cols or not numeric_cols:
    st.warning("ラベル列または数値列が見つかりません。")
else:
    col_x, col_y, col_color, col_agg, col_chart = st.columns([2, 1, 2, 1, 1])
    with col_x:
        x_col = st.selectbox("X軸", label_cols)
    with col_y:
        y_col = st.selectbox("Y軸", numeric_cols)
    with col_color:
        color_options = ["なし"] + [c for c in label_cols if c != x_col]
        color_col = st.selectbox("色分け", color_options)
    with col_agg:
        agg_func = st.selectbox("集計", ["sum", "mean", "median"])
    with col_chart:
        chart_type = st.selectbox("グラフ種別", ["bar", "line", "scatter"])

    color_col_value = None if color_col == "なし" else color_col
    chart_df = aggregate_for_chart(analysis_df, x_col, y_col, color_col_value, agg_func)

    if chart_df.empty:
        st.warning("集計結果が空です。")
    else:
        if chart_type == "bar":
            fig = px.bar(chart_df, x=x_col, y=y_col, color=color_col_value)
        elif chart_type == "line":
            fig = px.line(chart_df, x=x_col, y=y_col, color=color_col_value, markers=True)
        else:
            fig = px.scatter(chart_df, x=x_col, y=y_col, color=color_col_value)
        st.plotly_chart(fig, use_container_width=True)

st.subheader("データプレビュー")
st.dataframe(analysis_df.head(200), use_container_width=True, hide_index=True)

st.subheader("CSV ダウンロード")
csv_bytes = analysis_df.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    label="CSV をダウンロード",
    data=io.BytesIO(csv_bytes),
    file_name="estat_joined.csv",
    mime="text/csv",
)
