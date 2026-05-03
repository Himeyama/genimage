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
uv run --directory $HOME/genimage python -m main --model-id models/<MODEL>.safetensors "girl"
```

### WSL2
```ps1
wsl -- uv run --directory $HOME/genimage python -m main --model-id models/<MODEL>.safetensors "girl"
```

## 詳細な使い方

```
usage: main.py [-h] [--mcp] [--img2img] [--input-image INPUT_IMAGE] [--strength STRENGTH]
               [--model-id MODEL_ID] [--negative-prompt NEGATIVE_PROMPT] [--output OUTPUT]
               [--num-images NUM_IMAGES] [--steps STEPS] [--compile] [--lcm]
               [--width WIDTH] [--height HEIGHT] [prompt]
```

画像生成 AI (Stable Diffusion XL) を使用します。

### 位置引数
- `prompt`: 画像生成のプロンプト (通常モードでは必須、MCP モードでは標準入力から読み取られます)

### オプション
- `-h`, `--help`: ヘルプメッセージを表示して終了します
- `--mcp`: MCP モードを有効にします
- `--img2img`: image2image モードを有効にします。入力画像をプロンプトに基づいて変換します
- `--input-image INPUT_IMAGE`, `-i`: image2image の入力画像パス (image2image モード必須)
- `--strength STRENGTH`, `-s`: image2image の変換強度 0.0–1.0 (デフォルト: 0.1)
- `--model-id MODEL_ID`, `-m`: Stable Diffusion XL のモデル ID
- `--negative-prompt NEGATIVE_PROMPT`, `-np`: ネガティブプロンプト (オプション)
- `--output OUTPUT`, `-o`: 出力ファイル名 (デフォルト: `images/output.png`)
- `--num-images NUM_IMAGES`, `-n`: 生成する画像の数 (デフォルト: 1、通常モードのみ)
- `--steps STEPS`: 推論ステップ数 (デフォルト: `--lcm` 時は 8、通常時は 40)
- `--width WIDTH`, `-W`: 生成画像の幅 px (デフォルト: 1024)
- `--height HEIGHT`, `-H`: 生成画像の高さ px (デフォルト: 1024)
- `--compile`: `torch.compile` で UNet を最適化します（初回実行時はウォームアップに数分かかります）
- `--lcm`: LCM スケジューラで高速推論を行います（最大約 5 倍高速）

## 高速化オプション

### LCM モード (`--lcm`)
LCM (Latent Consistency Model) スケジューラを使用することで、推論ステップ数をデフォルトの 40 から 8 に削減し、最大約 5 倍の高速化が可能です。

```sh
uv run python -m main --model-id "./models/sdxl.safetensors" --lcm "girl"
# 推論ステップ数が自動的に 8 に設定される
```

### torch.compile (`--compile`)
PyTorch 2.x の `torch.compile` で UNet を最適化し、20〜40% の高速化が可能です。
初回実行時のみコンパイルのウォームアップ（数分程度）が必要です。

```sh
uv run python -m main --model-id "./models/sdxl.safetensors" --compile "girl"
```

Windows の場合は別途 triton のインストールが必要です。

```ps1
pip install "triton-windows>=3.2,<3.3"
```

### 組み合わせ
`--lcm` と `--compile` は同時に使用できます。

```sh
uv run python -m main --model-id "./models/sdxl.safetensors" --lcm --compile "girl"
```

## モデルの設定と実行例

モデルの指定には `--model-id` オプションを使用します。

```sh
uv run --directory ~/genimage python -m main --model-id "./models/<MODEL>.safetensors" "girl"
```

環境変数 `MODEL` でモデルを指定することも可能ですが、`--model-id` オプションが優先されます。

```sh
export MODEL="./models/<MODEL>.safetensors"
uv run --directory ~/genimage python -m main "girl"

# コマンドラインで直接環境変数を指定
MODEL="./models/<MODEL>.safetensors" uv run --directory ~/genimage python -m main "girl"
```

### image2image (CLI)

入力画像をプロンプトに基づいて変換します。

```sh
uv run python -m main --model-id "./models/sdxl.safetensors" \
  --img2img --input-image input.png --strength 0.7 \
  "anime style, colorful" -o output.png
```

オプション：
- `--img2img`: image2image モードを有効化
- `--input-image`, `-i`: 入力画像パス（必須）
- `--strength`, `-s`: 変換強度 0.0–1.0（デフォルト: 0.1）

## MCP
### Claude アプリへの設定例
以下の条件下の場合、次の設定となります。

- genimage リポジトリが `~/` 下にあること
- uv コマンドがインストールされていること
- uv で仮想環境と依存ライブラリがインストールされていること

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

LCM 高速モードで起動する場合は `"--lcm"` を追加します。

```json
"args": ["--", "~/.local/bin/uv", "run", "--directory", "~/genimage", "python", "-m", "main", "--mcp", "--lcm"]
```

## MCP ツール

### generate_image
プロンプトから画像を生成します。

| パラメータ | 必須 | 説明 |
|-----------|------|------|
| `prompt` | ○ | 画像生成用のプロンプトテキスト |
| `negative_prompt` | - | ネガティブプロンプト |
| `output_path` | - | 出力ファイルパス |
| `steps` | - | 推論ステップ数（デフォルト: 起動時の設定に従う） |
| `width` | - | 生成画像の幅 px（デフォルト: 1024） |
| `height` | - | 生成画像の高さ px（デフォルト: 1024） |

### image2image
入力画像をプロンプトに基づいて変換します（image-to-image）。

| パラメータ | 必須 | 説明 |
|-----------|------|------|
| `prompt` | ○ | 画像変換用のプロンプトテキスト |
| `image_path` | ○ | 変換元の画像（Base64 またはファイルパス） |
| `negative_prompt` | - | ネガティブプロンプト |
| `strength` | - | 変換強度 0.0–1.0（デフォルト: 0.1） |
| `output_path` | - | 出力ファイルパス |
| `steps` | - | 推論ステップ数（デフォルト: 起動時の設定に従う） |

### 手動による確認
MCP を標準入力から打ち込む場合、WSL 上で次のコマンドを入力し、標準入力から JSON 形式でテキストを渡します。

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

> ツールの実行 (Base64 で生成画像を取得)
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

> ツールの実行 (解像度指定)
```json
{"jsonrpc":"2.0","id":"3","method":"tools/call","params":{"name":"generate_image","arguments":{"prompt":"girl","width":768,"height":1344,"output_path":"output.png"}}}
```

> image2image の実行 (ファイルパスから変換)
```json
{"jsonrpc":"2.0","id":"4","method":"tools/call","params":{"name":"image2image","arguments":{"prompt":"anime style, colorful, vibrant","image_path":"/path/to/input.png","strength":0.7}}}
```

> image2image の実行 (Base64 画像から変換)
```json
{"jsonrpc":"2.0","id":"5","method":"tools/call","params":{"name":"image2image","arguments":{"prompt":"anime style","image_path":"data:image/png;base64,iVBORw0KGgoAAA...","strength":0.8}}}
```

> image2image の実行 (出力パス指定)
```json
{"jsonrpc":"2.0","id":"6","method":"tools/call","params":{"name":"image2image","arguments":{"prompt":"anime style, colorful","image_path":"/path/to/input.png","output_path":"output.png","strength":0.75}}}
```
