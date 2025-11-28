DIR="$HOME/genimage"

if [ -e "$DIR" ]; then
    echo "❌ $DIR は既に存在します" >&2
    exit 1
fi

if ! command -v uv &> /dev/null; then
    echo "❌ uv コマンドが存在しません" >&2
    echo >&2
    echo "uv コマンドのインストールが必要です。" >&2
    echo "以下のコマンドを実行してインストールしてください。" >&2
    echo >&2
    echo -e "$ curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    echo >&2
    exit 1
fi

if ! git clone https://github.com/Himeyama/genimage.git "$DIR"; then
    echo "❌ git clone に失敗しました" >&2
    exit 1
fi

if ! uv venv --directory "$DIR"; then
    echo "❌ uv venv に失敗しました" >&2
    exit 1
fi

if ! uv sync --directory "$DIR"; then
    echo "❌ uv sync に失敗しました" >&2
    exit 1
fi

echo "✨  セットアップが完了しました"