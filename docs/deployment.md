# ChemEng デプロイメントガイド

ローカルサーバー + Vercelフロントエンド構成のセットアップ手順。

## アーキテクチャ概要

```
[ブラウザ] → [Vercel (UI)] → [ngrok トンネル] → [ローカルPC (計算サーバー)]
```

- **Vercel**: 軽量なフロントエンドUI
- **ローカルPC**: 重い計算処理を担当するFastAPIサーバー
- **ngrok**: ローカルサーバーを外部からアクセス可能にするトンネル

## 前提条件

- Python 3.10以上
- pip (Python パッケージマネージャー)
- ngrok アカウント（無料）

## セットアップ手順

### 1. 依存パッケージのインストール

```bash
cd d:\dev\chemEng
pip install -e ".[api]"
```

### 2. ngrokのインストール

#### オプション1: winget（推奨）

```bash
winget install ngrok
```

#### オプション2: 公式サイト

1. https://ngrok.com/download にアクセス
2. Windows版をダウンロード
3. 解凍してパスの通った場所に配置

### 3. ngrokアカウント設定

1. https://dashboard.ngrok.com/signup でアカウント作成
2. https://dashboard.ngrok.com/get-started/your-authtoken でトークン取得
3. 以下のコマンドでトークンを設定:

```bash
ngrok config add-authtoken YOUR_TOKEN_HERE
```

### 4. ローカルサーバー起動

```bash
# 方法1: 起動スクリプト（推奨）
# Windows:
ChemEng_Start.bat
# macOS/Linux:
./start.sh

# 方法2: 直接実行
python server.py --port 8000

# 方法3: uvicorn直接実行
python -m uvicorn interface.api:app --host 0.0.0.0 --port 8000
```

### 5. ngrokトンネル起動

別のターミナルウィンドウで:

```bash
ngrok http 8000
```

ngrokが起動すると、以下のような出力が表示されます:

```
Forwarding    https://xxxx-xxx-xxx.ngrok-free.app -> http://localhost:8000
```

この `https://xxxx-xxx-xxx.ngrok-free.app` がバックエンドのURLです。

### 6. Vercel環境変数の設定

1. [Vercelダッシュボード](https://vercel.com/dashboard) にアクセス
2. プロジェクトを選択
3. Settings → Environment Variables
4. 以下を追加:

| Key           | Value                                 |
| ------------- | ------------------------------------- |
| `BACKEND_URL` | `https://xxxx-xxx-xxx.ngrok-free.app` |

5. Productionにデプロイ

## 動作確認

### ローカルサーバー確認

```bash
# APIドキュメント
curl http://localhost:8000/docs

# エンジン一覧
curl http://localhost:8000/api/v1/engines
```

### ngrok経由確認

```bash
curl https://xxxx-xxx-xxx.ngrok-free.app/api/v1/engines
```

### Vercel経由確認

```bash
curl https://your-project.vercel.app/api/v1/engines
```

## トラブルシューティング

### ngrok接続エラー

```
Cannot connect to backend server
```

- ローカルサーバーが起動しているか確認
- ngrokが正しいポート（8000）を指しているか確認

### CORS エラー

ブラウザでCORSエラーが発生する場合:

- `interface/api.py` のCORS設定を確認
- `allow_origins` に適切なドメインを追加

### 無料プランのURL変更

ngrok無料プランでは、再起動のたびにURLが変わります。

対策:

1. 有料プラン（月$8〜）で固定URL
2. Cloudflare Tunnel（無料、固定URL可能）
3. 起動スクリプトでVercel環境変数を自動更新

## 将来のEC2移行

ローカルサーバーをEC2に移行する場合:

1. EC2インスタンスを起動
2. 同じコードをデプロイ
3. `BACKEND_URL` をEC2のURL/IPに変更

```bash
# EC2での起動例
python server.py --host 0.0.0.0 --port 8000
```

Elastic IPを使用すれば固定IPが得られます。
