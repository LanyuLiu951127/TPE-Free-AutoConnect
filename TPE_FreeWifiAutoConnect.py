import logging
import os
import sys
import time
import subprocess
import urllib.request
import threading

# 設定日誌等級為 INFO
# Set the logging level to INFO
log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "TPE_FreeWifiAutoConnect.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file_path, encoding='utf-8')
    ]
)

# =====================================================================
# 單一實體鎖 (Singleton Lock)：防止使用者重複點擊導致開啟多個守護行程
# =====================================================================
import msvcrt
lock_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "TPE_FreeWifiAutoConnect.lock")
try:
    # 必須保留檔案物件參照以維持鎖定狀態
    singleton_lock_file = open(lock_file_path, "w")
    msvcrt.locking(singleton_lock_file.fileno(), msvcrt.LK_NBLCK, 1)
except IOError:
    logging.warning("⚠️ 偵測到已有另一組守護行程正在系統背景執行中！")
    logging.warning("為避免多重連線互相衝突，本次啟動將自動攔截並退出。")
    sys.exit(0)
# =====================================================================

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
except ImportError:
    logging.error("未安裝 selenium 模組。請在終端機運行以下指令安裝：")
    logging.error("The 'selenium' module is not installed. Please run the following command to install it:")
    logging.error(">>> pip install selenium")
    sys.exit(1)

def check_internet():
    """
    檢查目前是否能夠正常存取網際網路。
    如果處於未登入的 TPE-Free 狀態，此要求會失敗或回傳重新導向，此時回傳 False。
    
    Checks if active internet connection is available.
    Returns False if disconnected or redirected by the captive portal.
    """
    try:
        # 使用 Google 輕量化的 204 網頁進行網路檢測
        # Use Google's lightweight generate_204 endpoint to test internet connectivity
        response = urllib.request.urlopen("http://clients3.google.com/generate_204", timeout=5)
        if response.getcode() == 204:
            return True
    except Exception:
        pass
    return False

# 全域變數以同步系統匣狀態與連線時間
current_status = "正常守護中"
tray_icon = None
wifi_connected_since = None
is_paused = False

# 防呆鎖 (Debounce Locks)
connect_lock = threading.Lock()
toggle_lock = threading.Lock()

def get_wifi_details():
    """
    透過 netsh wlan show interfaces 獲取當前 Wi-Fi 的連線狀態、SSID、收發速度與訊號強度。
    """
    rx_rate = "0"
    tx_rate = "0"
    signal = "0%"
    ssid = "未連線"
    connected = False
    try:
        res = subprocess.run("netsh wlan show interfaces", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = ""
        for encoding in ['cp950', 'utf-8', 'gbk']:
            try:
                output = res.stdout.decode(encoding, errors='ignore')
                if output.strip():
                    break
            except Exception:
                pass
        
        for line in output.splitlines():
            line_lower = line.lower()
            if "ssid" in line_lower and "bssid" not in line_lower:
                ssid = line.split(":", 1)[1].strip()
            elif "state" in line_lower or "狀態" in line:
                if "connected" in line_lower or "已連線" in line:
                    connected = True
            elif "receive rate" in line_lower or "接收速率" in line:
                rx_rate = line.split(":", 1)[1].strip()
            elif "transmit rate" in line_lower or "傳送速率" in line:
                tx_rate = line.split(":", 1)[1].strip()
            elif "signal" in line_lower or "訊號" in line:
                signal = line.split(":", 1)[1].strip()
    except Exception:
        pass
        
    return connected, ssid, rx_rate, tx_rate, signal

def is_wifi_connected_to_ssid(ssid="TPE-Free"):
    """
    檢查目前 Wi-Fi 網卡是否已成功連接至特定的 SSID（如 TPE-Free）。
    """
    connected, active_ssid, _, _, _ = get_wifi_details()
    return connected and (ssid.lower() in active_ssid.lower())

def tooltip_updater():
    """
    背景執行緒：每秒更新系統匣小圖示的懸停提示內容 (類似工作管理員的 4 行看板)
    """
    global current_status, wifi_connected_since, tray_icon, is_paused
    while True:
        try:
            if tray_icon:
                connected, ssid, rx_rate, tx_rate, signal = get_wifi_details()
                
                # 計算連線時間起點
                if connected and ssid == "TPE-Free":
                    if wifi_connected_since is None:
                        wifi_connected_since = time.time()
                else:
                    wifi_connected_since = None
                
                # 格式化連線時間
                if wifi_connected_since:
                    secs = int(time.time() - wifi_connected_since)
                    mins, secs = divmod(secs, 60)
                    hours, mins = divmod(mins, 60)
                    duration_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
                else:
                    duration_str = "--:--:--"
                
                # 組合 4 行精簡看板格式 (維持在 127 字元以內，符合 Windows 限制)
                tooltip_text = (
                    f"台北公眾 Wi-Fi 連線守護\n"
                    f"連線: {ssid} ({signal})\n"
                    f"速度: {rx_rate} / {tx_rate} Mbps\n"
                    f"時間: {duration_str} | {current_status}"
                )
                
                # 安全長度截斷
                if len(tooltip_text) > 125:
                    tooltip_text = tooltip_text[:122] + "..."
                    
                tray_icon.title = tooltip_text
        except Exception as e:
            logging.debug(f"更新提示資訊錯誤: {e}")
        time.sleep(1)

def on_reconnect(icon, item):
    global current_status, is_paused
    if is_paused:
        return
    current_status = "強制重連中..."
    logging.info("收到手動重連指令，開始連線驗證流程...")
    threading.Thread(target=connect_sequence, daemon=True).start()

def _toggle_pause_worker(icon):
    global is_paused, current_status
    
    # 防呆：確保切換程序不會被重複點擊平行觸發
    if not toggle_lock.acquire(blocking=False):
        logging.info("⚠️ 切換狀態處理中，已略過本次重複點擊...")
        return
        
    try:
        is_paused = not is_paused
        system_root = os.environ.get('SystemRoot', 'C:\\Windows')
        powershell_exe = os.path.join(system_root, 'System32\\WindowsPowerShell\\v1.0\\powershell.exe')
        
        if is_paused:
            current_status = "守護已暫停"
            icon.icon = create_wifi_icon_image(color=(150, 150, 150, 255))
            logging.info("守護行程已暫停，正在實體關閉 Windows Wi-Fi 網卡...")
            # 實體關閉 Windows Wi-Fi 網卡
            disable_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "disable_wifi.ps1")
            subprocess.run(f'"{powershell_exe}" -ExecutionPolicy Bypass -File "{disable_script}"', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            current_status = "正常守護中"
            icon.icon = create_wifi_icon_image(color=(0, 162, 232, 255))
            logging.info("守護行程已恢復，正在實體開啟 Windows Wi-Fi 網卡...")
            # 實體開啟 Windows Wi-Fi 網卡
            enable_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "enable_wifi.ps1")
            subprocess.run(f'"{powershell_exe}" -ExecutionPolicy Bypass -File "{enable_script}"', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # 立即觸發一次連線檢查
            threading.Thread(target=connect_sequence, daemon=True).start()
    finally:
        toggle_lock.release()

def toggle_pause(icon, item):
    threading.Thread(target=_toggle_pause_worker, args=(icon,), daemon=True).start()

def on_exit(icon, item):
    logging.info("使用者透過系統匣點擊結束，守護行程已關閉。")
    icon.stop()
    os._exit(0)

def create_wifi_icon_image(width=64, height=64, color=(0, 162, 232, 255)):
    from PIL import Image, ImageDraw
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    dc.ellipse([width//2 - 5, height - 15, width//2 + 5, height - 5], fill=color)
    dc.arc([width//2 - 15, height - 25, width//2 + 15, height - 5], start=210, end=330, fill=color, width=4)
    dc.arc([width//2 - 27, height - 37, width//2 + 27, height - 5], start=210, end=330, fill=color, width=4)
    dc.arc([width//2 - 39, height - 49, width//2 + 39, height - 5], start=210, end=330, fill=color, width=4)
    return image

def setup_tray():
    global tray_icon, is_paused
    try:
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError:
            logging.info("正在背景自動為您部署系統匣核心組件 (pystray, Pillow)...")
            import subprocess
            import sys
            subprocess.run([sys.executable, "-m", "pip", "install", "pystray", "Pillow"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            import pystray
            from PIL import Image, ImageDraw
            logging.info("背景核心組件部署完成！")

        image = create_wifi_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("台北公眾 Wi-Fi 自動連線", lambda: None, enabled=False),
            pystray.MenuItem("手動重新連線", on_reconnect),
            pystray.MenuItem(lambda text: "恢復守護行程 (啟用)" if is_paused else "暫停守護行程 (停用)", toggle_pause),
            pystray.MenuItem("完全結束程式", on_exit)
        )
        tray_icon = pystray.Icon("tpe_free_wifi", image, "台北公眾 Wi-Fi 自動連線", menu)
        
        # 啟動懸停提示每秒背景更新執行緒
        threading.Thread(target=tooltip_updater, daemon=True).start()
        
        tray_icon.run()
    except Exception as e:
        logging.error(f"系統匣圖示載入失敗: {e}")


def get_driver():
    """
    初始化並返回 Selenium WebDriver (優先使用 Chrome)。
    
    Initializes and returns a Selenium WebDriver (Chrome prioritized).
    """
    # 嘗試使用 Chrome
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--headless=new')  # 新版 Chromium 核心強制要求
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-position=-32000,-32000') # 終極隱藏技：將視窗移至螢幕外
        driver = webdriver.Chrome(options=options)
        return driver
    except Exception as e:
        logging.info(f"無法啟動 Chrome 瀏覽器，嘗試下一個瀏覽器。詳細原因: {e}")

    # 嘗試使用 Firefox
    try:
        options = webdriver.FirefoxOptions()
        options.add_argument('--headless')
        options.add_argument('--window-position=-32000,-32000')
        driver = webdriver.Firefox(options=options)
        return driver
    except Exception as e:
        logging.info(f"無法啟動 Firefox 瀏覽器，嘗試下一個瀏覽器。詳細原因: {e}")

    # 嘗試使用 Edge
    try:
        options = webdriver.EdgeOptions()
        options.add_argument('--headless')
        options.add_argument('--headless=new')  # 新版 Chromium 核心強制要求
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-position=-32000,-32000') # 終極隱藏技：將視窗移至螢幕外
        driver = webdriver.Edge(options=options)
        return driver
    except Exception as e:
        logging.error(f"無法初始化任何支援的瀏覽器 (Chrome / Firefox / Edge)。")
        raise e

def wait_for_wifi_connection(ssid="TPE-Free", timeout=15):
    """
    等待 Wi-Fi 網卡完成 SSID 連線並取得 IP。
    """
    global current_status
    logging.info(f"等待 Wi-Fi 網卡關聯至 SSID: {ssid}...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        elapsed = int(time.time() - start_time)
        current_status = f"配發 IP 中({timeout - elapsed}s)"
        try:
            res = subprocess.run("netsh wlan show interfaces", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output = ""
            # 多重編碼嘗試，防範解碼失敗
            for encoding in ['cp950', 'utf-8', 'gbk']:
                try:
                    output = res.stdout.decode(encoding, errors='ignore')
                    if output.strip():
                        break
                except Exception:
                    pass
            if ssid in output and ("connected" in output.lower() or "已連線" in output):
                logging.info(f"🎉 網卡已成功連線至 {ssid}！")
                time.sleep(3)  # 再額外等待 3 秒讓 DHCP 穩定取得 IP
                return True
        except Exception as e:
            logging.debug(f"連線偵測發生非預期錯誤: {e}")
        time.sleep(1)
    logging.warning(f"⚠️ 在 {timeout} 秒內未偵測到網卡完全連線至 {ssid}。將嘗試直接存取網頁...")
    return False

def connect_sequence():
    """
    執行連線並點擊同意條款的完整流程。
    """
    global current_status
    
    # 防呆：確保同一時間只有一個連線程序在執行
    if not connect_lock.acquire(blocking=False):
        logging.info("⚠️ 連線程序已在執行中，已略過本次重複觸發。")
        return
        
    driver = None
    try:
        # 1. 確保 Wi-Fi 軟體開關已開啟 (免系統管理員權限)
        current_status = "啟用 Wi-Fi 網卡..."
        logging.info("正在自動啟用 Wi-Fi 軟體開關...")
        system_root = os.environ.get('SystemRoot', 'C:\\Windows')
        powershell_exe = os.path.join(system_root, 'System32\\WindowsPowerShell\\v1.0\\powershell.exe')
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "enable_wifi.ps1")
        powershell_cmd = f'"{powershell_exe}" -ExecutionPolicy Bypass -File "{script_path}"'
        subprocess.run(powershell_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(2)
        
        # 2. 連接 TPE-Free Wi-Fi 熱點
        current_status = "連線 SSID 中..."
        logging.info("正在嘗試連接 TPE-Free Wi-Fi SSID...")
        subprocess.run(
            'netsh wlan connect name="TPE-Free"', 
            shell=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        
        # 2.1 主動等待網卡關聯與 DHCP 分配 IP 完成
        wait_for_wifi_connection("TPE-Free", timeout=15)
        
        # 2.2 啟動瀏覽器
        current_status = "啟動瀏覽器..."
        driver = get_driver()
        # 存取 Windows 官方的網路探測重導向網址，這百分之百會被 Captive Portal 強制攔截並帶入完整的 MAC & IP 參數
        url = "http://www.msftconnecttest.com/redirect"
        current_status = "載入認證網頁..."
        logging.info(f"正在透過 Windows 探測請求觸發 TPE-Free 重導向頁面: {url}")
        driver.get(url)

        # 3. 等待同意按鈕出現 (支援 ID, XPath 多重匹配防錯)
        current_status = "等待同意按鈕..."
        logging.info("等待同意條款按鈕...")
        agree_button = None
        for locator in [
            (By.ID, "btnContinue"),
            (By.XPATH, "//input[contains(@value, '同意')]"),
            (By.XPATH, "//button[contains(text(), '同意')]"),
            (By.XPATH, "//*[contains(text(), '開始上網')]")
        ]:
            try:
                agree_button = WebDriverWait(driver, 8).until(
                    EC.element_to_be_clickable(locator)
                )
                if agree_button:
                    logging.info(f"成功定位同意按鈕：{locator}")
                    break
            except TimeoutException:
                continue

        if not agree_button:
            raise TimeoutException("未能定位到任何同意條款按鈕")
        
        # 4. 點擊按鈕 (加入 JavaScript 點擊做為備用方案)
        current_status = "點擊同意按鈕..."
        try:
            agree_button.click()
            logging.info("已完成一般實體點擊！")
        except WebDriverException:
            logging.info("一般點擊受到干擾，已自動切換為 JavaScript 強制點擊...")
            driver.execute_script("arguments[0].click();", agree_button)
            logging.info("已使用 JavaScript 強制完成同意按鈕點擊！")
            
        current_status = "連線成功！"
        logging.info("🎉 TPE-Free 自動連線驗證完成！網路已成功開通！")

    except TimeoutException:
        current_status = "定位按鈕逾時"
        logging.warning("等待或定位同意條款按鈕時發生逾時。請確認周遭是否有有效的 TPE-Free 熱點訊號。")
    except WebDriverException as e:
        current_status = "瀏覽器異常"
        if "ERR_NAME_NOT_RESOLVED" in str(e):
            logging.warning("網頁位址解析失敗 (ERR_NAME_NOT_RESOLVED)。可能尚未進入 TPE-Free 訊號範圍，將於下個週期重新偵測。")
        else:
            logging.error(f"WebDriver 發生異常錯誤: {e}")
    except Exception as e:
        current_status = "連線錯誤"
        logging.error(f"發生未預期的錯誤: {e}")
    finally:
        if driver:
            driver.quit()
            logging.info("瀏覽器已關閉。")
        connect_lock.release()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="TPE-Free captive portal auto-login background daemon.")
    parser.add_argument("--force", action="store_true", help="Force login sequence once at startup regardless of active internet connection.")
    args = parser.parse_args()

    # 啟動系統匣圖示執行緒 (無聲整合至 Windows 系統匣收納區)
    threading.Thread(target=setup_tray, daemon=True).start()

    logging.info("=" * 60)
    logging.info("🚀 台北公眾 Wi-Fi 背景自動連線守護行程 (Daemon) 已啟動！")
    logging.info("偵測頻率：每 30 秒自動檢測一次網路狀態")
    logging.info("運作機制：當偵測到斷網或需要重新認證時，會自動在背景連接並完成開通。")
    logging.info("=" * 60)
    
    global current_status
    # 首次啟動先進行一次檢測連線
    if args.force:
        logging.info("【強制連線模式】忽略網路狀態，直接強制執行 TPE-Free 連線程序...")
        current_status = "強制連線中..."
        connect_sequence()
        current_status = "正常守護中"
    elif not is_wifi_connected_to_ssid("TPE-Free"):
        logging.info("首次啟動檢測：偵測到未連線至 TPE-Free SSID，執行連線程序...")
        current_status = "連線登入中..."
        connect_sequence()
        current_status = "正常守護中"
    elif not check_internet():
        logging.info("首次啟動檢測：已連上 SSID 但網路尚未開通，執行登入程序...")
        current_status = "驗證開通中..."
        connect_sequence()
        current_status = "正常守護中"
    else:
        logging.info("首次啟動檢測：目前網路正常，守護行程持續監控中...")
        current_status = "正常守護中"
        
    while True:
        try:
            time.sleep(30)
            
            # 定期同步系統匣狀態
            if tray_icon:
                tray_icon.title = f"台北公眾 Wi-Fi 自動連線\n狀態: {current_status}"

            # 若使用者點擊暫停，則跳過網路偵測與自動連線
            if is_paused:
                continue

            # 1. 優先檢查 Wi-Fi 是否已連接至 TPE-Free (即使此時有線網路是通的，也強制連線以符合測試需求)
            if not is_wifi_connected_to_ssid("TPE-Free"):
                logging.info("⚠️ 偵測到 Wi-Fi 未連線至 TPE-Free！開始執行自動連線與登入...")
                current_status = "自動連線中..."
                connect_sequence()
                current_status = "正常守護中"
                continue
                
            # 2. 如果已連接 SSID，但無法實際存取網路 (如 2 小時過期斷網)
            if not check_internet():
                logging.info("⚠️ 偵測到網路已中斷或需要重新開通！開始執行連線驗證程序...")
                current_status = "重新驗證中..."
                connect_sequence()
                current_status = "正常守護中"
                continue
                
            current_status = "正常守護中"
            
        except KeyboardInterrupt:
            logging.info("守護行程已手動停止。")
            break
        except Exception as e:
            logging.error(f"守護行程循環發生異常: {e}")

if __name__ == "__main__":
    main()