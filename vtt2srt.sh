#!/bin/bash
# VTT to SRT Converter - Gemini API版
# 使い方: ./vtt2srt.sh /path/to/file.vtt

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# APIキーの確認
if [ -z "$GEMINI_API_KEY" ]; then
    echo "エラー: GEMINI_API_KEY が設定されていません。"
    echo ""
    echo "以下のコマンドでAPIキーを設定してください："
    echo "  export GEMINI_API_KEY=\"your-api-key\""
    echo ""
    echo "永続化するには ~/.zshrc に追加してください："
    echo "  echo 'export GEMINI_API_KEY=\"your-api-key\"' >> ~/.zshrc"
    exit 1
fi

# 引数の確認
if [ -z "$1" ]; then
    echo "使い方: $0 <VTTファイルのパス>"
    echo ""
    echo "例: $0 ~/Downloads/meeting.vtt"
    exit 1
fi

# スクリプトを実行
python3 "$SCRIPT_DIR/process_vtt_gemini_v3.py" "$1"
