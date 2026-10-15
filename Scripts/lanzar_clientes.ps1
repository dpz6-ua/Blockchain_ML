# ==============================================================================
# Script de PowerShell para automatizar los Clientes en Windows 11 (PC 2)
# ==============================================================================

param(
    [string]$Exp = "E3",
    [int]$Runs = 3,
    [string]$ServerIp = "192.168.1.53"
)

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "ORQUESTADOR DE CLIENTES FEDERADOS (PC 2 - Windows 11)" -ForegroundColor Cyan
Write-Host "Experimento:      $Exp"
Write-Host "Total de runs:    $Runs"
Write-Host "IP del Servidor:  $ServerIp"
Write-Host "==============================================================================" -ForegroundColor Cyan

$usa_bc = $true
if ($Exp -match "^E[23]" -or $Exp -match "NO") {
    $usa_bc = $false
}

for ($run = 1; $run -le $Runs; $run++) {
    Write-Host ""
    Write-Host "------------------------------------------------------------------------------" -ForegroundColor Yellow
    Write-Host ">> [CLIENTES] Iniciando Ejecución $run de $Runs para $Exp" -ForegroundColor Yellow
    Write-Host "------------------------------------------------------------------------------" -ForegroundColor Yellow

    if ($usa_bc) {
        $script_cliente = "client.py"
    } else {
        $script_cliente = "client_sin_bc.py"
    }

    Write-Host "Lanzando Cliente 2 y Cliente 3 en paralelo contra $ServerIp:8081..."
    
    $p2 = Start-Process python -ArgumentList "$script_cliente --member 2 --exp $Exp --run $run --server-ip $ServerIp" -PassThru -NoNewWindow
    $p3 = Start-Process python -ArgumentList "$script_cliente --member 3 --exp $Exp --run $run --server-ip $ServerIp" -PassThru -NoNewWindow

    # Esperar a que ambos clientes completen sus 30 rondas
    Write-Host "Entrenando modelo federado... Esperando finalización del Run $run..."
    $p2.WaitForExit()
    $p3.WaitForExit()

    Write-Host ">> Run $run finalizado con éxito en ambos clientes." -ForegroundColor Green
    Write-Host "Pausa de 5 segundos antes del siguiente run..."
    Start-Sleep -Seconds 5
}

Write-Host ""
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host "¡Todas las ejecuciones de los clientes ($Exp) han finalizado!" -ForegroundColor Green
Write-Host "Copia la carpeta Metricas de este equipo a la Estación 1 para consolidar." -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Green

