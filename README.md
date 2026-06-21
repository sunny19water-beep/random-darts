# Random Darts

ダーツボードのターゲットをランダムに出題し、練習結果を記録・分析するFlaskアプリです。

## 主な機能

- Normal、Advanced、Cricket練習
- 成功本数の記録と成功率グラフ
- 成功率ワースト7を巡回する苦手ナンバー練習
- メールアドレス・ユーザー名・パスワードによるアカウント登録
- ログインユーザー別の記録保存
- 今週（月曜開始・日本時間）と歴代の成功率ランキング

## 使用技術

- Python 3.13 / Flask
- SQLite
- HTML / CSS / JavaScript Canvas
- Gunicorn
- Render

## 制作背景

競技プログラミングを通じて学んだPythonを、形に残るWebアプリへ発展させるために制作しました。好きなダーツを題材に、ランダムなターゲットを狙う練習と、成功率・苦手ナンバーの分析を一つのアプリにまとめています。Flaskのルーティング、HTML/CSSとの連携、DB設計、認証、デプロイまでを試行錯誤しながら実装しています。

## ローカル実行

```powershell
.\venv\Scripts\python.exe -m flask --app flaskr run --debug
```

ブラウザで <http://127.0.0.1:5000> を開きます。DBは `instance/darts.sqlite` に自動作成されます。

テスト:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Renderへのデプロイ

このリポジトリの `render.yaml` をBlueprintとして使用します。

- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn --workers 1 --threads 4 --timeout 120 --access-logfile - flaskr:app`
- Health Check: `/health`
- DB保存先: `/var/data/darts.sqlite`

`render.yaml` はSQLiteを永続化するため、1GBの永続ディスクと `starter` プランを指定しています。永続ディスクなしでデプロイすると、再起動や再デプロイでユーザーと記録が失われる可能性があります。

既存のRenderサービスをそのまま更新する場合、`render.yaml` の内容が既存サービスへ自動適用されるとは限りません。Render Dashboardで次の項目を設定してからデプロイしてください。

1. 永続ディスクを追加し、マウント先を `/var/data` にする
2. 下記3つの環境変数を設定する
3. Start CommandとHealth Check Pathを上記の値へ変更する
4. デプロイ後に `/health` が `{"status":"ok"}` を返すことを確認する

ローカルの `instance/darts.sqlite` はGit管理外です。ローカルの匿名記録はデプロイ先へ自動コピーされず、新しい永続ディスクでは空のDBから始まります。

### 必須環境変数

| 変数 | 用途 |
|---|---|
| `APP_ENV=production` | Secure Cookieなどの本番設定を有効化 |
| `SECRET_KEY` | セッション署名。Blueprintでは自動生成 |
| `DATABASE_PATH=/var/data/darts.sqlite` | 永続ディスク上のSQLiteファイル |

## 現在の制約

- メールアドレスの所有確認メールとパスワード再設定は未実装です。
- SQLiteを使うため、Gunicornは1プロセス構成です。利用者が増えた場合はPostgreSQLへの移行を推奨します。
- ランキングの結果は自己申告した成功本数をもとにしています。

公開URL: <https://random-darts.onrender.com/>
