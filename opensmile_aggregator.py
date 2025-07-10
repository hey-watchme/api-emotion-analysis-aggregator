#!/usr/bin/env python3
"""
OpenSMILE（感情分析）データ集計ツール

Supabaseのemotion_opensmileテーブルからOpenSMILE特徴量データを収集し、
eGeMapsベースの感情スコアリングで日次集計結果をSupabaseのemotion_opensmile_summaryテーブルに保存する。
30分スロット単位で最大48個のデータを非同期処理で取得・解析する。
"""

import asyncio
import json
from typing import Dict, List, Optional
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
    
    def _convert_supabase_to_opensmile_format(self, supabase_data: Dict) -> Optional[Dict]:
        """
        Supabaseのデータ形式をOpenSMILEの従来の形式に変換
        features_timelineから各秒のデータを抽出してOpenSMILE形式に変換
        """
        if not supabase_data or not supabase_data.get('features_timeline'):
            return None
        
        # features_timelineから全特徴量を集計
        features_timeline = supabase_data['features_timeline']
        if not features_timeline:
            return None
        
        # 各秒のデータを処理して平均値を計算
        feature_sums = {}
        feature_counts = {}
        
        for timestamp_data in features_timeline:
            if 'features' in timestamp_data:
                for feature_name, feature_value in timestamp_data['features'].items():
                    if feature_name not in feature_sums:
                        feature_sums[feature_name] = 0
                        feature_counts[feature_name] = 0
                    
                    feature_sums[feature_name] += feature_value
                    feature_counts[feature_name] += 1
        
        # 平均値を計算
        aggregated_features = {}
        for feature_name, total in feature_sums.items():
            if feature_counts[feature_name] > 0:
                aggregated_features[feature_name] = total / feature_counts[feature_name]
        
        # OpenSMILE形式のデータ構造を作成
        return {
            "features": aggregated_features,
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
                    # OpenSMILE形式に変換
                    opensmile_data = self._convert_supabase_to_opensmile_format(data)
                    if opensmile_data:
                        results[slot] = opensmile_data
                        print(f"取得完了: {slot}")
        else:
            # 一括取得したデータを処理
            for data in all_data:
                time_block = data.get('time_block')
                if time_block:
                    # OpenSMILE形式に変換
                    opensmile_data = self._convert_supabase_to_opensmile_format(data)
                    if opensmile_data:
                        results[time_block] = opensmile_data
                        print(f"取得完了: {time_block}")
        
        print(f"データ取得完了: {len(results)}/{len(self.time_slots)} スロット")
        return results
    
    def process_emotion_scores(self, slot_data: Dict[str, Dict]) -> Dict[str, Dict[str, int]]:
        """OpenSMILEデータから感情スコアを計算"""
        print("感情スコア処理開始...")
        
        slot_scores = {}
        total_emotions = 0
        
        for slot, opensmile_data in slot_data.items():
            try:
                # OpenSMILEデータから感情スコアを計算
                emotion_scores = self.emotion_scorer.process_opensmile_data(opensmile_data)
                slot_scores[slot] = emotion_scores
                
                # 統計情報
                total_score = sum(emotion_scores.values())
                total_emotions += total_score
                print(f"スロット {slot}: 感情スコア合計 {total_score}")
                
            except Exception as e:
                print(f"❌ スロット {slot} の感情分析エラー: {e}")
                # エラー時は全て0
                slot_scores[slot] = {emotion: 0 for emotion in self.emotion_scorer.emotions}
        
        print(f"感情スコア処理完了: 総感情ポイント数 {total_emotions}")
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
    
    async def run(self, device_id: str, date: str) -> bool:
        """メイン処理実行"""
        print(f"OpenSMILE感情分析集計処理開始: {device_id}, {date}")
        
        # データ取得
        slot_data = await self.fetch_all_data(device_id, date)
        
        if not slot_data:
            print("取得できたデータがありません")
            return False
        
        # 感情スコア計算
        slot_scores = self.process_emotion_scores(slot_data)
        
        # 1日分のグラフデータ生成
        result = self.emotion_scorer.generate_full_day_data(slot_scores, date)
        
        # 結果をSupabaseに保存
        success = await self.save_result_to_supabase(result, device_id, date)
        
        if success:
            print("OpenSMILE感情分析集計処理完了")
        else:
            print("OpenSMILE感情分析集計処理失敗")
        
        return success


async def main():
    """コマンドライン実行用メイン関数"""
    parser = argparse.ArgumentParser(description="OpenSMILE感情分析データ集計ツール")
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