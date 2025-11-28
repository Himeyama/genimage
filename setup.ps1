$dir = "$HOME\genimage"

if (Test-Path $DIR) {
    Write-Error "❌ $DIR は既に存在します"
    exit 1
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "❌  uv コマンドが存在しません"
    Write-Error
    Write-Error "uv コマンドのインストールが必要です。"
    Write-Error "以下のコマンドを実行してインストールしてください。"
    Write-Error
    Write-Error "PS> powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`""
    Write-Error
    exit 1
}

git clone https://github.com/Himeyama/genimage.git $dir
if ($LASTEXITCODE -ne 0) {
    Write-Error "❌  git clone に失敗しました"
    exit 1
}

uv venv --directory $dir
if ($LASTEXITCODE -ne 0) {
    Write-Error "❌  uv venv に失敗しました"
    exit 1
}

uv sync --directory $dir
if ($LASTEXITCODE -ne 0) {
    Write-Error "❌  uv sync に失敗しました"
    exit 1
}

Write-Host "✨  セットアップが完了しました"