import os
import sys
import subprocess
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# 定義路徑 / Define paths
WORKSPACE_DIR = r"c:\Users\tpechra\Desktop\TPE-FREE"
STARTUP_DIR = os.path.join(os.environ['APPDATA'], r"Microsoft\Windows\Start Menu\Programs\Startup")
DESKTOP_DIR = os.path.join(os.environ['USERPROFILE'], 'Desktop')

# 1. 產生 TPE-Free 的 Wi-Fi 設定檔 XML
wifi_profile_xml = """<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>TPE-Free</name>
    <SSIDConfig>
        <SSID>
            <name>TPE-Free</name>
        </SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>auto</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>open</authentication>
                <encryption>none</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
        </security>
    </MSM>
</WLANProfile>
"""

def setup():
    logging.info("開始設定開機自動開啟並守護連線 TPE-Free...")
    
    # 確保工作目錄存在
    if not os.path.exists(WORKSPACE_DIR):
        os.makedirs(WORKSPACE_DIR)
        
    xml_path = os.path.join(WORKSPACE_DIR, "TPE-Free.xml")
    
    # 寫入 XML 檔案
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(wifi_profile_xml)
    logging.info(f"1. 已產生 Wi-Fi 設定檔: {xml_path}")
    
    # 將設定檔匯入 Windows 系統
    try:
        subprocess.run(
            f'netsh wlan add profile filename="{xml_path}"',
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logging.info("2. 已成功將 「TPE-Free」 Wi-Fi 設定檔匯入 Windows 系統！")
    except subprocess.CalledProcessError as e:
        logging.error(f"無法匯入 Wi-Fi 設定檔: {e.stderr.decode('cp950', errors='ignore')}")
        
    # 3. 建立執行連線的 Batch 檔案 (.bat)
    bat_path = os.path.join(WORKSPACE_DIR, "run_tpe_wifi.bat")
    bat_content = f"""@echo off
:: 切換至工作目錄
cd /d "{WORKSPACE_DIR}"

:: 嘗試將 Wi-Fi 軟體開關切換為「開啟」 (免系統管理員權限)
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -ExecutionPolicy Bypass -File "{WORKSPACE_DIR}\enable_wifi.ps1" >nul 2>&1

:: 自動連接到 TPE-Free 熱點
netsh wlan connect name="TPE-Free" >nul 2>&1

:: 等待 8 秒讓電腦完成 Wi-Fi 關聯與 IP 取得
timeout /t 8 /nobreak >nul

:: 執行 Python 自動守護連線腳本 (優先使用虛擬環境)
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" TPE_FreeWifiAutoConnect.py
) else (
    python TPE_FreeWifiAutoConnect.py
)
"""
    with open(bat_path, "w", encoding="cp950") as f:
        f.write(bat_content)
    logging.info(f"3. 已產生啟動批次檔: {bat_path}")

    # 4. 在 Windows 啟動資料夾 (Startup) 建立開機自動啟動的靜音 VBS 腳本 (0 視窗完全靜默背景執行)
    # 刪除舊的捷徑檔案避免殘留
    old_startup_lnk = os.path.join(STARTUP_DIR, "TPE_Free_OnStartup.lnk")
    old_desktop_lnk = os.path.join(DESKTOP_DIR, "啟動台北公眾WiFi自動連線.lnk")
    for old_file in [old_startup_lnk, old_desktop_lnk]:
        if os.path.exists(old_file):
            try:
                os.remove(old_file)
            except Exception:
                pass

    startup_vbs_path = os.path.join(STARTUP_DIR, "TPE_Free_OnStartup.vbs")
    startup_vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd.exe /c ""{bat_path}""", 0, False
'''
    with open(startup_vbs_path, "w", encoding="utf-8") as f:
        f.write(startup_vbs_content)
    logging.info("4. 已成功將開機自動連線靜音腳本 (.vbs) 新增至「開機啟動資料夾」！")
    logging.info(f"   路徑: {startup_vbs_path}")

    # 5. 在「桌面」建立手動啟動的靜音捷徑 (.vbs)
    desktop_vbs_path = os.path.join(DESKTOP_DIR, "啟動台北公眾WiFi自動連線.vbs")
    desktop_vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd.exe /c ""{bat_path}""", 0, False
'''
    with open(desktop_vbs_path, "w", encoding="utf-8") as f:
        f.write(desktop_vbs_content)
    logging.info("5. 已成功在「桌面」建立【啟動】靜音捷徑 (.vbs)！")
    logging.info(f"   路徑: {desktop_vbs_path}")

    # 6. 在「桌面」建立停止連線守護行程的批次檔 (.bat)
    desktop_stop_path = os.path.join(DESKTOP_DIR, "停止台北公眾WiFi自動連線.bat")
    desktop_stop_content = f"""@echo off
echo 正在停止「台北公眾 Wi-Fi 自動連線」背景守護行程...
"%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "Get-CimInstance Win32_Process -Filter \\"CommandLine like '%%TPE_FreeWifiAutoConnect.py%%'\\" | Foreach-Object {{ Stop-Process -Id $_.ProcessId -Force }}" >nul 2>&1
echo 已成功停止背景守護行程！
pause
"""
    with open(desktop_stop_path, "w", encoding="cp950") as f:
        f.write(desktop_stop_content)
    logging.info("6. 已成功在「桌面」建立【停止】捷徑！")
    logging.info(f"   路徑: {desktop_stop_path}")
    
    logging.info("=" * 50)
    logging.info("🎉 自動化守護系統設定完成！這台電腦現在擁有以下超能力：")
    logging.info("  1. 開機/登入時：自動在背景無聲開啟 Wi-Fi、連上 TPE-Free 並開通上網。")
    logging.info("  2. 連續監控：每 30 秒自動偵測網路，若 2 小時後斷線，會立即在後台自動重連！")
    logging.info("  3. 桌面控制：")
    logging.info("     - 雙擊桌面「啟動台北公眾WiFi自動連線」隨時可在背景啟動守護行程。")
    logging.info("     - 雙擊桌面「停止台北公眾WiFi自動連線」可立即關閉該背景程序。")
    logging.info("=" * 50)

if __name__ == "__main__":
    setup()
