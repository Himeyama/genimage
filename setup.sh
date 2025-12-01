DIR="$HOME/genimage"

if ! command -v git &> /dev/null; then
    echo "git コマンドが存在しません。インストールを試みます..." >&2
    echo >&2

    INSTALLED_SUCCESSFULLY=false

    if command -v apt-get &> /dev/null; then
        echo "deb パッケージマネージャー (apt) を検出しました。" >&2
        if sudo apt-get update && sudo apt-get install -y git; then
            echo "✅ git のインストールが完了しました (apt)。" >&2
            INSTALLED_SUCCESSFULLY=true
        else
            echo "❌ git のインストールに失敗しました (apt)。" >&2
        fi
    elif command -v dnf &> /dev/null; then
        echo "rpm パッケージマネージャー (dnf) を検出しました。" >&2
        if sudo dnf install -y git; then
            echo "✅ git のインストールが完了しました (dnf)。" >&2
            INSTALLED_SUCCESSFULLY=true
        else
            echo "❌ git のインストールに失敗しました (dnf)。" >&2
        fi
    fi

    echo >&2

    if [ "$INSTALLED_SUCCESSFULLY" = false ]; then
        echo "❌ git の自動インストールに失敗しました。" >&2
        echo "手動で git をインストールしてください。" >&2
        echo >&2
        exit 1
    fi

    # 最終確認
    if ! command -v git &> /dev/null; then
        echo "❌ git のインストールは試みられましたが、まだコマンドが見つかりません。パスを確認してください。" >&2
        echo "手動で git をインストールしてください。" >&2
        echo >&2
        exit 1
    fi
fi

if [ -e "$DIR" ]; then
    echo "❌ $DIR は既に存在します" >&2
    exit 1
fi

if ! command -v uv &> /dev/null; then
    echo "uv コマンドが存在しません。インストールを試みます..." >&2
    echo >&2

    if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
        echo "❌ uv のインストールに失敗しました。" >&2
        echo "手動で uv をインストールしてください。" >&2
        echo >&2
        exit 1
    fi

    # 最終確認
    if ! command -v uv &> /dev/null; then
        echo "❌ uv のインストールは試みられましたが、まだコマンドが見つかりません。パスを確認してください。" >&2
        echo "手動で uv をインストールしてください。" >&2
        echo >&2
        exit 1
    fi
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