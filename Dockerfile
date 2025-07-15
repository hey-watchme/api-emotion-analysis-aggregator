FROM python:3.11-slim

# 作業ディレクトリを設定
WORKDIR /app

# 依存関係ファイルをコピー
COPY requirements.txt .

# 依存関係をインストール
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションファイルをコピー
COPY api_server.py .
COPY opensmile_aggregator.py .
COPY emotion_scoring.py .
COPY emotion_scoring_rules.yaml .
COPY supabase_service.py .
COPY .env.example .

# ポート8012を公開
EXPOSE 8012

# アプリケーションを起動
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8012"]