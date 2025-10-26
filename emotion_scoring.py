#!/usr/bin/env python3
"""
感情スコアリングエンジン (Kushinada v2対応版)

Kushinada v2の感情分類結果（4感情: neutral, joy, anger, sadness）をそのまま出力。
"""

import yaml
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


class EmotionScorer:
    """感情スコアリングクラス"""

    def __init__(self, rules_path: str = "emotion_scoring_rules.yaml"):
        self.rules_path = rules_path
        self.rules = self._load_rules()
        # Kushinada v2の4感情
        self.emotions = ["neutral", "joy", "anger", "sadness"]
    
    def _load_rules(self) -> Dict[str, Any]:
        """YAMLルールファイルを読み込み"""
        try:
            with open(self.rules_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"⚠️ ルールファイルが見つかりません: {self.rules_path}")
            return {"emotions": {}}
        except yaml.YAMLError as e:
            print(f"⚠️ YAMLパースエラー: {e}")
            return {"emotions": {}}
    
    def _evaluate_rule(self, features: Dict[str, float], rule: Dict[str, Any]) -> bool:
        """単一ルールの評価"""
        feature_name = rule.get('feature')
        if not feature_name or feature_name not in features:
            return False
        
        value = features[feature_name]
        op = rule.get('op')
        th = rule.get('th')
        
        if op is None or th is None:
            return False
        
        # 基本比較
        if op == ">" and value <= th:
            return False
        elif op == "<" and value >= th:
            return False
        elif op == "==" and value != th:
            return False
        
        # 範囲チェック（op2, th2がある場合）
        op2 = rule.get('op2')
        th2 = rule.get('th2')
        if op2 and th2 is not None:
            if op2 == ">" and value <= th2:
                return False
            elif op2 == "<" and value >= th2:
                return False
            elif op2 == "==" and value != th2:
                return False
        
        return True
    
    def score_features(self, features: Dict[str, float]) -> Dict[str, int]:
        """特徴量から感情スコアを計算"""
        scores = {emotion: 0 for emotion in self.emotions}
        
        for emotion in self.emotions:
            emotion_rules = self.rules.get("emotions", {}).get(emotion, [])
            
            for rule in emotion_rules:
                if self._evaluate_rule(features, rule):
                    scores[emotion] += self.rules.get("meta", {}).get("max_points_per_rule", 1)
        
        return scores
    
    def process_opensmile_data(self, opensmile_data: Dict[str, Any]) -> Dict[str, int]:
        """OpenSMILEのJSONデータから感情スコアを抽出（後方互換性用）"""
        # OpenSMILEのJSON構造に応じて特徴量を抽出
        # 通常は "features" や "data" キーの下にある
        features = {}
        
        # データ構造を探索してeGeMAPS特徴量を抽出
        def extract_features(obj, prefix=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, (int, float)):
                        # eGeMAPS特徴量名にマッチする場合
                        if any(pattern in key for pattern in [
                            "Loudness_sma3", "shimmerLocaldB_sma3nz", "HNRdBACF_sma3nz",
                            "jitterLocal_sma3nz", "F0semitoneFrom27.5Hz_sma3nz", 
                            "spectralFlux_sma3", "mfcc", "alphaRatio_sma3",
                            "HammarbergIndex_sma3", "logRelF0", "slope500-1500_sma3"
                        ]):
                            features[key] = float(value)
                    elif isinstance(value, (dict, list)):
                        extract_features(value, f"{prefix}{key}_")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    extract_features(item, f"{prefix}{i}_")
        
        extract_features(opensmile_data)
        
        # 特徴量が見つからない場合の処理
        if not features:
            print(f"⚠️ eGeMAPS特徴量が見つかりません。利用可能なキー: {list(opensmile_data.keys())}")
            return {emotion: 0 for emotion in self.emotions}
        
        return self.score_features(features)
    
    def process_kushinada_v2_data(self, emotion_data: Dict[str, Any]) -> Dict[str, float]:
        """Kushinada v2の感情分類結果（4感情）をそのまま返す"""
        # 初期化
        scores = {emotion: 0.0 for emotion in self.emotions}

        # Kushinada v2の感情スコアを取得
        kushinada_scores = emotion_data.get('emotion_scores', {})

        if not kushinada_scores:
            print(f"⚠️ Kushinada v2感情スコアが見つかりません")
            return scores

        # 内部ラベル（ang, sad, neu, hap）をKushinada v2ラベルにマッピング
        label_mapping = {
            'ang': 'anger',
            'sad': 'sadness',
            'neu': 'neutral',
            'hap': 'joy'
        }

        # スコアをそのまま（0.0-1.0の範囲で）設定
        for internal_label, score_value in kushinada_scores.items():
            v2_label = label_mapping.get(internal_label)
            if v2_label and v2_label in scores:
                scores[v2_label] = float(score_value)

        return scores
    
    def create_time_slot_data(self, time_slot: str, emotion_scores: Dict[str, float]) -> Dict[str, Any]:
        """時間スロット用のデータ構造を作成"""
        return {
            "time": f"{time_slot[:2]}:{time_slot[3:]}",  # "00-00" -> "00:00"
            **emotion_scores
        }

    def generate_full_day_data(self, slot_scores: Dict[str, Dict[str, float]], date: str) -> Dict[str, Any]:
        """1日分の感情グラフデータを生成（48スロット、4感情）"""
        time_slots = []
        for hour in range(24):
            for minute in [0, 30]:
                time_slots.append(f"{hour:02d}-{minute:02d}")
        
        emotion_graph = []
        for slot in time_slots:
            if slot in slot_scores:
                # データがある場合
                emotion_data = self.create_time_slot_data(slot, slot_scores[slot])
            else:
                # データがない場合は全て0.0
                emotion_data = self.create_time_slot_data(slot, {emotion: 0.0 for emotion in self.emotions})

            emotion_graph.append(emotion_data)

        return {
            "date": date,
            "emotion_graph": emotion_graph
        }


def main():
    """テスト用メイン関数"""
    scorer = EmotionScorer()

    # 1日分のデータ生成テスト（4感情）
    slot_scores = {
        "04-30": {"neutral": 0.1, "joy": 0.2, "anger": 0.5, "sadness": 0.2},
        "07-00": {"neutral": 0.2, "joy": 0.7, "anger": 0.05, "sadness": 0.05}
    }

    full_day = scorer.generate_full_day_data(slot_scores, "2025-06-26")
    print(f"1日分データ: {len(full_day['emotion_graph'])} スロット")
    print(f"サンプル: {full_day['emotion_graph'][0]}")


if __name__ == "__main__":
    main()