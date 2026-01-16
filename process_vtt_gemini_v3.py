#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VTTファイルをGemini APIで高精度校正してSRTに変換するスクリプト (v3)

改善点:
- gemini-2.5-pro モデル使用（より高精度）
- チャンクサイズ100（より丁寧な処理）
- 2パス処理（1回目:基本校正、2回目:専門用語チェック）
- 前後文脈を含めた処理
- Few-shot例をプロンプトに追加
- 誤字パターンを外部JSONで管理
- 後処理で辞書置換

使い方: python3 process_vtt_gemini_v3.py <vttファイルのパス>
環境変数: GEMINI_API_KEY にAPIキーを設定
"""

import os
import sys
import re
import json
import time
from datetime import datetime
from pathlib import Path
import shutil

# OpenAI SDKをインポート
try:
    from openai import OpenAI
except ImportError:
    print("\nエラー: openai パッケージがインストールされていません。")
    print("以下のコマンドでインストールしてください:")
    print("  pip install openai")
    sys.exit(1)


# 設定
CONFIG = {
    "model": "gemini-2.5-pro",  # より高精度なモデル
    "chunk_size": 100,          # より小さなチャンクで丁寧に処理
    "context_window": 3,        # 前後3エントリを文脈として含める
    "sleep_between_chunks": 1,  # チャンク間の待機秒数
    "enable_two_pass": True,    # 2パス処理を有効化
}


def load_correction_patterns():
    """誤字パターンをJSONファイルから読み込む"""
    patterns_file = Path(__file__).parent / "correction_patterns.json"
    if patterns_file.exists():
        with open(patterns_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        print("  [WARN] correction_patterns.json が見つかりません")
        return {"simple_patterns": {}, "filler_words": [], "dental_terms": {"terms": []}}


def read_vtt_file(vtt_path):
    """VTTファイルを読み込んでエントリのリストを返す"""
    print(f"  [LOG] ファイル読み込み: {vtt_path.name}")
    with open(vtt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = r'(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3}).*?\n((?:.*(?:\n|$))+?)(?=\n\d{2}:\d{2}:\d{2}\.\d{3}|$)'
    matches = re.findall(pattern, content, re.MULTILINE)

    entries = []
    for i, (start, end, text) in enumerate(matches, 1):
        text = text.strip()
        if text:
            entries.append({
                'index': i,
                'start': start,
                'end': end,
                'text': text
            })

    print(f"  [OK] 総エントリ数: {len(entries)}")
    return entries


def vtt_time_to_srt_time(vtt_time):
    """VTT形式の時間をSRT形式に変換（ピリオド→カンマ）"""
    return vtt_time.replace('.', ',')


def apply_simple_replacements(text, patterns):
    """単純な置換パターンを適用"""
    simple = patterns.get("simple_patterns", {})
    for wrong, correct in simple.items():
        text = text.replace(wrong, correct)
    return text


def build_few_shot_examples():
    """Few-shot例を生成"""
    return """【変換例】
入力: [1] 司会者マッチング店員についてですね
出力: [1] 歯科医師マッチング転院についてですね

入力: [2] えーと、強制治療の補填期間についてなんすけど
出力: [2] 矯正治療の保定期間についてなんですけど

入力: [3] minamidate: 開墾の症例が多いですね
出力: [3] minamidate: 開咬の症例が多いですね

入力: [4] レンズパークで作ったホームページがですね
出力: [4] Gensparkで作ったホームページがですね

入力: [5] 口頭干渉があるので効果調整が必要です
出力: [5] 咬頭干渉があるので咬合調整が必要です"""


def build_prompt_pass1(entries_batch, patterns, context_before="", context_after=""):
    """1パス目のプロンプトを構築（基本校正）"""

    # 誤変換パターンをリスト化
    simple = patterns.get("simple_patterns", {})
    pattern_list = "\n".join([f"- 「{w}」→「{c}」" for w, c in simple.items()])

    # 歯科専門用語リスト
    dental_terms = patterns.get("dental_terms", {}).get("terms", [])
    terms_list = "、".join(dental_terms[:20])  # 最初の20個

    # フィラーリスト
    fillers = patterns.get("filler_words", [])
    filler_list = "、".join(fillers)

    # Few-shot例
    few_shot = build_few_shot_examples()

    # 入力テキスト
    input_lines = [f"[{e['index']}] {e['text']}" for e in entries_batch]
    input_text = '\n'.join(input_lines)

    # 文脈情報
    context_info = ""
    if context_before:
        context_info += f"\n【直前の文脈】\n{context_before}\n"
    if context_after:
        context_info += f"\n【直後の文脈】\n{context_after}\n"

    prompt = f"""あなたは歯科医療・矯正歯科の専門家です。以下は歯科医師による会議の音声認識字幕です。

【最重要：音声認識の誤変換を必ず修正してください】
{pattern_list}

【歯科専門用語（正しい表記）】
{terms_list}

【削除するフィラー】
{filler_list}

{few_shot}
{context_info}
【校正ルール】
1. 上記の誤変換パターンを必ず修正
2. フィラーを除去
3. 口語を自然な日本語に（「なんすか」→「なんですか」）
4. 発話者名（例: minamidate:）は絶対に削除しない
5. 文脈から意味を推測して適切な専門用語に変換

【出力形式】
[番号] 校正後テキスト
※番号は入力と同じ。余計な説明は不要。

【入力データ】
{input_text}

【出力】"""

    return prompt


def build_prompt_pass2(entries_batch, patterns):
    """2パス目のプロンプトを構築（専門用語の再チェック）"""

    dental_terms = patterns.get("dental_terms", {}).get("terms", [])
    terms_list = "\n".join([f"- {t}" for t in dental_terms])

    input_lines = [f"[{e['index']}] {e['text']}" for e in entries_batch]
    input_text = '\n'.join(input_lines)

    prompt = f"""以下は1回目の校正済み字幕です。歯科専門用語が正しく使われているか最終チェックしてください。

【正しい歯科専門用語リスト】
{terms_list}

【チェック項目】
1. 専門用語のスペルミスや誤変換がないか
2. 文脈上おかしな単語がないか
3. 同音異義語が正しく使われているか

【出力形式】
[番号] 最終校正テキスト
※修正不要なら入力をそのまま出力。余計な説明は不要。

【入力データ】
{input_text}

【出力】"""

    return prompt


def parse_ai_response(response_text, original_entries):
    """AIの回答から[番号]形式でテキストを抽出"""
    original_dict = {entry['index']: entry['text'] for entry in original_entries}
    result = {}

    lines = response_text.strip().split('\n')
    for line in lines:
        match = re.match(r'^\[(\d+)\]\s*(.*)', line.strip())
        if match:
            index = int(match.group(1))
            text = match.group(2).strip()
            if text:
                result[index] = text

    # フォールバック
    for entry in original_entries:
        idx = entry['index']
        if idx not in result:
            result[idx] = original_dict[idx]

    return result


def call_gemini_api(client, prompt, pass_num=1):
    """Gemini APIを呼び出し"""
    try:
        response = client.chat.completions.create(
            model=CONFIG["model"],
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"    [ERROR] パス{pass_num} API呼び出しエラー: {e}")
        return None


def get_context_text(entries, start_idx, end_idx, window):
    """前後の文脈テキストを取得"""
    before_start = max(0, start_idx - window)
    after_end = min(len(entries), end_idx + window)

    before_entries = entries[before_start:start_idx]
    after_entries = entries[end_idx:after_end]

    context_before = "\n".join([f"[{e['index']}] {e['text']}" for e in before_entries])
    context_after = "\n".join([f"[{e['index']}] {e['text']}" for e in after_entries])

    return context_before, context_after


def process_entries(entries, client, patterns):
    """エントリを処理（2パス）"""
    chunk_size = CONFIG["chunk_size"]
    context_window = CONFIG["context_window"]
    total_entries = len(entries)
    total_chunks = (total_entries + chunk_size - 1) // chunk_size

    print(f"\n処理開始: 総エントリ数 {total_entries}, チャンクサイズ {chunk_size}")
    print(f"総チャンク数: {total_chunks}")
    print(f"使用モデル: {CONFIG['model']}")
    print(f"2パス処理: {'有効' if CONFIG['enable_two_pass'] else '無効'}")
    print("-" * 50)

    all_corrected = {}

    # === パス1: 基本校正 ===
    print("\n【パス1】基本校正...")
    for chunk_num in range(1, total_chunks + 1):
        start_idx = (chunk_num - 1) * chunk_size
        end_idx = min(start_idx + chunk_size, total_entries)
        chunk_entries = entries[start_idx:end_idx]

        print(f"\n[パス1 チャンク {chunk_num}/{total_chunks}] エントリ {start_idx + 1}-{end_idx}")

        # 前後文脈を取得
        context_before, context_after = get_context_text(entries, start_idx, end_idx, context_window)

        # プロンプト生成
        prompt = build_prompt_pass1(chunk_entries, patterns, context_before, context_after)

        # API呼び出し
        response_text = call_gemini_api(client, prompt, pass_num=1)

        if response_text:
            corrected = parse_ai_response(response_text, chunk_entries)
            all_corrected.update(corrected)
            print(f"  [OK] {len(corrected)} エントリを校正完了")
        else:
            for entry in chunk_entries:
                all_corrected[entry['index']] = entry['text']

        if chunk_num < total_chunks:
            time.sleep(CONFIG["sleep_between_chunks"])

    # === パス2: 専門用語チェック ===
    if CONFIG["enable_two_pass"]:
        print("\n【パス2】専門用語チェック...")

        # パス1の結果をエントリ形式に変換
        pass1_entries = [{'index': idx, 'text': text} for idx, text in sorted(all_corrected.items())]

        for chunk_num in range(1, total_chunks + 1):
            start_idx = (chunk_num - 1) * chunk_size
            end_idx = min(start_idx + chunk_size, len(pass1_entries))
            chunk_entries = pass1_entries[start_idx:end_idx]

            print(f"\n[パス2 チャンク {chunk_num}/{total_chunks}] エントリ {start_idx + 1}-{end_idx}")

            prompt = build_prompt_pass2(chunk_entries, patterns)
            response_text = call_gemini_api(client, prompt, pass_num=2)

            if response_text:
                corrected = parse_ai_response(response_text, chunk_entries)
                all_corrected.update(corrected)
                print(f"  [OK] {len(corrected)} エントリをチェック完了")

            if chunk_num < total_chunks:
                time.sleep(CONFIG["sleep_between_chunks"])

    # === 後処理: 辞書置換 ===
    print("\n【後処理】辞書置換...")
    for idx in all_corrected:
        all_corrected[idx] = apply_simple_replacements(all_corrected[idx], patterns)

    return all_corrected


def write_srt_file(entries, corrected_texts, output_path):
    """校正済みテキストをSRTファイルに書き出し"""
    with open(output_path, 'w', encoding='utf-8') as f:
        for entry in entries:
            idx = entry['index']
            text = corrected_texts.get(idx, entry['text'])

            f.write(f"{idx}\n")
            f.write(f"{vtt_time_to_srt_time(entry['start'])} --> {vtt_time_to_srt_time(entry['end'])}\n")
            f.write(f"{text}\n\n")

    print(f"\n[OK] SRTファイル保存完了: {output_path}")


def main():
    """メイン処理"""
    print("=" * 60)
    print("VTT to SRT Converter - Gemini API v3 (高精度版)")
    print("=" * 60)

    # APIキーの確認
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("\nエラー: 環境変数 GEMINI_API_KEY が設定されていません。")
        print("以下のコマンドで設定してください:")
        print('  export GEMINI_API_KEY="your-api-key-here"')
        sys.exit(1)

    # OpenAI クライアントをGemini用に設定
    client = OpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )

    # 誤字パターンを読み込み
    patterns = load_correction_patterns()
    print(f"誤字パターン: {len(patterns.get('simple_patterns', {}))} 件読み込み")

    # コマンドライン引数からVTTファイルのパスを取得
    if len(sys.argv) < 2:
        print("\n使い方: python3 process_vtt_gemini_v3.py <vttファイルのパス>")
        sys.exit(1)

    vtt_file_path = sys.argv[1]
    vtt_file = Path(vtt_file_path)

    if not vtt_file.exists():
        print(f"エラー: ファイルが見つかりません: {vtt_file_path}")
        sys.exit(1)

    if not vtt_file.suffix.lower() == '.vtt':
        print(f"エラー: VTTファイルを指定してください: {vtt_file_path}")
        sys.exit(1)

    print(f"\n入力ファイル: {vtt_file.name}")

    # タイムスタンプでフォルダ名を生成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work_folder_name = f"work_{timestamp}"
    work_folder = Path(__file__).parent / work_folder_name
    work_folder.mkdir(exist_ok=True)

    print(f"作業フォルダ: {work_folder_name}")

    # VTTファイルを作業フォルダにコピー
    work_vtt_file = work_folder / vtt_file.name
    shutil.copy2(vtt_file, work_vtt_file)

    # VTTファイルを読み込む
    entries = read_vtt_file(work_vtt_file)

    # Gemini APIで処理
    corrected_texts = process_entries(entries, client, patterns)

    # 最終ファイルの出力
    final_output_path = work_folder / "final_output_corrected.srt"
    write_srt_file(entries, corrected_texts, final_output_path)

    print("\n" + "=" * 60)
    print("処理完了!")
    print("=" * 60)
    print(f"作業フォルダ: {work_folder}")
    print(f"最終ファイル: {final_output_path.name}")
    print(f"サイズ: {final_output_path.stat().st_size / 1024:.1f} KB")
    print("=" * 60)
    print("\n誤字を見つけたら correction_patterns.json に追加してください。")


if __name__ == "__main__":
    main()
