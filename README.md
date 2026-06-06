# e-Stat 統計表検索・結合・可視化アプリ

e-Stat APIから統計表データを取得し、複数の `statsDataId` をメタ情報に基づいて整形・結合・可視化するStreamlit MVPです。

## セットアップ

```bash
cd estat_app
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

依存ライブラリをインストールします。

```bash
pip install -r requirements.txt
```

`.env.example` をコピーして `.env` を作成し、APIキーを設定します。

```powershell
Copy-Item .env.example .env
```

```env
eSTAT_API_KEY=your_estat_api_key
STREAMLIT_SERVER_PORT=
```

## 起動

通常起動:

```bash
streamlit run app.py
```

ポートを指定する場合:

```bash
streamlit run app.py --server.port 8502
```

## 使い方

1. `Search` ページで検索条件または手入力から `statsDataId` を保存する
2. `Join Check` ページでデータ取得とJoin判定を実行する
3. 結合DataFrameを作成する
4. `Dashboard` ページでプレビュー、統計量、可視化、CSVダウンロードを行う

## MVPの範囲

* e-Stat APIの `getStatsList` / `getStatsData` 呼び出し
* VALUEとCLASS_INFのDataFrame化
* コード列へのラベル列付与
* Safe Join / Warning Join / Cannot Join 判定
* Force Join相当の共通列結合、全列結合
* CSVダウンロード
* Plotlyによる折れ線グラフ、棒グラフ
