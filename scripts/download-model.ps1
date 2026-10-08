# Downloads the open-weight Qwen2.5-1.5B-Instruct model (GGUF, Q4_K_M, ~1.04 GB)
# once, then verifies its SHA-256. After this, the app runs fully offline.
#
#   powershell -ExecutionPolicy Bypass -File scripts\download-model.ps1
#
param(
    [string]$OutDir = (Join-Path $PSScriptRoot "..\models")
)

$ErrorActionPreference = "Stop"
$url = "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
$dest = Join-Path $OutDir "qwen2.5-1.5b-instruct-q4_k_m.gguf"
# SHA-256 of the official Qwen-published Q4_K_M file (pinned; re-verify if
# Qwen ever re-uploads): 6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e
$expectedSha256 = "6A1A2EB6D15622BF3C96857206351BA97E1AF16C30D7A74EE38970E434E9407E"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

if (Test-Path $dest) {
    $size = (Get-Item $dest).Length
    Write-Host "Model already present: $dest ($([math]::Round($size/1MB)) MB)"
} else {
    Write-Host "Downloading Qwen2.5-1.5B-Instruct (Apache-2.0) ~1.04 GB ..."
    curl.exe -L -C - --progress-bar -o $dest $url
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Download failed (exit $LASTEXITCODE). Re-run to resume with -C -"
        exit 1
    }
}

Write-Host "Verifying SHA-256 ..."
$actual = (Get-FileHash $dest -Algorithm SHA256).Hash
if ($actual -ne $expectedSha256) {
    Write-Error ("Checksum MISMATCH.`n  expected: $expectedSha256`n  actual:   $actual`n" +
                 "Delete the file and re-run to download a fresh copy.")
    exit 1
}
Write-Host "Checksum OK. Model ready: $dest"
