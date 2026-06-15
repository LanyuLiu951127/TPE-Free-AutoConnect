# disable_wifi.ps1
# 專為 Windows PowerShell 5.1 設計的非同步 WinRT Wi-Fi 關閉腳本 (免系統管理員權限)

try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    
    $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { 
        $_.Name -eq 'AsTask' -and 
        $_.GetParameters().Count -eq 1 -and 
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' 
    })[0]

    function Await-WinRt {
        param($WinRtTask, $ResultType)
        $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
        $netTask = $asTask.Invoke($null, @($WinRtTask))
        $netTask.Wait(-1) | Out-Null
        return $netTask.Result
    }

    [Windows.Devices.Radios.Radio, Windows.System.Devices, ContentType=WindowsRuntime] | Out-Null
    [Windows.Devices.Radios.RadioAccessStatus, Windows.System.Devices, ContentType=WindowsRuntime] | Out-Null

    $radios = Await-WinRt ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
    $wifi = $radios | Where-Object { $_.Kind -eq 1 }
    
    if ($wifi) {
        [Windows.Devices.Radios.RadioState, Windows.System.Devices, ContentType=WindowsRuntime] | Out-Null
        # 2 = RadioState.Off
        $status = Await-WinRt ($wifi.SetStateAsync(2)) ([Windows.Devices.Radios.RadioAccessStatus])
        Write-Host "Wi-Fi radio successfully disabled."
    } else {
        Write-Warning "No Wi-Fi adapter found."
    }
} catch {
    Write-Warning "Failed to disable Wi-Fi radio: $_"
}
