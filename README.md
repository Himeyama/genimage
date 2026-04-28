# GENIMAGE
画像生成 AI (SDXL) を使用して、コマンドライン (CLI) で画像を作成します。

## かんたん環境構築
### Windows
Windows 環境で簡単環境構築を実施するには、git コマンド及び uv コマンドのインストールが必要です。

```ps1
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/Himeyama/genimage/refs/heads/master/setup.ps1 | iex"
```

### Linux / WSL2
Linux 環境で簡単環境構築を実施するには、curl コマンド、git コマンド及び uv コマンドのインストールが必要です。

```sh
curl https://raw.githubusercontent.com/Himeyama/genimage/refs/heads/master/setup.sh | bash
```

## 簡単な使い方
まず、モデルの配置が必要です。
例えば、モデルを `$HOME/genimage/models/<MODEL>.safetensors` に配置します。

### Windows / Linux
```ps1
uv run --directory $HOME/genimage python -m main --model models/<MODEL>.safetensors 
```

### WSL2
```ps1
wsl -- uv run --directory $HOME/genimage python -m main --model models/<MODEL>.safetensors
```

## 詳細な使い方

```
usage: main.py [-h] [--mcp] [--model-id MODEL_ID] [--negative-prompt NEGATIVE_PROMPT] [--output OUTPUT] [--num-images NUM_IMAGES] [prompt]
```

画像生成 AI (Stable Diffusion XL) を使用します。

### 位置引数
- `prompt`: 画像生成のプロンプト (通常モードでは必須、MCPモードでは標準入力から読み取られます)。

### オプション
- `-h`, `--help`: ヘルプメッセージを表示して終了します。
- `--mcp`: MCP モードを有効にします。プロンプトは標準入力から読み取られ、出力パスは標準出力に出力します。
- `--img2img`: image2image モードを有効にします。入力画像をプロンプトに基づいて変換します。
- `--input-image`, `-i INPUT_IMAGE`: image2image の入力画像パス (image2image モード必須)
- `--strength`, `-s STRENGTH`: image2image の変換強度 0.0-1.0 (デフォルト: 0.8)
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

### image2image (CLI)

入力画像をプロンプトに基づいて変換します。

```sh
# image2image モードで画像変換
uv run --directory ~/genimage python -m main --img2img --input-image input.png --strength 0.7 "anime style, colorful" -o output.png
```

オプション：
- `--img2img`: image2image モードを有効化
- `--input-image`, `-i`: 入力画像パス（必須）
- `--strength`, `-s`: 変換強度 0.0-1.0（デフォルト: 0.8）

例：
```sh
uv run --directory ~/genimage python -m main --model-id "./models/sdxl.safetensors" --img2img -i photo.jpg -s 0.8 "painting style" -o result.png
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

## MCP ツール

### generate_image
プロンプトから画像を生成します。

| パラメータ | 必須 | 説明 |
|-----------|------|------|
| `prompt` | ○ | 画像生成用のプロンプトテキスト |
| `negative_prompt` | - | ネガティブプロンプト |
| `output_path` | - | 出力ファイルパス |

### image2image
入力画像をプロンプトに基づいて変換します（image-to-image）。

| パラメータ | 必須 | 説明 |
|-----------|------|------|
| `prompt` | ○ | 画像変換用のプロンプトテキスト |
| `image_path` | ○ | 変換元の画像（Base64またはファイルパス） |
| `negative_prompt` | - | ネガティブプロンプト |
| `strength` | - | 変換強度 0.0-1.0（デフォルト: 0.8） |
| `output_path` | - | 出力ファイルパス |

#### image2image 使用例

```json
{
  "name": "image2image",
  "arguments": {
    "prompt": "anime style, colorful, vibrant",
    "image_path": "/path/to/input.png",
    "strength": 0.7
  }
}
```

Base64画像を入力として使用する場合：

```json
{
  "name": "image2image",
  "arguments": {
    "prompt": "anime style",
    "image_path": "data:image/png;base64,iVBORw0KGgoAAA..."
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

> ツールの実行 (BASE64 で生成画像を取得)
```json
{"jsonrpc":"2.0","id":"3","method":"tools/call","params":{"name":"generate_image","arguments":{"prompt":"kimono, open-mouth, bob-cut, black-hair, green-eyes"}}}
```

> ツールの実行 (出力パスに生成画像を出力)
```json
{"jsonrpc":"2.0","id":"3","method":"tools/call","params":{"name":"generate_image","arguments":{"prompt":"kimono, open-mouth, bob-cut, black-hair, green-eyes","output_path":"output.png"}}}
```

> ツール実行 (ネガティブプロンプトあり)
```json
{"jsonrpc":"2.0","id":"3","method":"tools/call","params":{"name":"generate_image","arguments":{"prompt":"open-mouth, bob-cut, black-hair, green-eyes","negative_prompt":"ears","output_path":"output.png"}}}
```

> image2image の実行 (ファイルパスから変換)
```json
{"jsonrpc":"2.0","id":"4","method":"tools/call","params":{"name":"image2image","arguments":{"prompt":"anime style, colorful, vibrant","image_path":"/path/to/input.png","strength":0.7}}}
```

> image2image の実行 (Base64画像から変換)
```json
{"jsonrpc":"2.0","id":"5","method":"tools/call","params":{"name":"image2image","arguments":{"prompt":"anime style","image_path":"data:image/png;base64,iVBORw0KGgoAAA...","strength":0.8}}}
```

> image2image の実行 (出力パス指定)
```json
{"jsonrpc":"2.0","id":"6","method":"tools/call","params":{"name":"image2image","arguments":{"prompt":"anime style, colorful","image_path":"/path/to/input.png","output_path":"output.png","strength":0.75}}}
```