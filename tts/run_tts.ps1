#!/usr/bin/env pwsh
# TTS 程序启动脚本 (PowerShell 版本)
# 用于快速启动 TTS 主程序并验证图标显示

$scriptPath = $PSScriptRoot
Set-Location $scriptPath

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  TTS 工具集 - 启动程序 (已修复图标显示)  ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# 检查 Python 环境
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ 已找到 Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ 错误: 未找到 Python 环境" -ForegroundColor Red
    Read-Host "按 Enter 继续"
    exit 1
}

# 检查图标文件
Write-Host ""
Write-Host "📁 检查图标文件..." -ForegroundColor Yellow
$iconFiles = @("icon.ico", "icon.png", "icon_tb.ico")
foreach ($file in $iconFiles) {
    if (Test-Path $file) {
        $size = (Get-Item $file).Length
        Write-Host "  ✅ $file - $size bytes" -ForegroundColor Green
    } else {
        Write-Host "  ❌ $file - 未找到" -ForegroundColor Red
    }
}

# 检查是否需要生成图标
if (-not (Test-Path "icon.ico")) {
    Write-Host ""
    Write-Host "⚠️  未找到 icon.ico，尝试生成..." -ForegroundColor Yellow
    try {
        python generate_icon.py
        Write-Host "✅ 图标生成完成" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  图标生成失败，继续运行..." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "📋 启动检查项:" -ForegroundColor Cyan
Write-Host "  ✅ 检查窗口标题栏左上角的图标" -ForegroundColor Gray
Write-Host "  ✅ 检查 Windows 任务栏中的图标" -ForegroundColor Gray
Write-Host "  ✅ 按 Alt+Tab 查看窗口切换器中的图标" -ForegroundColor Gray
Write-Host "  ✅ 关闭程序后重启检查图标是否更新" -ForegroundColor Gray
Write-Host ""

Write-Host "🚀 启动 TTS 程序..." -ForegroundColor Green
Write-Host ""

# 启动程序
& python AYE_TTS_Main.pyw

# 程序结束后的提示
Write-Host ""
Write-Host "程序已关闭" -ForegroundColor Yellow
Read-Host "按 Enter 继续"
