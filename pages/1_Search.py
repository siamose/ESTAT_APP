from __future__ import annotations

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
        catalog_df = catalog_df.reset_index(drop=True)
        # 並び替えや重複IDに左右されない一意キー（選択状態の同期に使う）
        catalog_df["_row_uid"] = range(len(catalog_df))
        st.session_state["catalog_df"] = catalog_df
        st.session_state["selected_stats_ids"] = []
        st.session_state["prev_bulk_titles"] = []
        st.session_state["prev_sort"] = None
        st.session_state["last_display_uids"] = []
        # 新しい検索結果に合わせてエディタ/一括選択を作り直す
        st.session_state["editor_nonce"] = st.session_state.get("editor_nonce", 0) + 1
        st.session_state["bulk_epoch"] = st.session_state.get("bulk_epoch", 0) + 1
    except EstatApiError as exc:
        st.error(f"API エラー: {exc}")
    except Exception as exc:
        st.error(f"検索に失敗しました: {exc}")

# ---------- 結果表示 ----------
catalog_df: pd.DataFrame | None = st.session_state.get("catalog_df")

SORT_NONE = "（並び替えなし）"


def _fold_edits_into_base(
    base: pd.DataFrame, editor_key: str, display_uids: list[int]
) -> None:
    """直前のグリッド編集(edited_rows)を _row_uid 経由でベースの選択へ畳み込む。"""
    state = st.session_state.get(editor_key)
    if not state:
        return
    uid_to_sel: dict[int, bool] = {}
    for pos, changes in state.get("edited_rows", {}).items():
        if "選択" in changes:
            p = int(pos)
            if 0 <= p < len(display_uids):
                uid_to_sel[display_uids[p]] = bool(changes["選択"])
    if uid_to_sel:
        mapped = base["_row_uid"].map(uid_to_sel)
        base.loc[mapped.notna(), "選択"] = mapped[mapped.notna()].astype(bool)


if catalog_df is not None and not catalog_df.empty:
    st.subheader("検索結果")

    visible_cols = [c for c in catalog_df.columns if c != "_row_uid"]
    sortable_cols = [c for c in visible_cols if c != "選択"]
    cur_nonce = st.session_state.setdefault("editor_nonce", 0)
    cur_key = f"catalog_editor_{cur_nonce}"
    last_uids: list[int] = st.session_state.get("last_display_uids", [])

    # ---- 並び替えは自前で管理（グリッドを作り直しても保持されるようにする） ----
    sc_col, so_col = st.columns([3, 1])
    with sc_col:
        sort_col = st.selectbox("並び替え", [SORT_NONE] + sortable_cols, key="sort_col")
    with so_col:
        sort_order = st.radio("順序", ["昇順", "降順"], horizontal=True, key="sort_order")

    # ---- 表題で一括選択 ----
    bulk_epoch = st.session_state.setdefault("bulk_epoch", 0)
    unique_titles = catalog_df["表題"].dropna().unique().tolist()
    bulk_titles: list[str] = st.multiselect(
        "表題で一括選択（選んだ表題の行をまとめてチェック）",
        options=unique_titles,
        key=f"bulk_titles_{bulk_epoch}",
    )
    prev_bulk: list[str] = st.session_state.get("prev_bulk_titles", [])
    bulk_added = set(bulk_titles) - set(prev_bulk)
    bulk_removed = set(prev_bulk) - set(bulk_titles)

    # ---- グリッド生成前に「ベースを書き換える操作」を適用し、グリッドを作り直す ----
    # 手動チェック済みセルは同一keyでは上書きできないため、ベースを更新してから
    # key を変えて作り直す。ソートは自前管理なので作り直しても崩れない。
    pending = st.session_state.pop("pending_action", None)
    cur_sort = (sort_col, sort_order)
    sort_changed = cur_sort != st.session_state.get("prev_sort")
    need_remount = bool(pending) or sort_changed or bool(bulk_added or bulk_removed)

    if need_remount:
        # 直前の手動チェックをベースへ畳み込んでから操作を適用（取りこぼし防止）
        _fold_edits_into_base(catalog_df, cur_key, last_uids)

        if pending == "clear":
            catalog_df["選択"] = False
            st.session_state["prev_bulk_titles"] = []
            st.session_state["bulk_epoch"] = bulk_epoch + 1
        elif isinstance(pending, dict) and "deselect" in pending:
            sid = pending["deselect"]
            catalog_df.loc[catalog_df["statsDataId"].astype(str) == sid, "選択"] = False

        if bulk_added:
            catalog_df.loc[catalog_df["表題"].isin(bulk_added), "選択"] = True
        if bulk_removed:
            catalog_df.loc[catalog_df["表題"].isin(bulk_removed), "選択"] = False
        if bulk_added or bulk_removed:
            st.session_state["prev_bulk_titles"] = bulk_titles

        st.session_state["prev_sort"] = cur_sort
        st.session_state["catalog_df"] = catalog_df
        st.session_state.pop(cur_key, None)
        cur_nonce += 1
        st.session_state["editor_nonce"] = cur_nonce

    # ---- 表示用DataFrame（自前ソートを適用） ----
    display_df = catalog_df
    if sort_col != SORT_NONE and sort_col in catalog_df.columns:
        display_df = catalog_df.sort_values(
            sort_col, ascending=(sort_order == "昇順"), kind="stable", na_position="last"
        )
    st.session_state["last_display_uids"] = display_df["_row_uid"].tolist()

    st.caption("左端のチェックで個別選択。並び替えは上の「並び替え」を使ってください。")
    edited_df = st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_order=visible_cols,
        column_config={
            "選択": st.column_config.CheckboxColumn("選択", width="small"),
        },
        disabled=[c for c in visible_cols if c != "選択"],
        key=f"catalog_editor_{cur_nonce}",
    )

    # 選択の真実 = グリッドの現在状態（edited_df）
    selected_ids = (
        edited_df[edited_df["選択"].astype(bool)]["statsDataId"]
        .dropna()
        .astype(str)
        .tolist()
    )
    selected_ids = list(dict.fromkeys(selected_ids))  # 重複排除・順序維持

    if selected_ids:
        # 選択中アイテムの表題を引く（重複IDは先頭を採用）
        title_lookup = (
            catalog_df.assign(_sid=catalog_df["statsDataId"].astype(str))
            .dropna(subset=["statsDataId"])
            .drop_duplicates(subset="_sid")
            .set_index("_sid")["表題"]
            .to_dict()
        )

        head_col, clear_col = st.columns([3, 1])
        with head_col:
            st.success(f"{len(selected_ids)} 件を選択中")
        with clear_col:
            if st.button("すべて解除", use_container_width=True):
                st.session_state["pending_action"] = "clear"
                st.rerun()

        for sid in selected_ids:
            title = title_lookup.get(sid) or ""
            label_col, del_col = st.columns([8, 1])
            with label_col:
                st.markdown(f"`{sid}` {title}")
            with del_col:
                if st.button("×", key=f"deselect_{sid}", help="この項目を選択から外す"):
                    st.session_state["pending_action"] = {"deselect": sid}
                    st.rerun()

        if st.button("選択を保存して Join Check へ進む", type="primary"):
            st.session_state["selected_stats_ids"] = selected_ids
            st.switch_page("pages/2_Join_Check.py")
    else:
        already = st.session_state.get("selected_stats_ids", [])
        if already:
            st.info(f"保存済み: {', '.join(already)}")

elif catalog_df is not None and catalog_df.empty:
    st.info("該当する統計表がありません。")
