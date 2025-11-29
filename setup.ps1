$DIR = Join-Path $HOME "genimage"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host("❌ uv コマンドが存在しません") -ForegroundColor Red
    Write-Host("") -ForegroundColor Red
    Write-Host("uv コマンドのインストールが必要です。") -ForegroundColor Red
    Write-Host("以下のコマンドを実行してインストールしてください。") -ForegroundColor Red
    Write-Host("") -ForegroundColor Red
    Write-Host('PS> powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"') -ForegroundColor Red
    Write-Host("") -ForegroundColor Red
    exit 1
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host("❌ git コマンドが存在しません") -ForegroundColor Red 
    Write-Host("") -ForegroundColor Red
    Write-Host("以下のコマンドを実行してインストールしてください。") -ForegroundColor Red
    Write-Host("") -ForegroundColor Red
    Write-Host("PS> winget install --id Git.Git") -ForegroundColor Red
    Write-Host("") -ForegroundColor Red
    exit 1
}

if (Test-Path $DIR) {
    Push-Location .
    Set-Location $DIR
    git pull
    Pop-Location
    exit 0
}

git clone https://github.com/Himeyama/genimage.git $DIR
if ($LASTEXITCODE -ne 0) {
    Write-Host("❌ git clone に失敗しました") -ForegroundColor Red
    exit 1
}

uv venv --directory $DIR
if ($LASTEXITCODE -ne 0) {
    Write-Host("❌ uv venv に失敗しました") -ForegroundColor Red
    exit 1
}

uv sync --directory $DIR
if ($LASTEXITCODE -ne 0) {
    Write-Host("❌ uv sync に失敗しました") -ForegroundColor Red
    exit 1
}

Write-Host "✨  セットアップが完了しました"
