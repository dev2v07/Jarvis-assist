param(
  [string]$Provider = "openai",
  [string]$ApiKey = "",
  [string]$Model = "gpt-4o-mini",
  [string]$BaseUrl = "https://api.openai.com/v1"
)

$cfgDir = Join-Path $env:APPDATA "ProjectHel"
New-Item -ItemType Directory -Force -Path $cfgDir | Out-Null
$envFile = Join-Path $cfgDir ".env"

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
  $secure = Read-Host "Введите API ключ" -AsSecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try {
    $ApiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
  }
}

$existing = @{}
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    if ($_ -match '=') {
      $k,$v = $_ -split '=',2
      $existing[$k.Trim()] = $v.Trim()
    }
  }
}

$existing['HEL_LLM_PROVIDER'] = $Provider
$existing['HEL_OPENAI_BASE_URL'] = $BaseUrl
$existing['HEL_OPENAI_MODEL'] = $Model
$existing['HEL_OPENAI_API_KEY'] = $ApiKey

$ordered = @(
  'HEL_ENV','HEL_LOG_LEVEL','HEL_API_HOST','HEL_API_PORT',
  'HEL_LLM_PROVIDER','HEL_OLLAMA_BASE_URL','HEL_OLLAMA_MODEL',
  'HEL_OPENAI_BASE_URL','HEL_OPENAI_MODEL','HEL_OPENAI_API_KEY',
  'HEL_LLM_REQUEST_TIMEOUT','HEL_LLM_MAX_RETRIES',
  'HEL_NETWORK_REQUEST_TIMEOUT','HEL_NETWORK_MAX_RETRIES',
  'HEL_RETRY_BACKOFF_SECONDS','HEL_WORKSPACE_DIR','HEL_DATA_HOME','HEL_LOG_DIR'
)
$lines = @('# Project Hel runtime configuration')
foreach ($key in $ordered) {
  if ($existing.ContainsKey($key)) { $lines += "$key=$($existing[$key])" }
}
foreach ($item in $existing.GetEnumerator() | Sort-Object Name) {
  if ($ordered -notcontains $item.Name) { $lines += "$($item.Name)=$($item.Value)" }
}
Set-Content -Path $envFile -Value $lines -Encoding UTF8
Write-Host "Ключ сохранён в $envFile"
