#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VTTファイルをドラッグ&ドロップで処理するスクリプト
使い方: python3 process_vtt.py <vttファイルのパス>
"""

import os
import sys
import re
import json
from datetime import datetime
from pathlib import Path
import shutil


def read_vtt_file(vtt_path):
    """VTTファイルを読み込んでエントリのリストを返す"""
    print(f"  [LOG] ファイルオープン開始: {vtt_path}")
    with open(vtt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    print(f"  [LOG] ファイル読み込み完了: {len(content)} 文字")

    # VTTのエントリを抽出（タイムスタンプと字幕のペア）
    print(f"  [LOG] 正規表現パターンマッチング開始...")
    pattern = r'(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3}).*?\n((?:.*(?:\n|$))+?)(?=\n\d{2}:\d{2}:\d{2}\.\d{3}|$)'
    matches = re.findall(pattern, content, re.MULTILINE)
    print(f"  [LOG] パターンマッチング完了: {len(matches)} 件")

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
    print(f"  [LOG] エントリ構築完了: {len(entries)} エントリ")

    return entries


def vtt_time_to_srt_time(vtt_time):
    """VTT形式の時間（HH:MM:SS.mmm）をSRT形式（HH:MM:SS,mmm）に変換"""
    return vtt_time.replace('.', ',')


def correct_entry_text(text):
    """エントリのテキストを校正"""
    # フィラー除去
    fillers = ['えー、', 'えー', 'あのー、', 'あのー', 'えっと、', 'えっと', 'その、', 'まあ、', 'まあ']
    for filler in fillers:
        text = text.replace(filler, '')

    # 自然な表現に修正
    text = text.replace('なんすね', 'なんですね')
    text = text.replace('なんすか', 'なんですか')
    text = text.replace('っすね', 'ですね')
    text = text.replace('っすよ', 'ですよ')
    text = text.replace('っす', 'です')

    # 歯科用語の校正（ひらがな→漢字）
    text = text.replace('ほてつ', '補綴')
    text = text.replace('ホテツ', '補綴')
    text = text.replace('わいしょうし', '矮小歯')
    text = text.replace('けんじょうしつ', '舌側歯')
    text = text.replace('きょうごうめん', '咬合面')
    text = text.replace('こうくうがい', '口腔外')

    return text.strip()


def process_batch(entries, batch_num, output_dir):
    """バッチを処理してSRTファイルを作成"""
    print(f"\n[バッチ {batch_num}] {len(entries)} エントリを処理中...")

    output_path = output_dir / f"output_batch_{batch_num}.srt"

    with open(output_path, 'w', encoding='utf-8') as f:
        for entry in entries:
            # テキスト校正
            corrected_text = correct_entry_text(entry['text'])

            # SRT形式で書き込み
            f.write(f"{entry['index']}\n")
            f.write(f"{vtt_time_to_srt_time(entry['start'])} --> {vtt_time_to_srt_time(entry['end'])}\n")
            f.write(f"{corrected_text}\n\n")

    print(f"  ✓ 保存完了: {output_path}")
    return output_path


def merge_batch_files(output_dir, total_batches, final_output_path):
    """中間ファイルを結合して最終的なSRTファイルを作成"""
    print("\n最終ファイルを結合しています...")
    with open(final_output_path, 'w', encoding='utf-8') as final:
        for batch_num in range(1, total_batches + 1):
            batch_file = output_dir / f"output_batch_{batch_num}.srt"
            if batch_file.exists():
                with open(batch_file, 'r', encoding='utf-8') as f:
                    final.write(f.read())
    print(f"✓ 完成: {final_output_path}")


def main():
    """メイン処理"""
    print("=" * 60)
    print("VTT to SRT Converter - Claude 内部完結型")
    print("=" * 60)

    # コマンドライン引数からVTTファイルのパスを取得
    if len(sys.argv) < 2:
        print("\n使い方: python3 process_vtt.py <vttファイルのパス>")
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

    # タイムスタンプでフォルダ名を生成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work_folder_name = f"work_{timestamp}"
    work_folder = Path.cwd() / work_folder_name
    work_folder.mkdir(exist_ok=True)

    print(f"作業フォルダ: {work_folder_name}")

    # VTTファイルを作業フォルダにコピー
    work_vtt_file = work_folder / vtt_file.name
    shutil.copy2(vtt_file, work_vtt_file)
    print(f"✓ VTTファイルをコピーしました")

    # VTTファイルを読み込む
    print(f"\nVTTファイルを読み込んでいます...")
    entries = read_vtt_file(work_vtt_file)
    print(f"総エントリ数: {len(entries)}")

    # バッチ処理
    batch_size = 100
    total_batches = (len(entries) + batch_size - 1) // batch_size

    print(f"\nバッチ処理を開始します（{batch_size}エントリ/バッチ）")
    print(f"総バッチ数: {total_batches}")

    for batch_num in range(1, total_batches + 1):
        start_idx = (batch_num - 1) * batch_size
        end_idx = min(start_idx + batch_size, len(entries))
        batch_entries = entries[start_idx:end_idx]

        process_batch(batch_entries, batch_num, work_folder)

    # 最終ファイルの結合
    final_output_path = work_folder / "final_output_corrected.srt"
    merge_batch_files(work_folder, total_batches, final_output_path)

    print("\n" + "=" * 60)
    print("処理完了！")
    print("=" * 60)
    print(f"作業フォルダ: {work_folder}")
    print(f"最終ファイル: {final_output_path.name}")
    print(f"サイズ: {final_output_path.stat().st_size / 1024:.1f} KB")
    print("=" * 60)


if __name__ == "__main__":
    main()
