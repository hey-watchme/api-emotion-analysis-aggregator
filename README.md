# Kushinada v2 感情分析集計API - 完全仕様書

Kushinada v2の4感情分析結果の収集・集計・Supabase保存を行うFastAPIベースのREST APIサービスです。

## 🚨 重要：本番環境デプロイ手順（必ず以下の手順に従ってください）

### ⚠️ デプロイ前の注意事項
- **他の方法でデプロイしないでください**（手動ビルド、直接SSH、独自スクリプトなど）
- **必ず以下の公式手順を使用してください**
- **ECRリポジトリ**: `754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-api-opensmile-aggregator`
- **コンテナ名**: `opensmile-aggregator`（変更禁止）
- **ポート**: 8012（変更禁止）

### 📋 デプロイ手順（3ステップのみ）

#### Step 1: ローカルでデプロイスクリプト実行
```bash
# OpenSmile Aggregatorのディレクトリに移動
cd /path/to/api/opensmile-aggregator

# デプロイスクリプトを実行（これがECRにイメージをプッシュします）
./deploy-ecr.sh
```

#### Step 2: EC2サーバーでコンテナ更新
```bash
# EC2にSSH接続
ssh -i ~/watchme-key.pem ubuntu@3.24.16.82

# 既存コンテナを停止・削除
docker stop opensmile-aggregator
docker rm opensmile-aggregator

# 最新イメージを取得して起動
cd /home/ubuntu/watchme-opensmile-aggregator
aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com
docker pull 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-api-opensmile-aggregator:latest
docker-compose -f docker-compose.prod.yml up -d
```

#### Step 3: 動作確認
```bash
# ヘルスチェック（EC2上で実行）
curl http://localhost:8012/health

# HTTPSエンドポイント確認（どこからでも実行可能）
curl https://api.hey-watch.me/emotion-aggregator/health
```

### ❌ やってはいけないこと
- ローカルでビルドしたイメージを手動でアップロード
- systemdサービスの再起動（docker-composeを使用）
- ポート番号の変更
- コンテナ名の変更
- 独自のデプロイスクリプトの作成

### ✅ トラブルシューティング
```bash
# コンテナが起動しない場合
docker logs opensmile-aggregator

# ポートが使用中の場合
sudo lsof -i :8012

# メモリ不足の場合
docker stats --no-stream
```

## 🆕 最新アップデート (2025-10-26) - Logits生スコア & 最大値集計方式

### 🎯 設計思想: 感情のスパイクを見逃さない

**目的:**
- 月に1回しか怒らない人の「その1回」を確実に捉える
- 「どう見ても怒り」という強い値が最重要情報
- 感情の強度（intensity）を保持し、情報劣化を防ぐ

**データの流れ:**
```
1分の録音 = 10秒チャンク × 6個
  ↓
各チャンクで4感情のlogits（生スコア）を出力
  例: anger=8.5, joy=-2.1, sadness=1.2, neutral=-3.0
  ↓
30分ブロックごとに各感情の最大値を取得
  anger_max = max(8.5, -1.0, 0.3, ...) = 8.5
  ↓
4本の独立した折れ線グラフで可視化
```

### 📊 集計ロジック: 最大値方式（Max Aggregation）

**旧方式（削除）:** 平均化
```python
# ❌ 平均化するとスパイクが消える
anger_scores = [8.5, -1.0, 0.3, -2.0, -1.5, -0.5]
anger_avg = sum / count = 0.63  # 8.5のスパイクが0.63に！
```

**新方式:** 最大値抽出
```python
# ✅ 正の値の最大値を取得（スパイクを保持）
anger_scores = [8.5, -1.0, 0.3, -2.0, -1.5, -0.5]
positive_scores = [8.5, 0.3]  # 正の値のみ
anger_max = 8.5  # スパイクをそのまま記録

# 全部負の値の場合
neutral_scores = [-3.0, -1.5, -2.0, -1.8]
neutral_max = 0.0  # その感情は検出されなかった
```

**ルール:**
1. 各30分ブロック内の全チャンクから各感情の値を収集
2. **正の値（> 0）のみ抽出**
3. **最大値を採用**
4. 正の値がない場合は **0.0**（検出されなかった）
5. データがないブロックも **0.0**

### 🔧 技術的変更

**feature-extractor-v2:**
- Softmax削除 → logits生スコアをそのまま出力
- データ範囲: 0.0-1.0（確率分布） → -∞～+∞（logits、実際は-10～+10程度）
- percentage削除 → scoreのみ

**aggregator:**
- 平均化ロジック削除
- 最大値抽出ロジック実装
- 4感情を独立して処理（neutral, joy, anger, sadness）

### 📈 出力形式

```json
{
  "date": "2025-10-26",
  "emotion_graph": [
    {
      "time": "00:00",
      "neutral": 0.0,
      "joy": 0.0,
      "anger": 0.0,
      "sadness": 0.0
    },
    {
      "time": "14:00",
      "neutral": 0.0,
      "joy": 2.5,
      "anger": 8.5,   // ← このスパイクが重要！
      "sadness": 1.2
    }
  ]
}
```

**値の意味:**
- `8.5`: 強い怒りのスパイク検出（この時間帯に重要な感情イベント）
- `2.5`: 中程度の喜び
- `0.0`: その感情は検出されなかった
- 負の値は出力しない（正の値のみが「感情が検出された」という意味）

## 🆕 アップデート (2025-07-15) - Docker化とHTTPSエンドポイント

### Docker化への移行
- **Docker化完了**: Python venv + systemdからDocker + systemdに移行
- **Dockerイメージ**: `watchme-opensmile-aggregator:latest`
- **HTTPSエンドポイント**: https://api.hey-watch.me/emotion-aggregator/ でアクセス可能
- **systemdサービス更新**: Dockerコンテナの自動起動・監視に対応
- **動作確認済み**: device_id `d067d407-cf73-4174-a9c1-d91fb60d64d0`での2025-07-15データ処理成功（2スロット、13感情ポイント）

### 外部アクセス設定
- **Nginxリバースプロキシ**: `/emotion-aggregator/`エンドポイントを追加
- **CORS対応**: 外部アプリケーションからのAPIコールに対応
- **HTTPS対応**: SSL証明書による暗号化通信

## 🆕 最新アップデート (2025-07-13)

### 本番環境へのデプロイとsystemd設定
- **EC2本番環境**: AWS EC2 (3.24.16.82) に正常デプロイ完了
- **systemdサービス化**: 自動起動設定により常時稼働を実現
- **動作確認済み**: device_id `d067d407-cf73-4174-a9c1-d91fb60d64d0`での2025-07-10データ処理成功
- **ディレクトリ**: `/home/ubuntu/watchme-opensmile-aggregator`
- **Python仮想環境**: venv使用による独立した実行環境

## 🆕 最新アップデート (2025-07-10)

### 1. **WatchMe Admin統合**
- Admin画面の感情グラフタブにOpenSMILE Aggregatorセクションを追加
- デバイスIDと日付を指定して感情集計処理を実行可能
- タスクの進行状況をリアルタイムで表示
- 処理結果（データ有無、処理スロット数、総感情ポイント）を詳細表示

### 2. **CORS対応**
- FastAPIにCORSMiddlewareを追加
- Admin画面（http://localhost:9000）からのAPIコール（http://localhost:8012）に対応

### 3. **データ不在時の処理改善**
- データが存在しない日付でも正常な処理として扱う
- 空のデータ（全スロット0）をSupabaseに保存
- 「指定された日付にはデータが存在しません」というメッセージを返す
- ライフログツールとして測定していない日があっても問題なく処理

### 4. **Supabase完全移行**
- 入力: Vault API → Supabase emotion_opensmileテーブル
- 出力: ローカルファイル + Vault API → Supabase emotion_opensmile_summaryテーブル（ワイド型JSONB）
- upload_opensmile_summary.pyを削除（不要になったため）

## 📋 コードベース調査結果

### 🔍 システム構成分析
**調査日**: 2025-07-09  
**ファイル数**: 8個  
**コード行数**: 約1,600行  
**言語**: Python 3.11.8+  
**フレームワーク**: FastAPI + aiohttp + PyYAML + Supabase

### ✅ 動作検証結果
**検証日**: 2025-07-09  
**データソース**: Supabase emotion_opensmileテーブル  
**結果**: 正常動作確認済み

- ✅ API server 起動成功（ポート8012）
- ✅ Supabaseからのデータ取得成功（emotion_opensmileテーブル）
- ✅ 感情分析エンジン動作確認（8感情分類）
- ✅ Supabase保存成功（emotion_opensmile_summaryテーブル）

### 📊 主要機能の詳細分析

#### 🎯 **核心機能**
1. **OpenSMILE特徴量データ処理**
   - 30分スロット×48個（24時間分）の並列データ取得
   - eGeMAPS特徴量の自動抽出・分析
   - YAMLルールベースでの8感情スコアリング

2. **感情スコアリングエンジン**
   - anger, fear, anticipation, surprise, joy, sadness, trust, disgust
   - しきい値ベースの特徴量評価
   - スロット単位での感情ポイント集計

3. **バックグラウンドタスク処理**
   - 非同期タスク実行（FastAPI BackgroundTasks）
   - リアルタイム進捗監視（0-100%）
   - タスク状況管理（started/running/completed/failed）

4. **データ統合**
   - Supabaseからのデータ取得: emotion_opensmileテーブル
   - Supabaseへのデータ保存: emotion_opensmile_summaryテーブル（ワイド型JSONB形式）
   - 他のグラフデータベースと同じテーブル構造を採用

#### 📁 **ファイル別機能分析**

**api_server.py:240行** - メインAPIサーバー
- FastAPIアプリケーション（ポート8012）
- 5つのエンドポイント提供
- UUIDベースのタスク管理
- エラーハンドリング付きバックグラウンド処理

**opensmile_aggregator.py:209行** - データ集約エンジン
- Supabaseからのデータ取得（emotion_opensmileテーブル）
- OpenSMILE特徴量の集計・解析
- 感情スコアリングエンジン統合
- ローカルファイル保存（JSON形式）

**emotion_scoring.py:200行** - 感情スコアリングエンジン
- YAMLルールファイル読み込み
- eGeMAPS特徴量ベースの感情評価
- 8感情×しきい値比較処理
- 1日分グラフデータ生成

**upload_opensmile_summary.py:290行** - アップロード処理
- Vault APIへのFormDataアップロード
- 全ファイル/特定ファイル両対応
- 成功・失敗詳細レポート機能
- SSL証明書問題の自動回避

**example_usage.py:180行** - APIクライアント実装例
- 完全な使用フロー実装
- ヘルスチェック機能付き
- 感情分析結果表示例
- 感情スコアリングテスト機能

**emotion_scoring_rules.yaml:100行** - 感情ルール定義
- 8感情×複数ルール定義
- eGeMAPS特徴量しきい値設定
- 実測データベースの調整可能設計

#### 🔧 **技術仕様詳細**

**依存ライブラリ**
```python
fastapi>=0.104.0      # REST APIフレームワーク
uvicorn>=0.24.0       # ASGIサーバー
pydantic>=2.5.0       # データバリデーション
aiohttp>=3.8.0,<4.0.0 # 非同期HTTPクライアント
pyyaml>=6.0           # YAMLルール解析
supabase>=2.0.0       # Supabaseクライアント
python-dotenv>=1.0.0  # 環境変数管理
```

**処理能力**
- 同時並列処理: 最大48並列HTTP接続
- タイムアウト設定: 30秒/リクエスト
- SSL証明書検証: 環境変数制御可能
- メモリ効率: ストリーミング処理対応

**データ処理フロー**
1. Supabaseからのデータ取得 → 2. features_timeline解析 → 3. 特徴量集計 → 4. 感情スコアリング → 5. グラフデータ生成 → 6. ローカル保存 → 7. Vault APIへアップロード

## ⚠️ 重要: ファイル依存関係
**APIサーバー（`api_server.py`）を動作させるには、以下のファイルが必須です：**
- 📁 `api_server.py` - メインAPIサーバー
- 📁 `opensmile_aggregator.py` - データ処理モジュール (**必須依存**)
- 📁 `upload_opensmile_summary.py` - アップロードモジュール (**必須依存**)
- 📁 `emotion_scoring.py` - 感情スコアリングエンジン (**必須依存**)
- 📁 `emotion_scoring_rules.yaml` - 感情ルール定義ファイル (**必須依存**)
- 📁 `supabase_service.py` - Supabaseサービス (**必須依存**)

## 🎯 システム概要

**🌐 REST API**: FastAPIベースの非同期APIサーバー  
**📥 データ収集**: Supabase emotion_opensmileテーブルからOpenSMILEデータを取得  
**🎭 感情分析**: eGeMAPS特徴量ベースのYAMLルール感情スコアリング  
**📈 グラフ生成**: 1日48スロット分の感情推移データ生成  
**📤 データアップロード**: Vault APIへ自動アップロード  
**🔄 バックグラウンド処理**: 長時間処理の非同期実行とタスク管理

## 📋 システム要件

**🐍 Python環境:**
- Python 3.11.8以上
- FastAPI + Uvicorn（APIサーバー）
- aiohttp（HTTP非同期クライアント）
- PyYAML（ルールファイル解析）
- asyncio（非同期処理）

**🌐 ネットワーク:**
- Supabase APIへの接続（emotion_opensmileテーブル）
- Vault API `https://api.hey-watch.me/upload/analysis/opensmile-summary` へのHTTPS接続

**💾 ストレージ:**
- ローカルディスク: `/Users/kaya.matsumoto/data/data_accounts/`
- 書き込み権限必須

**📁 プロジェクト構成:**
```
opensmile-aggregator/
├── api_server.py                    # メインAPIサーバー（必須）
├── opensmile_aggregator.py          # データ処理モジュール（必須）
├── upload_opensmile_summary.py      # アップロードモジュール（必須）
├── emotion_scoring.py               # 感情スコアリングエンジン（必須）
├── emotion_scoring_rules.yaml       # 感情ルール定義ファイル（必須）
├── example_usage.py                 # 使用例（オプション）
├── requirements.txt                 # 依存関係
└── README.md                       # このファイル
```

## 🚀 セットアップ

### 1️⃣ 依存関係インストール
```bash
pip install -r requirements.txt
```

### 2️⃣ 環境変数設定
`.env`ファイルを作成し、Supabase接続情報を設定：
```bash
cp .env.example .env
# .envファイルを編集してSupabase URLとキーを設定
```

### 3️⃣ ファイル構成の確認
⚠️ **APIサーバー起動前に、必須ファイルが揃っていることを確認してください：**

```bash
ls -la
# 以下のファイルが必要です：
# - api_server.py (メイン)
# - opensmile_aggregator.py (必須依存)
# - upload_opensmile_summary.py (必須依存)
# - emotion_scoring.py (必須依存)
# - emotion_scoring_rules.yaml (必須依存)
```

### 4️⃣ APIサーバー起動
```bash
# 開発環境（推奨）
python api_server.py

# または
uvicorn api_server:app --reload --host 0.0.0.0 --port 8012

# 本番環境
uvicorn api_server:app --host 0.0.0.0 --port 8012 --workers 4
```

APIサーバーは `http://localhost:8012` で起動します。

### 5️⃣ 接続確認
```bash
curl http://localhost:8012/health
```

## 🚀 本番環境設定（AWS EC2）

### 本番環境情報
- **サーバー**: AWS EC2 (Ubuntu)
- **IPアドレス**: 3.24.16.82
- **ディレクトリ**: `/home/ubuntu/watchme-opensmile-aggregator`
- **ポート**: 8012（内部）
- **HTTPSエンドポイント**: https://api.hey-watch.me/emotion-aggregator/

### 本番環境での新しいアクセス方法

#### 外部からのAPIアクセス（推奨）
```bash
# ヘルスチェック
curl https://api.hey-watch.me/emotion-aggregator/health

# メインエンドポイント
curl https://api.hey-watch.me/emotion-aggregator/

# 感情分析実行
curl -X POST https://api.hey-watch.me/emotion-aggregator/analyze/opensmile-aggregator \
  -H "Content-Type: application/json" \
  -d '{"device_id": "d067d407-cf73-4174-a9c1-d91fb60d64d0", "date": "2025-07-15"}'
```

### 本番環境へのデプロイ手順（Docker化）

#### 1️⃣ SSHアクセス
```bash
ssh -i ~/watchme-key.pem ubuntu@3.24.16.82
```

#### 2️⃣ プロジェクトディレクトリに移動
```bash
cd /home/ubuntu/watchme-opensmile-aggregator
```

#### 3️⃣ Dockerイメージのビルド
```bash
# Dockerイメージをビルド
sudo docker build -t watchme-opensmile-aggregator:latest .
```

#### 4️⃣ 環境変数の設定
```bash
# .envファイルの確認・編集
vi .env
# Supabase URLとAPIキーが正しく設定されていることを確認
```

### systemdサービス設定（Docker化）

#### 1️⃣ サービスファイルの作成
```bash
sudo vi /etc/systemd/system/opensmile-aggregator.service
```

以下の内容を記載：
```ini
[Unit]
Description=OpenSMILE Aggregator API Docker Container
After=docker.service
Requires=docker.service

[Service]
TimeoutStartSec=0
Restart=always
RestartSec=5
# 既存のコンテナがあれば停止・削除してから起動
ExecStartPre=-/usr/bin/docker stop opensmile-aggregator
ExecStartPre=-/usr/bin/docker rm opensmile-aggregator
# Dockerコンテナを起動。ホストの8012ポートをコンテナの8012ポートにマッピング。
# --env-file で .env ファイルから環境変数を読み込みます。
ExecStart=/usr/bin/docker run --name opensmile-aggregator -p 8012:8012 --env-file /home/ubuntu/watchme-opensmile-aggregator/.env watchme-opensmile-aggregator:latest
# EnvironmentFileで環境変数を読み込む
EnvironmentFile=/home/ubuntu/watchme-opensmile-aggregator/.env

[Install]
WantedBy=multi-user.target
```

#### 2️⃣ サービスの有効化と起動
```bash
# systemdのリロード
sudo systemctl daemon-reload

# サービスを有効化（自動起動設定）
sudo systemctl enable opensmile-aggregator.service

# サービスを起動
sudo systemctl start opensmile-aggregator.service
```

#### 3️⃣ サービス管理コマンド
```bash
# サービス状態確認
sudo systemctl status opensmile-aggregator.service

# サービス再起動
sudo systemctl restart opensmile-aggregator.service

# サービス停止
sudo systemctl stop opensmile-aggregator.service

# ログ確認（リアルタイム）
sudo journalctl -u opensmile-aggregator.service -f

# 最新100行のログ確認
sudo journalctl -u opensmile-aggregator.service -n 100
```

### 本番環境での動作確認

#### APIヘルスチェック
```bash
# サーバー内から
curl http://localhost:8012/health

# 外部から（ポートが開放されている場合）
curl http://3.24.16.82:8012/health
```

#### 感情分析実行テスト
```bash
# テストデータで実行
curl -X POST http://localhost:8012/analyze/opensmile-aggregator \
  -H "Content-Type: application/json" \
  -d '{"device_id": "d067d407-cf73-4174-a9c1-d91fb60d64d0", "date": "2025-07-10"}'
```

### トラブルシューティング

#### ポートが既に使用されている場合
```bash
# ポート8012を使用しているプロセスを確認
sudo ss -tlnp | grep 8012

# プロセスを終了（PIDは上記コマンドで確認）
sudo kill <PID>
```

#### サービスが起動しない場合
```bash
# 詳細なエラーログを確認
sudo journalctl -u opensmile-aggregator.service -n 50 --no-pager

# Pythonの直接実行でエラー確認
cd /home/ubuntu/watchme-opensmile-aggregator
source venv/bin/activate
python api_server.py
```

#### 環境変数が読み込まれない場合
```bash
# .envファイルの存在確認
ls -la /home/ubuntu/watchme-opensmile-aggregator/.env

# 権限確認
chmod 600 .env
```

## 🌐 API エンドポイント詳細仕様

### 🎭 OpenSMILE感情分析API

#### **1. 感情分析開始** `POST /analyze/opensmile-aggregator`
**機能**: OpenSMILE感情分析をバックグラウンドで開始し、タスクIDを返却

**リクエスト:**
```bash
POST /analyze/opensmile-aggregator
Content-Type: application/json

{
  "device_id": "device123",    # 必須: デバイス識別子
  "date": "2025-06-26"     # 必須: 分析対象日（YYYY-MM-DD形式）
}
```

**レスポンス（成功）:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "started",
  "message": "device123/2025-06-26 の感情分析を開始しました"
}
```

**レスポンス（エラー）:**
```json
{
  "detail": "日付はYYYY-MM-DD形式で指定してください"
}
```

#### **2. 分析状況確認** `GET /analyze/opensmile-aggregator/{task_id}`
**機能**: 指定したタスクの進捗状況と結果を取得

**リクエスト:**
```bash
GET /analyze/opensmile-aggregator/550e8400-e29b-41d4-a716-446655440000
```

**レスポンス（処理中）:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "message": "OpenSMILEデータ収集・感情分析中...",
  "progress": 25,
  "device_id": "device123",
  "date": "2025-06-26",
  "created_at": "2025-06-30T10:30:00.000000"
}
```

**レスポンス（完了）:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "message": "感情分析完了",
  "progress": 100,
  "result": {
    "analysis": {
      "date": "2025-06-26",
      "emotion_graph": [
        {"time": "00:00", "anger": 0, "fear": 0, "anticipation": 0, "surprise": 0, "joy": 0, "sadness": 0, "trust": 0, "disgust": 0},
        {"time": "04:30", "anger": 4, "fear": 1, "anticipation": 2, "surprise": 1, "joy": 1, "sadness": 1, "trust": 1, "disgust": 1},
        {"time": "07:00", "anger": 0, "fear": 0, "anticipation": 2, "surprise": 1, "joy": 8, "sadness": 0, "trust": 4, "disgust": 0}
      ]
    },
    "upload": {"success": 1, "failed": 0, "total": 1},
    "total_emotion_points": 450,
    "output_path": "/Users/kaya.matsumoto/data/data_accounts/device123/2025-06-26/opensmile-summary/result.json",
    "emotion_graph_length": 48
  }
}
```

**レスポンス（失敗）:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "message": "感情分析中にエラーが発生しました",
  "progress": 100,
  "error": "接続エラー: タイムアウト"
}
```

#### **3. 全タスク一覧** `GET /analyze/opensmile-aggregator`
**機能**: 実行中・完了済みの全タスクを一覧表示

**リクエスト:**
```bash
GET /analyze/opensmile-aggregator
```

**レスポンス:**
```json
{
  "tasks": [
    {
      "task_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "completed",
      "device_id": "device123",
      "date": "2025-06-26",
      "progress": 100
    },
    {
      "task_id": "660e8400-e29b-41d4-a716-446655440001",
      "status": "running",
      "device_id": "device456",
      "date": "2025-06-27",
      "progress": 50
    }
  ],
  "total": 2
}
```

#### **4. タスク削除** `DELETE /analyze/opensmile-aggregator/{task_id}`
**機能**: 完了・失敗したタスクを削除（実行中タスクは削除不可）

**リクエスト:**
```bash
DELETE /analyze/opensmile-aggregator/550e8400-e29b-41d4-a716-446655440000
```

**レスポンス（成功）:**
```json
{
  "message": "タスク 550e8400-e29b-41d4-a716-446655440000 を削除しました"
}
```

**レスポンス（エラー）:**
```json
{
  "detail": "実行中のタスクは削除できません"
}
```

#### **5. ヘルスチェック** `GET /health` | `GET /`
**機能**: API稼働状況の確認

**リクエスト:**
```bash
GET /health
```

**レスポンス:**
```json
{
  "status": "healthy"
}
```

**リクエスト:**
```bash
GET /
```

**レスポンス:**
```json
{
  "service": "OpenSMILE感情分析API",
  "status": "running",
  "timestamp": "2025-06-30T10:30:00.000000"
}
```

## 📊 感情スコアリング仕様

### 🎭 **4感情分類（Kushinada v2）**
1. **neutral** - 中立
2. **joy** - 喜び
3. **anger** - 怒り
4. **sadness** - 悲しみ

### 🔧 **スコアリングロジック**
- **AIモデルベース**: Kushinada HuBERT-largeモデルによる直接分類
- **スコア範囲**: 0.0-1.0（確率値）
- **スロット集計**: 10秒チャンク単位で分析、30分スロット単位で平均化
- **データソース**: Supabase emotion_opensmileテーブルのfeatures_timeline

### 📐 **データフロー**
```
feature-extractor-v2 (Kushinada)
  ↓ 10秒チャンク単位で4感情分析
  ↓ {neutral: 0.25, joy: 0.15, anger: 0.10, sadness: 0.50}
emotion_opensmile テーブル保存
  ↓
aggregator が取得
  ↓ 30分スロット単位で平均化
  ↓ {neutral: 0.23, joy: 0.18, anger: 0.12, sadness: 0.47}
emotion_opensmile_summary テーブル保存
```

## 📊 データフォーマット

### 感情分析結果

**保存先:**
Supabase `emotion_opensmile_summary` テーブル

**テーブル構造:**
```sql
create table public.emotion_opensmile_summary (
  device_id   text        not null,
  date        date        not null,
  emotion_graph jsonb     not null,          -- 48 スロット入り JSON
  file_path   text,
  created_at  timestamptz not null default now(),
  primary key (device_id, date)
);
```

**emotion_graph JSON構造（Kushinada v2: 4感情）:**
```json
{
  "date": "2025-10-26",
  "emotion_graph": [
    {"time": "00:00", "neutral": 0.0, "joy": 0.0, "anger": 0.0, "sadness": 0.0},
    {"time": "00:30", "neutral": 0.0, "joy": 0.0, "anger": 0.0, "sadness": 0.0},
    {"time": "04:30", "neutral": 0.15, "joy": 0.20, "anger": 0.45, "sadness": 0.20},
    {"time": "07:00", "neutral": 0.10, "joy": 0.75, "anger": 0.05, "sadness": 0.10},
    {"time": "12:00", "neutral": 0.20, "joy": 0.15, "anger": 0.50, "sadness": 0.15},
    {"time": "23:30", "neutral": 0.80, "joy": 0.10, "anger": 0.05, "sadness": 0.05}
  ]
}
```

**注**: スコアは0.0-1.0の範囲のfloat値で、4感情の合計が1.0になる確率分布を表します。

### Kushinada v2 モデル仕様

**モデル情報:**
- **ベースモデル**: HuBERT-large (Facebook AI)
- **日本語特化**: 産総研Kushinadaモデル
- **感情分類**: 4感情（neutral, joy, anger, sadness）
- **入力**: 16kHz音声波形
- **セグメント**: 10秒固定長
- **出力**: 4感情の確率分布（合計1.0）

**処理の特徴:**
- **エンドツーエンド**: 音声から直接感情を分類
- **特徴量抽出不要**: HuBERTが自動で特徴を学習
- **高精度**: JTESデータセットで学習済み
- **ロバスト性**: ノイズや話者変動に強い

## 💡 実用的な使用例

### Python クライアント（完全版）
```python
import asyncio
import aiohttp
from datetime import datetime

class OpenSMILEAnalysisClient:
    def __init__(self, base_url="http://localhost:8012"):
        self.base_url = base_url
    
    async def health_check(self):
        """APIの稼働状況を確認"""
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.base_url}/health") as response:
                    return response.status == 200
        except Exception as e:
            print(f"❌ API接続エラー: {e}")
            return False
    
    async def start_analysis(self, device_id, date):
        """感情分析を開始してタスクIDを取得"""
        try:
            data = {"device_id": device_id, "date": date}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/analyze/opensmile-aggregator",
                    json=data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        print(f"✅ 感情分析開始: {result['message']}")
                        return result["task_id"]
                    else:
                        error = await response.json()
                        print(f"❌ 感情分析開始エラー: {error['detail']}")
                        return None
        except Exception as e:
            print(f"❌ 感情分析開始エラー: {e}")
            return None
    
    async def wait_for_completion(self, task_id, max_wait=600):
        """感情分析完了まで待機（タイムアウト付き）"""
        print(f"⏳ 感情分析完了を待機中... (最大{max_wait}秒)")
        
        start_time = datetime.now()
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.base_url}/analyze/opensmile-aggregator/{task_id}"
                    ) as response:
                        if response.status != 200:
                            print(f"❌ 状況取得エラー: HTTP {response.status}")
                            return None
                        
                        status = await response.json()
            except Exception as e:
                print(f"❌ 状況取得エラー: {e}")
                return None
            
            # 進捗表示
            elapsed = (datetime.now() - start_time).seconds
            print(f"🎭 進捗: {status['progress']}% - {status['message']} ({elapsed}秒経過)")
            
            if status['status'] == 'completed':
                print("🎉 感情分析完了!")
                return status
            elif status['status'] == 'failed':
                print(f"❌ 感情分析失敗: {status.get('error', '不明なエラー')}")
                return status
            
            if elapsed >= max_wait:
                print("⏰ タイムアウト: 感情分析が時間内に完了しませんでした")
                return None
            
            await asyncio.sleep(2)  # 2秒間隔でチェック
    
    async def run_full_analysis(self, device_id, date):
        """完全な感情分析フローを実行"""
        print(f"🚀 OpenSMILE感情分析開始: {device_id} / {date}")
        
        # 1. ヘルスチェック
        if not await self.health_check():
            print("❌ APIサーバーが応答しません")
            return None
        
        # 2. 感情分析開始
        task_id = await self.start_analysis(device_id, date)
        if not task_id:
            return None
        
        # 3. 完了まで待機
        result = await self.wait_for_completion(task_id)
        if not result:
            return None
        
        # 4. 結果処理
        if result['status'] == 'completed' and 'result' in result:
            analysis_data = result['result']['analysis']
            upload_data = result['result']['upload']
            
            print(f"\n📊 感情分析結果:")
            print(f"  📁 出力ファイル: {result['result']['output_path']}")
            print(f"  🎭 総感情ポイント数: {result['result']['total_emotion_points']}")
            print(f"  📈 グラフデータ点数: {result['result']['emotion_graph_length']}")
            print(f"  ☁️ アップロード: 成功 {upload_data['success']}, 失敗 {upload_data['failed']}")
            
            # トップ感情表示
            emotion_graph = analysis_data.get('emotion_graph', [])
            if emotion_graph:
                print(f"\n🎭 感情推移サンプル（最初の5スロット）:")
                for slot_data in emotion_graph[:5]:
                    emotions = []
                    for emotion in ["anger", "fear", "anticipation", "surprise", "joy", "sadness", "trust", "disgust"]:
                        score = slot_data.get(emotion, 0)
                        if score > 0:
                            emotions.append(f"{emotion}:{score}")
                    
                    emotion_str = ", ".join(emotions) if emotions else "ニュートラル"
                    print(f"  {slot_data['time']}: {emotion_str}")
            
            return result
        
        return result

# 使用例
async def main():
    client = OpenSMILEAnalysisClient()
    
    # 単体分析実行
    result = await client.run_full_analysis("device123", "2025-06-26")
    
    # 複数日分析実行
    dates = ["2025-06-24", "2025-06-25", "2025-06-26"]
    for date in dates:
        print(f"\n{'='*60}")
        await client.run_full_analysis("device123", date)
        await asyncio.sleep(1)  # 1秒間隔

# 実行
if __name__ == "__main__":
    asyncio.run(main())
```

### Bash/curl スクリプト
```bash
#!/bin/bash
# OpenSMILE感情分析 実行スクリプト

API_BASE="http://localhost:8012"
DEVICE_ID="device123"
DATE="2025-06-26"

echo "🚀 OpenSMILE感情分析開始: $DEVICE_ID / $DATE"

# 1. ヘルスチェック
echo "🔍 APIヘルスチェック..."
if ! curl -s -f "$API_BASE/health" > /dev/null; then
    echo "❌ APIサーバーが応答しません"
    exit 1
fi
echo "✅ API稼働中"

# 2. 感情分析開始
echo "🎭 感情分析開始..."
RESPONSE=$(curl -s -X POST "$API_BASE/analyze/opensmile-aggregator" \
  -H "Content-Type: application/json" \
  -d "{\"device_id\": \"$DEVICE_ID\", \"date\": \"$DATE\"}")

TASK_ID=$(echo "$RESPONSE" | jq -r '.task_id')
if [ "$TASK_ID" = "null" ]; then
    echo "❌ 感情分析開始エラー:"
    echo "$RESPONSE" | jq '.'
    exit 1
fi

echo "✅ 感情分析開始成功: Task ID = $TASK_ID"

# 3. 進捗監視
echo "⏳ 感情分析完了まで待機..."
while true; do
    STATUS_RESPONSE=$(curl -s "$API_BASE/analyze/opensmile-aggregator/$TASK_ID")
    STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status')
    PROGRESS=$(echo "$STATUS_RESPONSE" | jq -r '.progress')
    MESSAGE=$(echo "$STATUS_RESPONSE" | jq -r '.message')
    
    echo "🎭 進捗: $PROGRESS% - $MESSAGE"
    
    if [ "$STATUS" = "completed" ]; then
        echo "🎉 感情分析完了!"
        echo "$STATUS_RESPONSE" | jq '.result'
        break
    elif [ "$STATUS" = "failed" ]; then
        echo "❌ 感情分析失敗:"
        echo "$STATUS_RESPONSE" | jq '.error'
        exit 1
    fi
    
    sleep 2
done

echo "✅ OpenSMILE感情分析が正常に完了しました"
```

## 🚨 エラーハンドリング

### よくあるエラー

**404 - タスクが見つかりません**
```json
{"detail": "タスクが見つかりません"}
```

**400 - 日付形式エラー**
```json
{"detail": "日付はYYYY-MM-DD形式で指定してください"}
```

**SSL証明書検証エラー**
```
SSLCertVerificationError: certificate verify failed: unable to get local issuer certificate
```
→ 解決方法: 環境変数 `VERIFY_SSL=false` を設定してSSL検証を無効化

**500 - 内部エラー**
```json
{
  "status": "failed",
  "message": "感情分析中にエラーが発生しました",
  "error": "詳細なエラーメッセージ"
}
```

### 正常な動作
- **404エラー**: 該当スロットのファイルが存在しない場合はスキップ（通常の動作）
- **空ファイル**: データが空の場合は全感情0でスキップ  
- **特徴量なし**: eGeMAPS特徴量が見つからない場合は全感情0
- **タイムアウト**: 30秒でタイムアウト、該当スロットをスキップ
- **JSON解析エラー**: 不正な形式のファイルはスキップ
- **データが少ない場合**: 48スロット中1つしかデータがない場合でも正常に処理される
- **SSL証明書検証**: デフォルトで無効化され、ダッシュボード環境での接続問題を回避

## 🏗️ システム構成と依存関係

### 📋 プログラム間の依存関係

```
┌─────────────────────────────────────┐
│          api_server.py              │ ← メインAPIサーバー
│    (FastAPIアプリケーション)          │
└─────────────────────────────────────┘
              │
              ├─ 必須依存 ─→ ┌─────────────────────────────────────┐
              │              │    opensmile_aggregator.py          │
              │              │  データ収集・感情分析モジュール        │
              │              │    (単体実行も可能)                 │
              │              └─────────────────────────────────────┘
              │                              │
              │                              ├─ 必須依存 ─→ ┌─────────────────────────────────────┐
              │                              │              │     emotion_scoring.py             │
              │                              │              │   感情スコアリングエンジン            │
              │                              │              └─────────────────────────────────────┘
              │                              │                              │
              │                              │                              └─ 必須依存 ─→ emotion_scoring_rules.yaml
              │
              └─ 必須依存 ─→ ┌─────────────────────────────────────┐
                             │   upload_opensmile_summary.py       │
                             │     アップロードモジュール            │
                             │     (単体実行も可能)                │
                             └─────────────────────────────────────┘

┌─────────────────────────────────────┐
│        example_usage.py             │ ← クライアント使用例
│   (api_server.pyに依存)             │   (独立したファイル)
└─────────────────────────────────────┘
```

### 🔗 **重要**: APIサーバーの動作に必要なファイル

`api_server.py`を実行するためには、以下のファイルが**必須**です：

```python
# api_server.py 内でのインポート
from opensmile_aggregator import OpenSMILEAggregator
from upload_opensmile_summary import OpenSMILESummaryUploader

# opensmile_aggregator.py 内でのインポート  
from emotion_scoring import EmotionScorer

# emotion_scoring.py 内での読み込み
emotion_scoring_rules.yaml
```

⚠️ **これらのファイルがないとAPIサーバーは起動できません**

## 📞 サポート

**API仕様の詳細:**
- OpenAPI/Swagger UI: `http://localhost:8012/docs`
- ReDoc: `http://localhost:8012/redoc`

**Supabaseデータ確認:**
```sql
-- 保存されたデータを確認
SELECT device_id, date, 
       jsonb_array_length(emotion_graph) as slot_count,
       created_at
FROM emotion_opensmile_summary
ORDER BY created_at DESC;

-- 特定のデータを詳細確認
SELECT emotion_graph->0 as first_slot,
       emotion_graph->23 as noon_slot,
       emotion_graph->47 as last_slot
FROM emotion_opensmile_summary
WHERE device_id = 'your_device_id' AND date = '2025-07-09';
```

**開発者向けサポート:**
- 非同期処理の実装ガイド
- エラーハンドリングベストプラクティス  
- 感情スコアリングルール調整方法
- パフォーマンス最適化手法

## 📝 変更履歴

### v5.0.0 (2025-10-26) - Kushinada v2 4感情対応
- **感情数変更**: 8感情 → 4感情（neutral, joy, anger, sadness）
- **マッピングロジック削除**: 複雑な8感情へのマッピングを完全削除
- **データ型変更**: int（ポイント制） → float（0.0-1.0の確率値）
- **処理シンプル化**: AIモデルの出力をそのまま使用
- **パフォーマンス向上**: 不要な変換処理を削除
- **iOS連携強化**: iOSアプリで4感情を直接表示可能
- **emotion_scoring.py更新**: 4感情専用に書き換え
- **opensmile_aggregator.py更新**: Kushinada v2データ形式に対応
- **後方互換性**: テーブル構造は維持（emotion_opensmile_summary）

### v4.0.0 (2025-07-15) - Docker化とHTTPSエンドポイント
- **Docker化完全移行**: Python venv + systemd → Docker + systemd
- **HTTPSエンドポイント**: https://api.hey-watch.me/emotion-aggregator/ でアクセス可能
- **Dockerイメージ**: watchme-opensmile-aggregator:latest
- **systemdサービス更新**: Dockerコンテナの自動起動・監視に対応
- **Nginxリバースプロキシ**: `/emotion-aggregator/` エンドポイントを追加
- **CORS対応**: 外部アプリケーションからのAPIコール対応
- **動作確認完了**: device_id `d067d407-cf73-4174-a9c1-d91fb60d64d0` での2025-07-15データ処理成功（2スロット、13感情ポイント）

### v3.0.0 (2025-07-10)
- **入出力完全移行**: 入力と出力を全てSupabaseに移行
- **入力ソース**: Supabase emotion_opensmileテーブル
- **出力先**: Supabase emotion_opensmile_summaryテーブル（ワイド型）
- **テーブル構造統一**: 他のグラフDBと同じワイド型構造に変更
- **ローカルファイル不要**: ローカル保存処理を完全削除
- **Vaultアップロード削除**: upload_opensmile_summary.pyを削除
- **パフォーマンス向上**: DBベースのデータ処理に統一
- **データ形式統一**: emotion_graphをJSONB型で48スロット配列として保存

### v2.0.0 (2025-07-05)
- **デバイスベース識別に変更**: `user_id` → `device_id` への全面移行
- **Whisper APIとの統一**: デバイス識別システムの一貫性確保
- **API仕様更新**: 全エンドポイントでdevice_idパラメータを使用
- **データパス変更**: `/data/data_accounts/{device_id}/{date}/` 構造に更新
- **動作確認完了**: device_id `d067d407-cf73-4174-a9c1-d91fb60d64d0` での実データ処理成功（2025-07-05データ、総感情ポイント50）
- **ドキュメント更新**: README、使用例、curlスクリプト全体の修正完了