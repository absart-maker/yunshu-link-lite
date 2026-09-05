# Bootstrap - Windows 运行环境检查与安装
# 用法: powershell -ExecutionPolicy Bypass -File scripts/bootstrap_windows.ps1
#
# 说明: 本项目完整运行需要 Python 3.10、FFmpeg、JDK 21、Maven、
#       MySQL 8+、Redis。本脚本仅做“缺失则用 winget 安装”，
#       MySQL/Redis 建议走 Docker Compose（见 docker-setup.sh）。

$ErrorActionPreference = "Stop"

function Install-IfMissing {
    param([string]$Name, [string]$Command, [string]$Package)
    $found = Get-Command $Command -ErrorAction SilentlyContinue
    if ($found) {
        Write-Host "[OK] $Name 已安装: $(& $Command --version 2>$null | Select-Object -First 1)"
    }
    else {
        Write-Host "[安装] $Name ($Package) ..."
        winget install --id $Package --accept-source-agreements --accept-package-agreements
    }
}

Install-IfMissing -Name "Python 3.10+" -Command "python" -Package "Python.Python.3.10"
Install-IfMissing -Name "FFmpeg" -Command "ffmpeg" -Package "Gyan.FFmpeg"
Install-IfMissing -Name "JDK 21" -Command "java" -Package "EclipseAdoptium.Temurin.21.JDK"
Install-IfMissing -Name "Maven" -Command "mvn" -Package "Apache.Maven"
Install-IfMissing -Name "Node.js" -Command "node" -Package "OpenJS.NodeJS.LTS"

Write-Host ""
Write-Host "接下来请在项目根目录执行:"
Write-Host "  cd main/xiaozhi-server"
Write-Host "  pip install -r requirements.txt"
Write-Host "  python -m engine.check"
Write-Host ""
Write-Host "提示: MySQL/Redis 推荐使用根目录 docker-setup.sh 或 "
Write-Host "       main/xiaozhi-server/docker-compose_all.yml 启动。"
Write-Host "       ESP32 硬件可选；无硬件时用 python -m engine.device_simulator 验收协议。"
