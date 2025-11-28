$DIR = Join-Path $HOME "genimage"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    [Console]::Error.WriteLine("❌ uv コマンドが存在しません")
    [Console]::Error.WriteLine("")
    [Console]::Error.WriteLine("uv コマンドのインストールが必要です。")
    [Console]::Error.WriteLine("以下のコマンドを実行してインストールしてください。")
    [Console]::Error.WriteLine("")
    [Console]::Error.WriteLine('PS> powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"')
    [Console]::Error.WriteLine("")
    exit 1
}

if (Test-Path $DIR) {
    [Console]::Error.WriteLine("❌ $DIR は既に存在します")
    exit 1
}

git clone https://github.com/Himeyama/genimage.git $DIR 2>$null
if ($LASTEXITCODE -ne 0) {
    [Console]::Error.WriteLine("❌ git clone に失敗しました")
    exit 1
}

uv venv --directory $DIR 2>$null
if ($LASTEXITCODE -ne 0) {
    [Console]::Error.WriteLine("❌ uv venv に失敗しました")
    exit 1
}

uv sync --directory $DIR 2>$null
if ($LASTEXITCODE -ne 0) {
    [Console]::Error.WriteLine("❌ uv sync に失敗しました")
    exit 1
}

Write-Host "✨  セットアップが完了しました"
