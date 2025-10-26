#!/usr/bin/env python3
"""
感情分析データ集計ツール (Kushinada v2対応版)

Supabaseのemotion_opensmileテーブルからKushinada v2による感情分類データを収集し、
日次集計結果をSupabaseのemotion_opensmile_summaryテーブルに保存する。
30分スロット単位で最大48個のデータを非同期処理で取得・解析する。

Kushinada v2の感情ラベル: neutral, joy, anger, sadness (4種類)
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import argparse

from emotion_scoring import EmotionScorer
from supabase_service import SupabaseService


class OpenSMILEAggregator:
    """OpenSMILE データ集計クラス"""
    
    def __init__(self):
        self.time_slots = self._generate_time_slots()
        self.emotion_scorer = EmotionScorer()
        self.supabase_service = SupabaseService()
    
    def _generate_time_slots(self) -> List[str]:
        """30分スロットのリストを生成（00-00 から 23-30 まで）"""
        slots = []
        for hour in range(24):
            for minute in [0, 30]:
                slots.append(f"{hour:02d}-{minute:02d}")
        return slots
    
    def _convert_kushinada_v2_to_emotion_format(self, supabase_data: Dict) -> Optional[Dict]:
        """
        Kushinada v2の感情分類結果を処理用の形式に変換
        features_timelineから感情スコアを抽出（4感情: neutral, joy, anger, sadness）
        """
        if not supabase_data or not supabase_data.get('features_timeline'):
            return None
        
        features_timeline = supabase_data['features_timeline']
        if not features_timeline:
            return None
        
        # Kushinada v2の感情分類結果を集計（4感情）
        # 各チャンク（10秒単位）の感情スコアを平均化
        # ラベルマッピング: neutral, joy, anger, sadness
        emotion_scores = {
            'ang': 0.0,  # 怒り (anger)
            'sad': 0.0,  # 悲しみ (sadness)
            'neu': 0.0,  # 中立 (neutral)
            'hap': 0.0   # 喜び (joy)
        }

        # v2のラベル名を旧形式にマッピング
        label_mapping = {
            'anger': 'ang',
            'sadness': 'sad',
            'neutral': 'neu',
            'joy': 'hap'
        }

        chunk_count = 0

        for chunk_data in features_timeline:
            if 'emotions' in chunk_data:
                chunk_count += 1
                for emotion in chunk_data['emotions']:
                    label = emotion.get('label')
                    score = emotion.get('score', 0.0)
                    # v2のラベル名を旧形式に変換
                    mapped_label = label_mapping.get(label, label)
                    if mapped_label in emotion_scores:
                        emotion_scores[mapped_label] += score
        
        # 平均値を計算
        if chunk_count > 0:
            for label in emotion_scores:
                emotion_scores[label] = emotion_scores[label] / chunk_count
        
        return {
            "emotion_scores": emotion_scores,
            "metadata": {
                "device_id": supabase_data.get('device_id'),
                "date": supabase_data.get('date'),
                "time_block": supabase_data.get('time_block'),
                "duration_seconds": supabase_data.get('duration_seconds', 0),
                "filename": supabase_data.get('filename', '')
            }
        }
    
    async def fetch_all_data(self, device_id: str, date: str) -> Dict[str, Dict]:
        """指定日の全OpenSMILEデータをSupabaseから取得"""
        print(f"データ取得開始: device_id={device_id}, date={date}")
        
        results = {}
        
        # Supabaseから一日分のデータを一括取得
        all_data = await self.supabase_service.fetch_all_opensmile_data_for_day(device_id, date)
        
        if not all_data:
            print("Supabaseにデータが見つかりません")
            # 個別にスロットごとに取得を試みる
            for slot in self.time_slots:
                print(f"🔍 スロット {slot} のデータ取得中...")
                data = await self.supabase_service.fetch_opensmile_data(device_id, date, slot)
                if data:
                    # Kushinada v2形式に変換
                    emotion_data = self._convert_kushinada_v2_to_emotion_format(data)
                    if emotion_data:
                        results[slot] = emotion_data
                        print(f"取得完了: {slot}")
        else:
            # 一括取得したデータを処理
            for data in all_data:
                time_block = data.get('time_block')
                if time_block:
                    # Kushinada v2形式に変換
                    emotion_data = self._convert_kushinada_v2_to_emotion_format(data)
                    if emotion_data:
                        results[time_block] = emotion_data
                        print(f"取得完了: {time_block}")
        
        print(f"データ取得完了: {len(results)}/{len(self.time_slots)} スロット")
        return results
    
    def process_emotion_scores(self, slot_data: Dict[str, Dict]) -> Dict[str, Dict[str, float]]:
        """Kushinada v2の感情分類結果（4感情）をそのまま処理"""
        print("感情スコア処理開始...")

        slot_scores = {}

        for slot, emotion_data in slot_data.items():
            try:
                # Kushinada v2の感情スコア（4感情）をそのまま取得
                emotion_scores = self.emotion_scorer.process_kushinada_v2_data(emotion_data)
                slot_scores[slot] = emotion_scores

                # 統計情報
                max_emotion = max(emotion_scores, key=emotion_scores.get)
                max_score = emotion_scores[max_emotion]
                print(f"スロット {slot}: 主要感情={max_emotion} ({max_score:.3f})")

            except Exception as e:
                print(f"❌ スロット {slot} の感情分析エラー: {e}")
                # エラー時は全て0.0
                slot_scores[slot] = {emotion: 0.0 for emotion in self.emotion_scorer.emotions}

        print(f"感情スコア処理完了: {len(slot_scores)} スロット処理")
        return slot_scores
    
    async def save_result_to_supabase(self, result: Dict, device_id: str, date: str) -> bool:
        """結果をSupabaseのemotion_opensmile_summaryテーブルに保存"""
        emotion_graph = result.get("emotion_graph", [])
        success = await self.supabase_service.save_emotion_summary(device_id, date, emotion_graph)
        
        if success:
            print(f"結果保存完了: Supabase emotion_opensmile_summary")
        else:
            print(f"結果保存失敗")
        
        return success
    
    async def run(self, device_id: str, date: str) -> Dict[str, Any]:
        """メイン処理実行"""
        print(f"感情分析集計処理開始 (Kushinada v2): {device_id}, {date}")
        
        # データ取得
        slot_data = await self.fetch_all_data(device_id, date)
        
        if not slot_data:
            print(f"指定された日付（{date}）にはデータが存在しません")
            # データがない場合でも、空のデータを保存（全スロット0）
            empty_scores = {}
            result = self.emotion_scorer.generate_full_day_data(empty_scores, date)
            success = await self.save_result_to_supabase(result, device_id, date)
            return {
                "success": success,
                "has_data": False,
                "message": f"指定された日付（{date}）にはデータが存在しません。空のデータを保存しました。",
                "processed_slots": 0,
                "total_emotion_points": 0
            }
        
        # 感情スコア計算
        slot_scores = self.process_emotion_scores(slot_data)
        
        # 1日分のグラフデータ生成
        result = self.emotion_scorer.generate_full_day_data(slot_scores, date)
        
        # 結果をSupabaseに保存
        success = await self.save_result_to_supabase(result, device_id, date)

        if success:
            print("感情分析集計処理完了")
        else:
            print("感情分析集計処理失敗")

        return {
            "success": success,
            "has_data": True,
            "message": f"感情分析が完了しました（4感情: neutral, joy, anger, sadness）",
            "processed_slots": len(slot_data),
            "total_emotion_points": len(slot_data)  # 処理したスロット数を返す
        }


async def main():
    """コマンドライン実行用メイン関数"""
    parser = argparse.ArgumentParser(description="感情分析データ集計ツール (Kushinada v2版)")
    parser.add_argument("device_id", help="デバイスID（例: device123）")
    parser.add_argument("date", help="対象日付（YYYY-MM-DD形式）")
    
    args = parser.parse_args()
    
    # 日付形式検証
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print("エラー: 日付はYYYY-MM-DD形式で指定してください")
        return
    
    # 集計実行
    aggregator = OpenSMILEAggregator()
    success = await aggregator.run(args.device_id, args.date)
    
    if success:
        print(f"\n✅ 処理完了")
        print(f"結果: Supabase emotion_opensmile_summaryテーブルに保存")
    else:
        print("\n❌ 処理失敗")


if __name__ == "__main__":
    asyncio.run(main())