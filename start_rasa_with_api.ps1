$OPENAI_API_KEY = "TA_CLE_OPENAI_ICI"

$root = $PSScriptRoot
$venv = "$root\.venv\Scripts\Activate.ps1"
$src  = "$root\src"

Write-Host "🚀 Démarrage de l'environnement..." -ForegroundColor Cyan

# 1. Lancer Rasa Server (API)
Write-Host "Lancement de Rasa Server (API)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList `
    "-NoExit",
    "-Command",
    "& '$venv'; cd '$src'; `$env:OPENAI_API_KEY='$OPENAI_API_KEY'; `$host.UI.RawUI.WindowTitle='Rasa Server'; rasa run --enable-api"

# ⏳ Attente pour laisser le temps à Rasa Server de démarrer
Write-Host "⏳ Attente du démarrage de Rasa Server..." -ForegroundColor DarkYellow
Start-Sleep -Seconds 5

# 2. Lancer Rasa Action Server
Write-Host "Lancement de Rasa Action Server..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList `
    "-NoExit",
    "-Command",
    "& '$venv'; cd '$src'; `$env:OPENAI_API_KEY='$OPENAI_API_KEY'; `$host.UI.RawUI.WindowTitle='Rasa Actions'; rasa run actions"

# 3. Lancer l'interface Streamlit
Write-Host "Lancement de l'interface Streamlit..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList `
    "-NoExit",
    "-Command",
    "& '$venv'; cd '$root\ui'; `$env:OPENAI_API_KEY='$OPENAI_API_KEY'; `$host.UI.RawUI.WindowTitle='Streamlit UI'; streamlit run streamlit_app.py"