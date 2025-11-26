DIR="$HOME/genimage"

if ! command -v uv &> /dev/null; then
    echo "❌ uv コマンドが存在しません"
    echo
    echo "uv コマンドのインストールが必要です。"
    echo "以下のコマンドを実行してインストールしてください。"
    echo
    echo -e "$ curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo
    exit 1
fi

if ! git clone https://github.com/Himeyama/genimage.git "$DIR"; then
    echo "❌ git clone に失敗しました"
    exit 1
fi

if ! uv venv --directory "$DIR"; then
    echo "❌ uv venv に失敗しました"
    exit 1
fi

if ! uv sync --directory "$DIR"; then
    echo "❌ uv sync に失敗しました"
    exit 1
fi

echo "✨  セットアップが完了しました"