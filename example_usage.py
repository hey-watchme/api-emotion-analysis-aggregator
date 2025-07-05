#!/usr/bin/env python3
"""
OpenSMILE感情分析API クライアント使用例

APIサーバーを使用してOpenSMILE感情分析を実行する方法を示します。
"""

import asyncio
import aiohttp
import json
from datetime import datetime


class OpenSMILEAnalysisClient:
    """OpenSMILE感情分析APIクライアント"""
    
    def __init__(self, base_url: str = "http://localhost:8012"):
        self.base_url = base_url
    
    async def start_analysis(self, device_id: str, date: str) -> str:
        """感情分析を開始してタスクIDを取得"""
        url = f"{self.base_url}/analyze/opensmile-aggregator"
        data = {"device_id": device_id, "date": date}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["task_id"]
                else:
                    error = await response.text()
                    raise Exception(f"感情分析開始エラー: {error}")
    
    async def get_status(self, task_id: str) -> dict:
        """タスク状況を取得"""
        url = f"{self.base_url}/analyze/opensmile-aggregator/{task_id}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error = await response.text()
                    raise Exception(f"状況取得エラー: {error}")
    
    async def wait_for_completion(self, task_id: str, max_wait: int = 600) -> dict:
        """感情分析完了まで待機"""
        print(f"⏳ 感情分析完了を待機中... (最大{max_wait}秒)")
        
        for i in range(max_wait):
            status = await self.get_status(task_id)
            
            print(f"🎭 進捗: {status['progress']}% - {status['message']}")
            
            if status['status'] == 'completed':
                print("✅ 感情分析完了!")
                return status
            elif status['status'] == 'failed':
                print(f"❌ 感情分析失敗: {status.get('error', '不明なエラー')}")
                return status
            
            await asyncio.sleep(1)
        
        raise Exception("タイムアウト: 感情分析が時間内に完了しませんでした")


async def example_api_usage():
    """API使用例の実行"""
    print("OpenSMILE感情分析API クライアント使用例")
    print("=" * 60)
    
    client = OpenSMILEAnalysisClient()
    
    # 実行パラメータ
    device_id = "device123"
    date = "2025-06-26"  # 実際の日付に変更してください
    
    print(f"📋 感情分析パラメータ:")
    print(f"  デバイスID: {device_id}")
    print(f"  対象日付: {date}")
    print()
    
    try:
        # 1. 感情分析開始
        print("🚀 感情分析開始...")
        task_id = await client.start_analysis(device_id, date)
        print(f"   タスクID: {task_id}")
        
        # 2. 完了まで待機
        result = await client.wait_for_completion(task_id)
        
        # 3. 結果表示
        if result['status'] == 'completed' and 'result' in result:
            analysis_data = result['result']['analysis']
            upload_data = result['result']['upload']
            
            print("\n📊 感情分析結果:")
            print(f"  📁 出力ファイル: {result['result']['output_path']}")
            print(f"  🎭 総感情ポイント数: {result['result']['total_emotion_points']}")
            print(f"  📈 グラフデータ点数: {result['result']['emotion_graph_length']}")
            print(f"  ☁️ アップロード: 成功 {upload_data['success']}, 失敗 {upload_data['failed']}")
            
            # 感情グラフサンプル表示
            emotion_graph = analysis_data.get('emotion_graph', [])
            if emotion_graph:
                print("\n🎭 感情グラフサンプル（最初の5スロット）:")
                for i, slot_data in enumerate(emotion_graph[:5]):
                    emotions = []
                    for emotion in ["anger", "fear", "anticipation", "surprise", "joy", "sadness", "trust", "disgust"]:
                        score = slot_data.get(emotion, 0)
                        if score > 0:
                            emotions.append(f"{emotion}:{score}")
                    
                    emotion_str = ", ".join(emotions) if emotions else "ニュートラル"
                    print(f"  {slot_data['time']}: {emotion_str}")
                
                # 感情統計
                print("\n📈 感情統計（全スロット合計）:")
                emotion_totals = {}
                for slot_data in emotion_graph:
                    for emotion in ["anger", "fear", "anticipation", "surprise", "joy", "sadness", "trust", "disgust"]:
                        emotion_totals[emotion] = emotion_totals.get(emotion, 0) + slot_data.get(emotion, 0)
                
                sorted_emotions = sorted(emotion_totals.items(), key=lambda x: x[1], reverse=True)
                for emotion, total in sorted_emotions[:5]:
                    print(f"  {emotion}: {total}ポイント")
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")


async def example_health_check():
    """ヘルスチェック例"""
    print("\n🔍 APIヘルスチェック")
    print("-" * 40)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8012/health") as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ API稼働中: {result}")
                else:
                    print(f"❌ APIエラー: HTTP {response.status}")
    except Exception as e:
        print(f"❌ 接続エラー: {e}")
        print("💡 api_server.pyを起動してください")


async def example_emotion_scoring_test():
    """感情スコアリング機能のテスト"""
    print("\n🎭 感情スコアリング機能テスト")
    print("-" * 40)
    
    try:
        from emotion_scoring import EmotionScorer
        
        scorer = EmotionScorer()
        
        # サンプル特徴量（怒りを想定）
        anger_features = {
            "Loudness_sma3": 0.35,          # 声量が高い
            "shimmerLocaldB_sma3nz": 0.45,  # 振幅ゆらぎが大きい
            "HNRdBACF_sma3nz": 0.8,         # 雑音が多い
            "logRelF0-H1-A3_sma3nz": 12.0   # スペクトル鋭さ
        }
        
        anger_scores = scorer.score_features(anger_features)
        print(f"怒り特徴量のスコア: {anger_scores}")
        
        # サンプル特徴量（喜びを想定）
        joy_features = {
            "Loudness_sma3": 0.25,          # 適度な声量
            "HNRdBACF_sma3nz": 2.5,         # ハーモニクス優勢
            "mfcc1_sma3": 25.0,             # 明瞭な音声
            "logRelF0-H1-A3_sma3nz": 8.0    # スペクトル鋭さ適度
        }
        
        joy_scores = scorer.score_features(joy_features)
        print(f"喜び特徴量のスコア: {joy_scores}")
        
        print("\n✅ 感情スコアリング機能は正常に動作しています")
        
    except ImportError as e:
        print(f"❌ インポートエラー: {e}")
        print("💡 emotion_scoring.pyファイルを確認してください")
    except Exception as e:
        print(f"❌ 感情スコアリングエラー: {e}")


if __name__ == "__main__":
    asyncio.run(example_health_check())
    asyncio.run(example_emotion_scoring_test())
    asyncio.run(example_api_usage())