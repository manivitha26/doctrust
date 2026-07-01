# Script to start DocuTrust Backend and Frontend on Windows

Write-Host "Starting DocuTrust Enterprise RAG Platform..." -ForegroundColor Cyan

# Start Backend in a new window
Write-Host "Starting FastAPI Backend..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; if (!(Test-Path venv)) { python -m venv venv; .\\venv\\Scripts\\activate; pip install -r requirements.txt } else { .\\venv\\Scripts\\activate }; uvicorn app.main:app --host 127.0.0.1 --port 8005 --reload"

# Start Frontend in a new window
Write-Host "Starting Frontend Server..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; python -m http.server 8080"

Write-Host "DocuTrust is starting up!" -ForegroundColor Cyan
Write-Host "Backend API: http://127.0.0.1:8005"
Write-Host "Frontend UI: http://localhost:8080"
