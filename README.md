# GENIMAGE
画像生成 AI (SDXL) を使用して、コマンドライン (CLI) で画像を作成します。 

## モデルの設定
オフラインのモデルを使用する場合、
SDXL 作業ディレクトリ下にモデルを置きます。

作業ディレクトリ下に .env ファイルを作成しモデルの場所を指定しモデルを定義します。

```
MODEL="./models/xxxxxxxx.safetensors"
```

## MCP
### 初期化
```json
{"jsonrpc":"2.0","method":"initialize","id":"1","params":{"protocolVersion":"2024-11-05","clientInfo":{"name":"example-client","version":"0.0.1"},"capabilities":{}}}
```

## ツールの取得
```json
{"jsonrpc": "2.0", "id": "2", "method": "tools/list"}
```

## ツールの実行
```json
{"jsonrpc":"2.0","id":"3","method":"tools/call","params":{"name":"generate_image","arguments":{"prompt":"kimono, open-mouth, bob-cut, black-hair, green-eyes"}}}
```