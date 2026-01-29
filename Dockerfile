# ChemEng Docker Image
# Python 3.10 + FastAPI

FROM python:3.10-slim

# メタデータ
LABEL maintainer="WalkTalk Hub Team"
LABEL description="ChemEng - Chemical Engineering Calculation Module"

# 作業ディレクトリ
WORKDIR /app

# システム依存関係（thermo/chemicalsのビルドに必要な場合）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 依存関係のインストール（キャッシュ活用のため先にコピー）
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# アプリケーションコード
COPY . .

# パッケージとしてインストール
RUN pip install --no-cache-dir -e .

# 非rootユーザーで実行
RUN useradd --create-home appuser
USER appuser

# ポート公開
EXPOSE 8000

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api')" || exit 1

# 起動コマンド
CMD ["uvicorn", "chemeng.interface.api:app", "--host", "0.0.0.0", "--port", "8000"]
