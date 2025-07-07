from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import mysql.connector
import requests


# 主程式
def searchkey_crawler_main():
    print("開始訓練家爬蟲...")
    # 建立與資料庫的連線
    connection = mysql.connector.connect(host="127.0.0.1",
                                         port="3306",
                                         user="root",
                                         password="PokemonTCG",
                                         database="PTCG")

    chrome_path = "/home/ptcg/chrome-testing/chrome-linux64/chrome"
    chromedriver_path = "/home/ptcg/chrome-testing/chromedriver-linux64/chromedriver"

    options = Options()
    options.binary_location = chrome_path
    options.add_argument("--headless=new")
    options.add_argument('--window-size=1280,1024')
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-debugging-port=0")
    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=options)                                  

    # 打開訓練家網站
    driver.get("https://asia.pokemon-card.com/tw/card-search/")

    # 等待網頁載入搜尋按鈕
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "searchButton"))
    )

    # 按下搜尋
    search_button = driver.find_element(By.ID, "searchButton")
    search_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.ID, "searchButton"))
    )
    search_button.click()

    # 等待網頁載入
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#searchForm > div > div.resultHeader > "
                                                         "div.resultSummary > p.resultTotalPages"))
    )

    # 總共有幾頁
    total_page_element = driver.find_element(By.CSS_SELECTOR, "#searchForm > div > div.resultHeader > "
                                                              "div.resultSummary > p.resultTotalPages")
    total_page = extractNumber(total_page_element.text)

    # 爬蟲
    name_list = crawler(total_page, driver, connection)

    # 將資料新增至資料庫
    for card in name_list:
        connection.ping(reconnect=True)  # 確保資料庫連線正常
        with connection.cursor() as cursor:
            cursor.execute("INSERT IGNORE INTO `card`(search_key, from_where) VALUES(%s, %s);",
                        [card['search_key'], card['from_where']])

    # 關閉瀏覽器
    driver.quit()

    connection.ping(reconnect=True)  # 確保資料庫連線正常
    # 將資料提交至MySQL
    connection.commit()

    # 關閉與資料庫的連線
    connection.close()
    print("訓練家爬蟲完成，資料已更新至資料庫。")


def namefilter(name):
    # 將"噴火龍VMAX"排除，因為他已經退環境了
    if '噴火龍VMAX' in name:
        return False
    else:
        return True


# 將字串中數字擷取出來
def extractNumber(string):
    num_str = ''
    for ch in string:
        if isDigit(ch):
            num_str += ch

    if len(num_str) > 0:
        return int(num_str)
    else:
        return 0


# 是否為數字字元
def isDigit(ch):
    if '0' <= ch <= '9':
        return True
    else:
        return False


# 是否為球閃
def is_ball_shine(link):
    if "https://asia.pokemon-card.com/tw/card-search/detail/12" in link:
        num = link.split('12', 1)[1]
        num = int(num.replace('/', ''))
        if 319 <= num <= 462:
            return True
    return False


# 爬蟲
def crawler(last_page, driver, connection):
    alist = []  # search key + from where + image
    page = 1
    finish = False
    while page <= last_page and not finish:
        if page > 1:
            # 翻頁
            next_icon = driver.find_element(By.CLASS_NAME, "next")
            next_a = next_icon.find_element(By.TAG_NAME, "a")
            next_page_link = next_a.get_attribute("href")
            driver.get(next_page_link)

        while True:
            try:
                # 等待網頁載入
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "card"))
                )
                break
            except TimeoutException:
                # 等一下後重新整理
                time.sleep(5)
                driver.refresh()

        # 找到該頁所有卡片
        card_list = driver.find_element(By.CLASS_NAME, "list")
        cards = card_list.find_elements(By.CLASS_NAME, "card")

        for card in cards:
            # 取得每張卡片的連結
            card_a = card.find_element(By.TAG_NAME, "a")
            card_link = card_a.get_attribute("href")

            # 在分頁中開啟連結
            driver.execute_script(f"window.open('{card_link}');")
            driver.switch_to.window(driver.window_handles[1])

            while True:
                try:
                    # 等待網頁載入
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "cardDetail"))
                    )
                    break
                except TimeoutException:
                    # 等5秒後重新整理
                    time.sleep(5)
                    driver.refresh()

            # 取得卡片編號
            collector_num = driver.find_element(By.CLASS_NAME, "collectorNumber")
            if collector_num.text != "SV-P":            
                # 找到卡名資訊
                notclearname = driver.find_element(By.CLASS_NAME, "cardDetail")
                name = ""  # search key

                # 卡片出處
                expansionLinkColumn = driver.find_element(By.CLASS_NAME, "expansionLinkColumn")
                from_where = expansionLinkColumn.find_element(By.TAG_NAME, "a")
                card_from_where = from_where.text

                if namefilter(notclearname.text):  # 卡名篩選，將不要的卡排除
                    if '\n' in notclearname.text:  # 這張卡是寶可夢
                        # 去除卡名資訊中的進化型態
                        i = 0
                        for ch in notclearname.text:
                            if ch == '\n':
                                name = notclearname.text[i+1:]
                                break
                            i += 1
                    else:  # 非寶可夢卡
                        name = notclearname.text

                    # 刪除多餘的括號
                    if "[" in name:
                        start = 0
                        end = 0
                        for i in range(len(name)):
                            if name[i] == "[":
                                start = i

                            if name[i] == "]":
                                end = i
                                break

                        name = name[:start] + name[end + 1:]
                    elif "【" in name:
                        name = name.replace("【", "")
                        name = name.replace("】", "")
                    elif "<" in name:
                        name = name.replace("<", "")
                        name = name.replace(">", "")

                    # 連接卡片編號和卡名
                    name = collector_num.text + ' ' + name

                    # 非基本能量
                    if "基本" not in name or "能量" not in name:
                        # 檢查球閃
                        if is_ball_shine(card_link):
                            name = name + ' 球閃'

                        connection.ping(reconnect=True)  # 確保資料庫連線正常
                        with connection.cursor() as cursor:
                            # 檢查是否有重複資料
                            cursor.execute("SELECT * FROM `card` WHERE `search_key` = %s AND "
                                        "`from_where` = %s;", (name, card_from_where))
                            already_in_database = cursor.fetchone()
                        # 有重複資料，代表以前爬過了
                        if already_in_database:
                            print(f"{name} 已經在資料庫中了")
                            # 關閉分頁
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])
                            # 結束爬蟲
                            finish = True
                            break

                    # 卡圖
                    image = driver.find_element(By.CSS_SELECTOR, "body > main > div > div > section.imageColumn > "
                                                                "div > img")
                    img_url = image.get_attribute("src")
                    response = requests.get(img_url, timeout=10)
                    # card_image = io.BytesIO(response.content).getvalue()

                    # 存圖片
                    connection.ping(reconnect=True)  # 確保資料庫連線正常
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT * FROM `booster_pack` WHERE `from_where` = %s;", (card_from_where,))
                        result = cursor.fetchone()
                    if not result:
                        connection.ping(reconnect=True)  # 確保資料庫連線正常
                        with connection.cursor() as cursor:
                            cursor.execute("INSERT INTO `booster_pack`(from_where) VALUES(%s);",
                                        (card_from_where,))
                        connection.ping(reconnect=True)  # 確保資料庫連線正常
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT `id` FROM `booster_pack` WHERE `from_where` = %s;", (card_from_where,))
                            from_where_id = cursor.fetchone()[0]
                    else:
                        from_where_id = result[0]
                    
                    search_key_id = name.replace('/', '_').split()[0]
                    if '球閃' in name:
                        image_file_name = f"{search_key_id}+{from_where_id}-ball.jpg"
                    else:
                        image_file_name = f"{search_key_id}+{from_where_id}.jpg"
                    with open(f"/home/ptcg/PTCGHTML/official_card_image/{image_file_name}", "wb") as file:
                        file.write(response.content)

                    card_info = {
                        'search_key': name,  # 搜尋用關鍵字：<編號> <卡名>
                        'from_where': card_from_where  # 卡片出處
                    }

                    alist.append(card_info)  # 將卡片資訊加入list

            # 關閉分頁
            driver.close()
            driver.switch_to.window(driver.window_handles[0])

        # 頁碼加1
        page += 1
    return alist


# 執行主程式
# searchkey_crawler_main()
