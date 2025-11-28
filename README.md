# GENIMAGE
画像生成 AI (SDXL) を使用して、コマンドライン (CLI) で画像を作成します。

## かんたん環境構築
### Windows
Windows 環境で簡単環境構築を実施するには、git コマンド及び uv コマンドのインストールが必要です。

```ps1
iwr "https://raw.githubusercontent.com/Himeyama/genimage/refs/heads/master/setup.ps1" -UseBasicParsing | iex
```


### Linux
Linux 環境で簡単環境構築を実施するには、curl コマンド、git コマンド及び uv コマンドのインストールが必要です。

```sh
curl https://raw.githubusercontent.com/Himeyama/genimage/refs/heads/master/setup.sh | bash
```

## 使い方

```
usage: main.py [-h] [--mcp] [--model-id MODEL_ID] [--negative-prompt NEGATIVE_PROMPT] [--output OUTPUT] [--num-images NUM_IMAGES] [prompt]
```

画像生成 AI (Stable Diffusion XL) を使用します。

### 位置引数
- `prompt`: 画像生成のプロンプト (通常モードでは必須、MCPモードでは標準入力から読み取られます)。

### オプション
- `-h`, `--help`: ヘルプメッセージを表示して終了します。
- `--mcp`: MCP モードを有効にします。プロンプトは標準入力から読み取られ、出力パスは標準出力に出力します。
- `--model-id`, `-m MODEL_ID`: Stable Diffusion XL のモデル ID
- `--negative-prompt`, `-np NEGATIVE_PROMPT`: 画像生成のネガティブプロンプト (デフォルト: なし)
- `--output`, `-o OUTPUT`: 生成された画像の出力ファイル名 (デフォルト: `output.png`)
- `--num-images`, `-n NUM_IMAGES`: 生成する画像の数 (デフォルト: 1、MCP モードではプロンプトごとに無視されます。)

## モデルの設定と実行例

モデルの指定には `--model-id` オプションを使用します。

SDXL 作業ディレクトリ下にモデルを配置する例：

```sh
uv run --directory ~/genimage python -m main --model-id "./models/<MODEL>.safetensors" girl
```

環境変数 `MODEL` でモデルを指定することも可能ですが、`--model-id` オプションが優先されます。

```sh
export MODEL="./models/<MODEL>.safetensors" # 環境変数
uv run --directory ~/genimage python -m main girl # この場合、--model-id オプションがないため環境変数が使用される

# もしくは、コマンドラインで直接環境変数を指定
MODEL="./models/<MODEL>.safetensors" uv run --directory ~/genimage python -m main girl
```

## MCP
### Claude アプリへの設定例
以下の条件下の場合、次の設定となります。

- genimage リポジトリが ~/ 下にあること
- uv コマンドがインストールされていること
- uv で仮想環境が作成されていること
- uv で依存ライブラリがインストールされていること

```json
{
  "mcpServers": {
    "genimage": {
      "command": "wsl",
      "args": [
        "--",
        "~/.local/bin/uv",
        "run",
        "--directory",
        "~/genimage",
        "python",
        "-m",
        "main",
        "--mcp"
      ]
    }
  }
}
```

### 手動による確認
MCP を標準入力から打ち込む場合、WSL 上で次のコマンドを入力し、標準入力から json 形式でテキストを渡します。

```sh
uv run --directory ~/genimage python -m main --mcp
```

> 初期化
```json
{"jsonrpc":"2.0","method":"initialize","id":"1","params":{"protocolVersion":"2024-11-05","clientInfo":{"name":"example-client","version":"0.0.1"},"capabilities":{}}}
```

> ツールの取得
```json
{"jsonrpc": "2.0", "id": "2", "method": "tools/list"}
```

> ツールの実行
```json
{"jsonrpc":"2.0","id":"3","method":"tools/call","params":{"name":"generate_image","arguments":{"prompt":"kimono, open-mouth, bob-cut, black-hair, green-eyes"}}}
```