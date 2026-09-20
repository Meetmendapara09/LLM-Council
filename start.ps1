# Start the LLM Council backend + frontend on Windows.
# Usage: .\start.ps1  (Ctrl+C stops both servers)

$root = $PSScriptRoot

$backendJob = Start-Job -Name "llm-council-backend" -ScriptBlock {
    Set-Location $using:root
    uv run python -m backend.main
}

$frontendJob = Start-Job -Name "llm-council-frontend" -ScriptBlock {
    Set-Location (Join-Path $using:root "frontend")
    npm run dev
}

Write-Host "Backend:  http://localhost:8001"
Write-Host "Frontend: http://localhost:5173"
Write-Host "Press Ctrl+C to stop both servers."

try {
    while ($true) {
        Receive-Job -Job $backendJob, $frontendJob
        Start-Sleep -Seconds 1
        $states = ($backendJob, $frontendJob | ForEach-Object { (Get-Job -Id $_.Id).State })
        if ($states -contains "Completed" -or $states -contains "Failed") {
            Receive-Job -Job $backendJob, $frontendJob
            break
        }
    }
}
finally {
    Stop-Job -Job $backendJob, $frontendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $backendJob, $frontendJob -ErrorAction SilentlyContinue
    Write-Host "Stopped backend and frontend."
}
