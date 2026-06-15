# 📡 TPE-Free Wi-Fi Auto Connect Daemon

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)
![Selenium](https://img.shields.io/badge/Selenium-4.x-green?logo=selenium)
![Platform](https://img.shields.io/badge/OS-Windows_11-0078D6?logo=windows)
![License](https://img.shields.io/badge/License-MIT-blue.svg)

**TPE-Free Wi-Fi Auto Connect Daemon** 是一個專為 Windows 設計的「台北公眾區免費無線上網 (TPE-Free)」自動連線守護程式。
它能常駐於系統背景，徹底免除使用者必須手動打開瀏覽器、點擊同意條款的繁瑣步驟，實現真正的「零感連線」。

---

## ✨ 核心特色 (Key Features)

- 🤖 **完全自動化 (Zero-Click Login)**: 透過 Selenium 4 自動完成 Captive Portal 網頁導向與登入驗證。
- 📊 **精緻系統匣看板 (Mini Dashboard)**: 在工作列右下角的 Wi-Fi 圖示懸停，即可即時查看連線 SSID、訊號強度、即時上/下傳速度與連線經過時間。
- 🔌 **硬體級網卡連動 (Hardware Sync)**: 獨家結合 Windows Runtime (WinRT) API，系統匣右鍵選單的「暫停/啟用」能直接實體開關 Windows Wi-Fi 網卡。
- 👻 **終極無頭模式 (Ultimate Headless)**: 結合 `--headless=new` 與超邊界視窗座標隱藏技術，支援 Chrome/Edge/Firefox，保證 100% 靜音背景執行，絕不彈出干擾視窗。
- 🛡️ **強健的守護機制 (Robust Daemon)**: 包含單一實體鎖 (Singleton Lock) 防止程式多開，以及智慧偵測 2 小時強制斷線並自動重連。

---

## 🚀 快速開始 (Quick Start)

### 1. 環境需求 (Prerequisites)
- Windows 10 / Windows 11
- Python 3.8+ 

### 2. 安裝與初始化 (Installation)
1. 下載或 Clone 此專案到您的電腦。
2. 雙擊執行目錄中的 `Setup_AutoConnect.py` (或透過終端機執行 `python Setup_AutoConnect.py`)。
3. 程式會自動為您：
   - 建立 Python 虛擬環境 (`.venv`)
   - 安裝所需依賴 (`selenium`, `pystray`, `Pillow`)
   - 產生桌面的啟動/停止捷徑
   - 自動寫入 Windows 開機啟動登錄檔 (可選)

### 3. 一鍵執行 (Usage)
- 🟢 **啟動守護程式**：雙擊桌面上的 **「啟動台北公眾WiFi自動連線.vbs」**。程式將無聲無息地啟動，並在系統匣出現科技藍 Wi-Fi 小圖示。
- 🔴 **停止守護程式**：雙擊桌面上的 **「停止台北公眾WiFi自動連線.bat」**，將徹底清除背景進程。

### 4. 搬移至其他電腦 (Migration)
當您將此專案資料夾複製到另一台電腦，或是更換磁碟機路徑時，**請勿直接點擊舊的捷徑**。
因 Python 的虛擬環境與捷徑依賴「絕對路徑」，換電腦後請依照以下步驟重置環境：
1. 將整個專案資料夾複製到新電腦。
2. 開啟終端機 (PowerShell / CMD) 進入該資料夾，並執行 `python Setup_AutoConnect.py`。
3. 腳本會自動為您綁定新電腦的路徑、重建虛擬環境，並產生全新的專屬桌面捷徑。接著就能直接一鍵啟動了！

---

## 🎛️ 系統匣操作指南 (System Tray Controls)

對著右下角系統匣的藍色 Wi-Fi 圖示點擊 **右鍵**，可執行以下操作：
* **手動重新連線**：強制觸發一次 TPE-Free 認證流程。
* **暫停守護行程 (停用)**：圖示變為灰階，停止背景監控，並 **實體關閉** Windows 系統的 Wi-Fi 網卡。
* **恢復守護行程 (啟用)**：圖示恢復藍色，**實體開啟** Windows Wi-Fi 網卡，並立刻開始自動連線。
* **完全結束程式**：安全退出守護程式並釋放資源。

---

## 📂 專案結構 (Project Structure)

```text
├── TPE_FreeWifiAutoConnect.py   # 核心守護程式 (包含系統匣UI與連線邏輯)
├── Setup_AutoConnect.py         # 環境與依賴自動安裝腳本
├── enable_wifi.ps1              # WinRT 實體開啟網卡腳本 (無須管理員權限)
├── disable_wifi.ps1             # WinRT 實體關閉網卡腳本 (無須管理員權限)
├── 啟動台北公眾WiFi自動連線.vbs    # 背景靜默啟動器
└── 停止台北公眾WiFi自動連線.bat    # 背景進程清理器
```

---

## ⚠️ 注意事項 (Notes)
- **瀏覽器支援**：本程式會依照順序自動尋找系統中的 Chrome、Firefox 或 Edge 核心，您無須手動下載任何 Driver。
- **免責聲明**：本程式僅為輔助自動點擊官方免費條款之用，請遵守臺北公眾區免費無線上網服務規章。
