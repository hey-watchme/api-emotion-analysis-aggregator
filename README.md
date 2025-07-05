# OpenSMILE感情分析API システム - 完全仕様書

OpenSMILE特徴量データの収集・感情スコア集計・アップロードを行うFastAPIベースのREST APIサービスです。

## 📋 コードベース調査結果

### 🔍 システム構成分析
**調査日**: 2025-06-30  
**ファイル数**: 7個  
**コード行数**: 約1,500行  
**言語**: Python 3.11.8+  
**フレームワーク**: FastAPI + aiohttp + PyYAML

### ✅ 動作検証結果
**検証日**: 2025-06-30  
**検証データ**: device123/2025-06-30  
**結果**: 正常動作確認済み

- ✅ API server 起動成功（ポート8012）
- ✅ OpenSMILE データ収集成功（48スロット処理）
- ✅ 感情分析エンジン動作確認（8感情分類）
- ✅ 結果ファイル生成成功（総感情ポイント: 5）
- ✅ Vault API アップロード成功

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

4. **Vault API統合**
   - OpenSMILE専用データ取得: `https://api.hey-watch.me/download-opensmile`
   - Vault APIへのアップロード: `https://api.hey-watch.me/upload/analysis/opensmile-summary`
   - SSL証明書検証無効化対応

#### 📁 **ファイル別機能分析**

**api_server.py:240行** - メインAPIサーバー
- FastAPIアプリケーション（ポート8012）
- 5つのエンドポイント提供
- UUIDベースのタスク管理
- エラーハンドリング付きバックグラウンド処理

**opensmile_aggregator.py:280行** - データ集約エンジン
- Vault APIからの並列HTTP処理（最大30並列接続）
- OpenSMILE特徴量抽出・解析
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
```

**処理能力**
- 同時並列処理: 最大48並列HTTP接続
- タイムアウト設定: 30秒/リクエスト
- SSL証明書検証: 環境変数制御可能
- メモリ効率: ストリーミング処理対応

**データ処理フロー**
1. Vault APIからの並列取得 → 2. JSON解析 → 3. 特徴量抽出 → 4. 感情スコアリング → 5. グラフデータ生成 → 6. ローカル保存 → 7. Vault APIへアップロード

## ⚠️ 重要: ファイル依存関係
**APIサーバー（`api_server.py`）を動作させるには、以下のファイルが必須です：**
- 📁 `api_server.py` - メインAPIサーバー
- 📁 `opensmile_aggregator.py` - データ処理モジュール (**必須依存**)
- 📁 `upload_opensmile_summary.py` - アップロードモジュール (**必須依存**)
- 📁 `emotion_scoring.py` - 感情スコアリングエンジン (**必須依存**)
- 📁 `emotion_scoring_rules.yaml` - 感情ルール定義ファイル (**必須依存**)

## 🎯 システム概要

**🌐 REST API**: FastAPIベースの非同期APIサーバー  
**📥 データ収集**: Vault API上のOpenSMILEファイル（最大48個の30分スロット）を非同期並列取得  
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
- OpenSMILE専用Vault API `https://api.hey-watch.me/download-opensmile` へのHTTPS接続
- 30分スロット×48個の並列リクエスト対応

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

### 2️⃣ ファイル構成の確認
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

### 3️⃣ APIサーバー起動
```bash
# 開発環境（推奨）
python api_server.py

# または
uvicorn api_server:app --reload --host 0.0.0.0 --port 8012

# 本番環境
uvicorn api_server:app --host 0.0.0.0 --port 8012 --workers 4
```

APIサーバーは `http://localhost:8012` で起動します。

### 4️⃣ 接続確認
```bash
curl http://localhost:8012/health
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

### 🎭 **8感情分類**
1. **anger** - 怒り
2. **fear** - 恐れ
3. **anticipation** - 期待・予期
4. **surprise** - 驚き
5. **joy** - 喜び
6. **sadness** - 悲しみ
7. **trust** - 信頼・安心
8. **disgust** - 嫌悪・不快

### 🔧 **スコアリングロジック**
- **ルールベース**: YAMLファイルで定義されたしきい値比較
- **ポイント制**: 1ルール満足 = 1ポイント加算
- **スロット集計**: 30分スロット内でポイント合算
- **ニュートラル**: 全感情0ポイントの場合

### 📐 **特徴量例**
```yaml
anger:
  - feature: Loudness_sma3            # 声量が高い
    op: ">"
    th: 0.30
  - feature: shimmerLocaldB_sma3nz    # 振幅ゆらぎが大きい
    op: ">"
    th: 0.40

joy:
  - feature: Loudness_sma3
    op: ">"
    th: 0.20
  - feature: HNRdBACF_sma3nz          # ハーモニクス優勢
    op: ">"
    th: 2.0
```

## 📊 データフォーマット

### 感情分析結果

**出力ファイルパス:**
```
/Users/kaya.matsumoto/data/data_accounts/{device_id}/{YYYY-MM-DD}/opensmile-summary/result.json
```

**JSON構造:**
```json
{
  "date": "2025-06-26",
  "emotion_graph": [
    {"time": "00:00", "anger": 0, "fear": 0, "anticipation": 0, "surprise": 0, "joy": 0, "sadness": 0, "trust": 0, "disgust": 0},
    {"time": "00:30", "anger": 0, "fear": 0, "anticipation": 0, "surprise": 0, "joy": 0, "sadness": 0, "trust": 0, "disgust": 0},
    {"time": "04:30", "anger": 4, "fear": 1, "anticipation": 2, "surprise": 1, "joy": 1, "sadness": 1, "trust": 1, "disgust": 1},
    {"time": "07:00", "anger": 0, "fear": 0, "anticipation": 2, "surprise": 1, "joy": 8, "sadness": 0, "trust": 4, "disgust": 0},
    {"time": "12:00", "anger": 6, "fear": 1, "anticipation": 2, "surprise": 1, "joy": 1, "sadness": 2, "trust": 1, "disgust": 1},
    {"time": "23:30", "anger": 0, "fear": 0, "anticipation": 0, "surprise": 0, "joy": 0, "sadness": 0, "trust": 0, "disgust": 0}
  ]
}
```

### eGeMAPS特徴量タイプ

**主要な特徴量例:**
- **Loudness_sma3**: 音声の大きさ・音圧レベル
- **F0semitoneFrom27.5Hz_sma3nz**: 基本周波数（ピッチ）
- **jitterLocal_sma3nz**: 周期ゆらぎ（声の震え）
- **shimmerLocaldB_sma3nz**: 振幅ゆらぎ（音量の震え）
- **HNRdBACF_sma3nz**: 調波雑音比（声の清澄度）
- **spectralFlux_sma3**: スペクトル変化量（音色変化）
- **mfcc1_sma3, mfcc2_sma3**: メル周波数ケプストラム係数
- **alphaRatio_sma3**: 高域エネルギー比
- **HammarbergIndex_sma3**: 高域ピーク指標
- **slope500-1500_sma3**: 周波数スロープ

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

**開発者向けサポート:**
- 非同期処理の実装ガイド
- エラーハンドリングベストプラクティス  
- 感情スコアリングルール調整方法
- パフォーマンス最適化手法

## 📝 変更履歴

### v2.0.0 (2025-07-05)
- **デバイスベース識別に変更**: `user_id` → `device_id` への全面移行
- **Whisper APIとの統一**: デバイス識別システムの一貫性確保
- **API仕様更新**: 全エンドポイントでdevice_idパラメータを使用
- **データパス変更**: `/data/data_accounts/{device_id}/{date}/` 構造に更新
- **動作確認完了**: device_id `d067d407-cf73-4174-a9c1-d91fb60d64d0` での実データ処理成功（2025-07-05データ、総感情ポイント50）
- **ドキュメント更新**: README、使用例、curlスクリプト全体の修正完了