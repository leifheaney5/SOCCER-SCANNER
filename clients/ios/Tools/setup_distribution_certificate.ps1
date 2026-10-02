<#
.SYNOPSIS
    One-time setup of the long-lived Apple Distribution certificate used by CI.

.DESCRIPTION
    Creates a private key and certificate signing request locally, waits while you
    upload the request in the Apple Developer portal and download the resulting
    certificate, then packages key + certificate as a .p12 and stores it and a
    random password as the app-store environment secrets
    APPLE_DISTRIBUTION_CERT_P12_BASE64 and APPLE_DISTRIBUTION_CERT_PASSWORD.

    The private key and password never leave this machine except as GitHub
    secrets, and are never printed. Back up the .p12 and password (for example in
    a password manager): Apple cannot re-issue the private key.

.EXAMPLE
    pwsh clients/ios/Tools/setup_distribution_certificate.ps1 -Email you@example.com
#>
param(
    [Parameter(Mandatory = $true)][string]$Email,
    [string]$Repo = 'leifheaney5/soccer-radar',
    [string]$Environment = 'app-store',
    [string]$WorkDir = (Join-Path $HOME 'soccer-radar-signing'),
    # Build and verify the .p12 but do not write GitHub secrets.
    [switch]$SkipSecretUpload
)

$ErrorActionPreference = 'Stop'

$openssl = (Get-Command openssl -ErrorAction SilentlyContinue).Source
if (-not $openssl) { $openssl = 'C:\Program Files\Git\usr\bin\openssl.exe' }
if (-not (Test-Path $openssl)) { throw 'openssl not found. Install Git for Windows or add openssl to PATH.' }
if (-not $SkipSecretUpload -and -not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'GitHub CLI (gh) not found.' }

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
$key = Join-Path $WorkDir 'distribution.key'
$csr = Join-Path $WorkDir 'distribution.csr'
$cer = Join-Path $WorkDir 'distribution.cer'
$pem = Join-Path $WorkDir 'distribution.pem'
$p12 = Join-Path $WorkDir 'distribution.p12'

function Invoke-OpenSsl {
    & $openssl @args
    if ($LASTEXITCODE -ne 0) { throw "openssl $($args[0]) failed with exit code $LASTEXITCODE" }
}

if (-not (Test-Path $key)) {
    Invoke-OpenSsl genrsa -out $key 2048 2>$null
}
Invoke-OpenSsl req -new -key $key -out $csr -subj "/emailAddress=$Email/CN=Soccer Radar CI/C=US"

if (-not (Test-Path $cer)) {
    Write-Host ''
    Write-Host "Certificate request written to: $csr"
    Write-Host '1. Open https://developer.apple.com/account/resources/certificates/add'
    Write-Host '   (if Apple says the Distribution limit is reached, revoke an unused CI-created'
    Write-Host '   Apple Distribution certificate first).'
    Write-Host '2. Choose "Apple Distribution", upload the .csr above, and download the certificate.'
    Write-Host "3. Save it as: $cer"
    Read-Host 'Press Enter once the .cer is saved there'
    if (-not (Test-Path $cer)) { throw "Certificate not found at $cer" }
}

# Apple serves DER; accept PEM too.
& $openssl x509 -inform DER -in $cer -out $pem 2>$null
if ($LASTEXITCODE -ne 0) { Invoke-OpenSsl x509 -inform PEM -in $cer -out $pem }

$certModulus = & $openssl x509 -noout -modulus -in $pem
$keyModulus = & $openssl rsa -noout -modulus -in $key 2>$null
if ($certModulus -ne $keyModulus) { throw 'The downloaded certificate does not match distribution.key. Upload the .csr from this folder.' }

$subject = & $openssl x509 -noout -subject -in $pem
if ($subject -notmatch 'Apple Distribution|iPhone Distribution') {
    throw "Not an Apple Distribution certificate: $subject"
}

# 256 bits from the OS cryptographic RNG; PowerShell's random cmdlet is not cryptographically secure.
$passwordBytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($passwordBytes) } finally { $rng.Dispose() }
$password = [BitConverter]::ToString($passwordBytes).Replace('-', '')
$env:SOCCER_RADAR_P12_PASS = $password
try {
    # SHA1/3DES PBE keeps the .p12 importable by macOS `security` on CI runners.
    Invoke-OpenSsl pkcs12 -export -inkey $key -in $pem -out $p12 -name 'Apple Distribution' `
        -passout env:SOCCER_RADAR_P12_PASS -keypbe PBE-SHA1-3DES -certpbe PBE-SHA1-3DES -macalg sha1
    Invoke-OpenSsl pkcs12 -in $p12 -noout -passin env:SOCCER_RADAR_P12_PASS
} finally {
    Remove-Item Env:SOCCER_RADAR_P12_PASS -ErrorAction SilentlyContinue
}

if ($SkipSecretUpload) {
    Write-Host "Built and verified $p12 (secrets not uploaded)."
    return
}

[Convert]::ToBase64String([IO.File]::ReadAllBytes($p12)) |
    gh secret set APPLE_DISTRIBUTION_CERT_P12_BASE64 --env $Environment --repo $Repo
if ($LASTEXITCODE -ne 0) { throw 'Failed to set APPLE_DISTRIBUTION_CERT_P12_BASE64' }
$password | gh secret set APPLE_DISTRIBUTION_CERT_PASSWORD --env $Environment --repo $Repo
if ($LASTEXITCODE -ne 0) { throw 'Failed to set APPLE_DISTRIBUTION_CERT_PASSWORD' }

$passwordFile = Join-Path $WorkDir 'distribution.p12.password.txt'
Set-Content -Path $passwordFile -Value $password -NoNewline
Write-Host ''
Write-Host "Secrets set on the '$Environment' environment of $Repo."
Write-Host "Back up $p12 and $passwordFile in a password manager, then delete $WorkDir."
