#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VTTファイルをGemini APIで高精度校正してSRTに変換するスクリプト (v2)

使い方: python3 process_vtt_gemini_v2.py <vttファイルのパス>
環境変数: GEMINI_API_KEY にAPIキーを設定

変更点 (v2):
- OpenAI SDKを使用してGemini APIを呼び出し
- [番号] 形式で正規表現抽出（AIの回答フォーマット崩れ対策）
- チャンクサイズ500件
- フォールバック処理（元テキスト保持）
"""

import os
import sys
import re
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
    """VTT形式の時間（HH:MM:SS.mmm）をSRT形式（HH:MM:SS,mmm）に変換"""
    return vtt_time.replace('.', ',')


def parse_ai_response(response_text, original_entries):
    """
    AIの回答から[番号]形式でテキストを抽出
    フォーマットが崩れても対応できる堅牢なパーサー
    """
    # 元のテキストをインデックスで辞書化（フォールバック用）
    original_dict = {entry['index']: entry['text'] for entry in original_entries}
    result = {}

    # [番号] パターンで行を抽出
    lines = response_text.strip().split('\n')
    for line in lines:
        match = re.match(r'^\[(\d+)\]\s*(.*)', line.strip())
        if match:
            index = int(match.group(1))
            text = match.group(2).strip()
            if text:  # 空でない場合のみ採用
                result[index] = text

    # フォールバック: 見つからなかった番号は元のテキストを使用
    for entry in original_entries:
        idx = entry['index']
        if idx not in result:
            result[idx] = original_dict[idx]
            print(f"    [FALLBACK] エントリ {idx} は元のテキストを使用")

    return result


def call_gemini_api(client, entries_batch, batch_info=""):
    """
    Gemini APIを呼び出してバッチを校正
    OpenAI SDK経由でGemini APIを使用
    """
    # エントリを[番号] 形式のテキストに変換
    input_lines = []
    for entry in entries_batch:
        input_lines.append(f"[{entry['index']}] {entry['text']}")
    input_text = '\n'.join(input_lines)

    prompt = f"""以下は歯科医師・矯正歯科医による会議の音声認識字幕です。専門家として校正してください。

【最重要：音声認識の誤変換を修正】
以下は頻出する誤変換パターンです。必ず修正してください：
- 「司会者」→「歯科医師」（しかいし）
- 「店員」→「転院」（てんいん）
- 「強制」→「矯正」（きょうせい）
- 「補填」→「保定」（ほてい）
- 「開墾」→「開咬」（かいこう）
- 「口頭」→「咬頭」（こうとう）
- 「抜歯」の誤変換に注意
- 「支店」→「視点」または「歯点」の文脈判断
- 「効果」→「咬合」の可能性を検討
- 「ほてつ」→「補綴」
- 「舌足らず」→「舌側」の可能性
- 「近親」→「近心」
- 「援心」「遠心」の確認
- 「症例」「正例」の統一
- 「レンズパーク」「現図パーク」→「Genspark」（AIサービス名）
- 「エンズパーク」→「Genspark」

【校正ルール】
1. フィラーを完全除去（えー、あのー、えっと、その、まあ、なんか）

2. 歯科専門用語を正確に
   - インビザライン、アライナー、ブラケット、ワイヤー
   - 咬合、舌側、頬側、近心、遠心
   - IPR、アタッチメント、エラスティック、リテーナー

3. 口語を自然な日本語に（「なんすか」→「なんですか」）

4. 発話者名（minamidate:、Asano:等）は絶対に保持

【出力形式】
[番号] 校正後テキスト
※番号は入力と同じ。余計な挨拶・説明は不要。

【入力データ】
{input_text}

【出力】"""

    try:
        response = client.chat.completions.create(
            model="gemini-2.0-flash",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"    [ERROR] API呼び出しエラー: {e}")
        return None


def process_entries(entries, client, output_dir, chunk_size=500):
    """
    エントリをチャンクに分割して処理
    """
    total_entries = len(entries)
    total_chunks = (total_entries + chunk_size - 1) // chunk_size

    print(f"\n処理開始: 総エントリ数 {total_entries}, チャンクサイズ {chunk_size}")
    print(f"総チャンク数: {total_chunks}")
    print("-" * 50)

    all_corrected = {}

    for chunk_num in range(1, total_chunks + 1):
        start_idx = (chunk_num - 1) * chunk_size
        end_idx = min(start_idx + chunk_size, total_entries)
        chunk_entries = entries[start_idx:end_idx]

        # 進捗表示（タイムアウト対策）
        print(f"\n[チャンク {chunk_num}/{total_chunks}] エントリ {start_idx + 1}-{end_idx} を処理中...")

        # API呼び出し
        response_text = call_gemini_api(client, chunk_entries, f"chunk {chunk_num}")

        if response_text:
            # AIの回答をパース
            corrected = parse_ai_response(response_text, chunk_entries)
            all_corrected.update(corrected)
            print(f"  [OK] {len(corrected)} エントリを校正完了")
        else:
            # APIエラー時は元のテキストを使用
            print(f"  [WARN] APIエラー、元のテキストを使用")
            for entry in chunk_entries:
                all_corrected[entry['index']] = entry['text']

        # レートリミット対策（最後のチャンク以外は1秒待機）
        if chunk_num < total_chunks:
            print(f"  [WAIT] 1秒待機...")
            time.sleep(1)

    return all_corrected


def write_srt_file(entries, corrected_texts, output_path):
    """
    校正済みテキストをSRTファイルに書き出し
    """
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
    print("VTT to SRT Converter - Gemini API v2 (OpenAI SDK)")
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

    # コマンドライン引数からVTTファイルのパスを取得
    if len(sys.argv) < 2:
        print("\n使い方: python3 process_vtt_gemini_v2.py <vttファイルのパス>")
        print("または: VTTファイルをこのスクリプトにドラッグ&ドロップ")
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
    print(f"使用モデル: gemini-2.0-flash")
    print(f"API方式: OpenAI SDK互換エンドポイント")

    # タイムスタンプでフォルダ名を生成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work_folder_name = f"work_{timestamp}"
    work_folder = Path(__file__).parent / work_folder_name
    work_folder.mkdir(exist_ok=True)

    print(f"作業フォルダ: {work_folder_name}")

    # VTTファイルを作業フォルダにコピー
    work_vtt_file = work_folder / vtt_file.name
    shutil.copy2(vtt_file, work_vtt_file)
    print(f"[OK] VTTファイルをコピーしました")

    # VTTファイルを読み込む
    print(f"\nVTTファイルを読み込んでいます...")
    entries = read_vtt_file(work_vtt_file)

    # Gemini APIでバッチ処理
    corrected_texts = process_entries(entries, client, work_folder, chunk_size=500)

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


if __name__ == "__main__":
    main()
