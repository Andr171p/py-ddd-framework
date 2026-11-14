# Ждёт Locust UI и открывает браузер (make test-load).
$ErrorActionPreference = "SilentlyContinue"
$url = "http://127.0.0.1:8089/"
$deadline = (Get-Date).AddSeconds(45)

while ((Get-Date) -lt $deadline) {
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 1
        if ($response.StatusCode -eq 200) {
            Start-Process $url
            exit 0
        }
    } catch {
        Start-Sleep -Milliseconds 300
    }
}

Write-Host "Locust UI did not become ready at $url"
exit 1
