$stackFile = "stack.yml"
$port = 31112
$configFiles = Get-ChildItem -Path "." -Filter "yl-*.txt"

foreach ($file in $configFiles) {
    Write-Host "🚀 Processing $($file.Name)..."

    $lines = Get-Content $file.FullName
    $hostLine = $lines | Where-Object { $_ -like "Host:*" }
    $userLine = $lines | Where-Object { $_ -like "Username:*" }
    $passLine = $lines | Where-Object { $_ -like "Password:*" }

    $hostName = $hostLine -replace "Host:\s*", ""
    $user = $userLine -replace "Username:\s*", ""
    $pass = $passLine -replace "Password:\s*", ""

    if (!$hostName -or !$user -or !$pass) {
        Write-Warning "⚠️ Missing info in $($file.Name), skipping."
        continue
    }

    $gateway = "http://$hostName`:$port"
    Write-Host "🌐 Deploying to $gateway with user '$user'"

    $env:OPENFAAS_USERNAME = $user
    $env:OPENFAAS_PASSWORD = $pass

    faas-cli login --gateway $gateway --username $user --password $pass

    faas-cli deploy -f $stackFile --gateway $gateway

    Write-Host "✅ Done with $hostName"
    Write-Host "-------------------------------------`n"
}
