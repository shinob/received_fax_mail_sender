#!/bin/bash

# FAX受信メール送信システム 実行スクリプト
# このスクリプトはどのディレクトリからでも実行可能です

set -e  # エラー時に停止

# スクリプトの場所を取得（シンボリックリンク対応）
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"

# プロジェクトディレクトリに移動
cd "$SCRIPT_DIR"

# デフォルト設定ファイルのパスを絶対パスに変換
DEFAULT_CONFIG="$SCRIPT_DIR/config/config.yaml"
DEFAULT_ENV="$SCRIPT_DIR/.env"

# 引数を解析して設定ファイルパスを調整
ARGS=()
CONFIG_SPECIFIED=false
ENV_SPECIFIED=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --config|-c)
            if [[ "$2" == ./* ]] || [[ "$2" == ../* ]]; then
                # 相対パスの場合は元の作業ディレクトリからの絶対パスに変換
                ARGS+=("$1" "$(realpath -m "$OLDPWD/$2")")
            elif [[ "$2" == /* ]]; then
                # 絶対パスの場合はそのまま使用
                ARGS+=("$1" "$2")
            else
                # 相対パス（./ ../ で始まらない）の場合はプロジェクトディレクトリからの相対パス
                ARGS+=("$1" "$SCRIPT_DIR/$2")
            fi
            CONFIG_SPECIFIED=true
            shift 2
            ;;
        --env|-e)
            if [[ "$2" == ./* ]] || [[ "$2" == ../* ]]; then
                # 相対パスの場合は元の作業ディレクトリからの絶対パスに変換
                ARGS+=("$1" "$(realpath -m "$OLDPWD/$2")")
            elif [[ "$2" == /* ]]; then
                # 絶対パスの場合はそのまま使用
                ARGS+=("$1" "$2")
            else
                # 相対パス（./ ../ で始まらない）の場合はプロジェクトディレクトリからの相対パス
                ARGS+=("$1" "$SCRIPT_DIR/$2")
            fi
            ENV_SPECIFIED=true
            shift 2
            ;;
        *)
            ARGS+=("$1")
            shift
            ;;
    esac
done

# デフォルト設定ファイルを指定（ユーザーが指定していない場合）
if [[ "$CONFIG_SPECIFIED" == false ]]; then
    ARGS+=("--config" "$DEFAULT_CONFIG")
fi

if [[ "$ENV_SPECIFIED" == false ]]; then
    ARGS+=("--env" "$DEFAULT_ENV")
fi

# Python環境の確認
if ! command -v python3 &> /dev/null; then
    echo "エラー: python3が見つかりません。Python 3.8以上をインストールしてください。" >&2
    exit 1
fi

# 必要なライブラリがインストールされているか確認
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    python3 -c "
import sys
required_packages = []
try:
    with open('$SCRIPT_DIR/requirements.txt', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                package = line.split('>=')[0].split('==')[0].split('[')[0]
                required_packages.append(package)
except FileNotFoundError:
    pass

missing_packages = []
for package in required_packages:
    try:
        __import__(package.replace('-', '_'))
    except ImportError:
        missing_packages.append(package)

if missing_packages:
    print(f'エラー: 以下のパッケージがインストールされていません: {', '.join(missing_packages)}', file=sys.stderr)
    print('次のコマンドでインストールしてください:', file=sys.stderr)
    print(f'pip install -r $SCRIPT_DIR/requirements.txt', file=sys.stderr)
    #sys.exit(1)
" || exit 1
fi

# ログディレクトリが存在しない場合は作成
mkdir -p "$SCRIPT_DIR/logs"
mkdir -p "$SCRIPT_DIR/temp"

# 実行情報をログに記録
echo "[$(date '+%Y-%m-%d %H:%M:%S')] FAX Processor starting from $(pwd) with args: ${ARGS[*]}" >> "$SCRIPT_DIR/logs/run.log"

# メインプログラムを実行
exec python3 -m src.main "${ARGS[@]}"