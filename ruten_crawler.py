from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service
import time
import mysql.connector
import datetime
import numpy as np


# 主程式
def ruten_crawler_main():
    print("開始執行ruten爬蟲")
    # 建立與資料庫的連線
    connection = mysql.connector.connect(host="127.0.0.1",
                                         port="3306",
                                         user="root",
                                         password="PokemonTCG",
                                         database="PTCG")
                                         
    # 初始化瀏覽器
    driver = init_browser()  
    
    # 設定時區
    tzone = datetime.timezone(datetime.timedelta(hours=8))

    # 現在日期
    date_now = datetime.datetime.now(tz=tzone).strftime('%Y-%m-%d')

    """connection.ping(reconnect=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT `search_key`, `from_where` FROM `product` WHERE `update_date` = %s;", (date_now,))
        done_result = cursor.fetchall()"""

    # 從資料庫取得search_key和from_where
    connection.ping(reconnect=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT `search_key`, `from_where`, `full_name` FROM `card`;")
        all_result = cursor.fetchall()

    count = 0
    for one_result in all_result:
        search_key = one_result[0]
        from_where = one_result[1]
        full_name = one_result[2]
        """if (search_key, from_where) in done_result:
            continue  # 已經爬過了"""
        if count == 100:
            driver.quit()
            driver = init_browser()
            count = 0
        count += 1
        products_price, no_result = crawler(search_key, full_name, driver, connection)
        has_result = not no_result

        # 刪除舊資料
        connection.ping(reconnect=True)
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM `product` WHERE `update_date` <> %s"
                           " AND `search_key` = %s AND `from_where` = %s;", (date_now, search_key, from_where))
        connection.ping(reconnect=True)
        connection.commit()  # 將資料提交至MySQL

        # 插入新資料至product
        connection.ping(reconnect=True)
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO `product`(search_key, from_where, update_date) VALUES(%s, %s, %s);",
                           (search_key, from_where, date_now))

        # 插入資料至product_history 若已存在就忽略不插入
        connection.ping(reconnect=True)
        with connection.cursor() as cursor:
            cursor.execute("INSERT IGNORE INTO `product_history`(search_key, from_where) VALUES(%s, %s);",
                           (search_key, from_where))

        # 插入資料至product_week
        connection.ping(reconnect=True)
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO `product_week`(search_key, from_where, price_date)"
                           " VALUES(%s, %s, %s);", (search_key, from_where, date_now))

        if has_result:
            # 去除掉缺貨所以把價格設的很高的商品
            product_num = len(products_price)
            if product_num == 1:  # 只有一個樣本，使用固定門檻法
                if products_price[0] >= 10000:
                    filtered_products_price = []
                else:
                    filtered_products_price = products_price
            elif 1 < product_num <= 5:  # 樣本數過少，使用排除最大值法
                filtered_products_price = sorted(products_price)[:-1]
            else:  # 樣本數足夠，使用iqr法
                q1 = np.percentile(products_price, 25)
                q3 = np.percentile(products_price, 75)
                iqr = q3 - q1
                upper_bound = q3 + 1.5 * iqr
                filtered_products_price = [price for price in products_price if price <= upper_bound]

            if len(filtered_products_price) > 0:
                # 計算中位數和第一第三四分位數
                q1 = np.percentile(filtered_products_price, 25)
                median = np.percentile(filtered_products_price, 50)
                q3 = np.percentile(filtered_products_price, 75)
                highest = max(filtered_products_price)
                lowest = min(filtered_products_price)
            else:
                q1 = 0
                median = 0
                q3 = 0
                highest = 0
                lowest = 0

            # 將資料更新至product_week
            connection.ping(reconnect=True)
            with connection.cursor() as cursor:
                cursor.execute("UPDATE `product_week` SET `q1` = %s, `median` = %s, `q3` = %s, `highest` = %s, `lowest` = %s"
                               " WHERE `price_date` = %s AND `search_key` = %s AND `from_where` = %s;",
                               (q1, median, q3, highest, lowest, date_now, search_key, from_where))

            # 對每個商品價格做計數
            for price in filtered_products_price:
                # 計算商品價格的區間
                start = ((price - 1) // 10) * 10 + 1
                end = start + 9
                price_range = str(start) + "~" + str(end)

                # 取得product的columns名稱
                connection.ping(reconnect=True)
                with connection.cursor() as cursor:
                    cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'product';")
                    product_columns = cursor.fetchall()

                # 檢查product中所有column名稱
                no_column = True
                for column in product_columns:
                    # product中有跟price_range一樣名稱的column
                    column_name = column[0]
                    if column_name == price_range:
                        #  取得該column中的值
                        connection.ping(reconnect=True)
                        with connection.cursor() as cursor:
                            cursor.execute(f"SELECT `{column_name}` FROM `product` WHERE `search_key` = %s AND"
                                           f" `from_where` = %s;", (search_key, from_where))
                            result = cursor.fetchone()
                        if result[0] is None:  # 該column原本沒有值
                            connection.ping(reconnect=True)
                            with connection.cursor() as cursor:
                                cursor.execute(f"UPDATE `product` SET `{column_name}` = 1 WHERE"
                                               f" `search_key` = %s AND `from_where` = %s;", (search_key, from_where))
                        else:  # 該column原本就有值
                            # 直接將該column的值+1
                            connection.ping(reconnect=True)
                            with connection.cursor() as cursor:
                                cursor.execute(f"UPDATE `product` SET `{column_name}` = `{column_name}` + 1 WHERE"
                                               f" `search_key` = %s AND `from_where` = %s;", (search_key, from_where))
                        no_column = False
                        break

                # product中沒有跟price_range一樣名稱的column
                if no_column:
                    # 新增一個名稱叫price_range的column
                    connection.ping(reconnect=True)
                    with connection.cursor() as cursor:
                        cursor.execute(f"ALTER TABLE `product` ADD COLUMN `{price_range}` INT;")

                    # 將該column的值設為1
                    connection.ping(reconnect=True)
                    with connection.cursor() as cursor:
                        cursor.execute(f"UPDATE `product` SET `{price_range}` = 1"
                                       f" WHERE `search_key` = %s AND `from_where` = %s;", (search_key, from_where))

                # 取得product_history的columns名稱
                connection.ping(reconnect=True)
                with connection.cursor() as cursor:
                    cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS"
                                   " WHERE TABLE_NAME = 'product_history';")
                    history_columns = cursor.fetchall()

                # 檢查product_history中所有column名稱
                no_column = True
                for column in history_columns:
                    # product_history中有跟price_range一樣名稱的column
                    column_name = column[0]
                    if column_name == price_range:
                        #  取得該column中的值
                        connection.ping(reconnect=True)
                        with connection.cursor() as cursor:
                            cursor.execute(f"SELECT `{column_name}` FROM `product_history` WHERE `search_key` = %s AND"
                                           f" `from_where` = %s;", (search_key, from_where))
                            result = cursor.fetchone()
                        if result[0] is None:  # 該column原本沒有值
                            connection.ping(reconnect=True)
                            with connection.cursor() as cursor:
                                cursor.execute(f"UPDATE `product_history` SET `{column_name}` = 1 WHERE"
                                               f" `search_key` = %s AND `from_where` = %s;", (search_key, from_where))
                        else:  # 該column原本就有值
                            # 直接將該column的值+1
                            connection.ping(reconnect=True)
                            with connection.cursor() as cursor:
                                cursor.execute(f"UPDATE `product_history` SET `{column_name}` = `{column_name}` + 1"
                                               f" WHERE `search_key` = %s AND `from_where` = %s;",
                                               (search_key, from_where))
                        no_column = False
                        break

                # product_history中沒有跟price_range一樣名稱的column
                if no_column:
                    # 新增一個名稱叫price_range的column
                    connection.ping(reconnect=True)
                    with connection.cursor() as cursor:
                        cursor.execute(f"ALTER TABLE `product_history` ADD COLUMN `{price_range}` INT;")

                    # 將該column的值設為1
                    connection.ping(reconnect=True)
                    with connection.cursor() as cursor:
                        cursor.execute(f"UPDATE `product_history` SET `{price_range}` = 1"
                                       f" WHERE `search_key` = %s AND `from_where` = %s;", (search_key, from_where))

        connection.ping(reconnect=True)
        connection.commit()  # 將資料提交至MySQL
    
    driver.quit()  # 關閉瀏覽器
    print("爬蟲完成")  # 測試用
    connection.close()  # 關閉與資料庫的連線


# 初始化瀏覽器
def init_browser():
    chrome_path = "/home/ptcg/chrome-testing/chrome-linux64/chrome"
    chromedriver_path = "/home/ptcg/chrome-testing/chromedriver-linux64/chromedriver"
    options = Options()
    options.binary_location = chrome_path
    options.add_argument("--headless=new")
    options.add_argument('--window-size=1280,1024')
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-debugging-port=0")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/133.0.0.0 Safari/537.36")
    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=options)

    # 設定載入網頁timeout
    driver.set_page_load_timeout(180)

    # 打開露天
    driver.get("https://www.ruten.com.tw/")

    try:
        # 等待彈出式廣告的X可被點擊
        close_button = WebDriverWait(driver, 10).until(
            ec.element_to_be_clickable((By.CLASS_NAME, 'rt-lightbox-close-button'))
        )

        # 關閉進入露天首頁時的彈出式廣告
        close_button.click()
    except TimeoutException:
        pass

    return driver


# 爬蟲
def crawler(search_key, keyword, driver, connection):
    while True:
        try:
            # 等待網頁載入搜尋欄位
            search = WebDriverWait(driver, 10).until(
                ec.presence_of_element_located((By.ID, "searchKeyword"))
            )
            break
        except TimeoutException:
            # 等一下後重新整理
            time.sleep(5)
            driver.refresh()

    # 使用露天搜尋功能
    search.send_keys(Keys.CONTROL, 'a')  # 將輸入框全選，用以覆蓋前次搜尋文字
    search.send_keys(keyword)
    search.send_keys(Keys.RETURN)

    has_next_page = True  # 有下一頁
    products_price = []  # 商品價格list
    no_result = True  # 無搜尋結果
    while has_next_page:
        while True:
            try:
                # 等待載入完成
                WebDriverWait(driver, 10).until(
                    ec.presence_of_element_located((By.CLASS_NAME, "top-part"))
                )
                break
            except TimeoutException:
                # 等一下後重新整理
                time.sleep(5)
                driver.refresh()

        # 將網頁往下滑至底部
        for i in range(2):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(5)

        done_one_page_crawling = False  # 完成一頁的爬蟲
        while not done_one_page_crawling:
            try:
                # 檢查此頁是否有翻頁功能
                # 沒有的話代表無搜尋結果
                pagination = WebDriverWait(driver, 10).until(
                    ec.presence_of_element_located((By.ID, "mainPagination"))
                )

                # 有搜尋結果
                # 開始處理該頁商品資料
                top_part = driver.find_element(By.CLASS_NAME, "top-part")
                products = top_part.find_elements(By.CLASS_NAME, "rt-product-card")
                bottom_part = driver.find_elements(By.CLASS_NAME, "bottom-part")

                # 檢查該頁是否有下半部分商品
                if len(bottom_part) != 0:  # 有
                    products = products + bottom_part[0].find_elements(By.CLASS_NAME, "rt-product-card")

                for product in products:
                    # 判斷此商品是否為廣告
                    if len(product.find_elements(By.CLASS_NAME, "rt-product-card-ad-tag")) == 0:  # 否
                        title = product.find_element(By.CLASS_NAME, "rt-product-card-name")
                        # 過濾器
                        if productfilter(title.text, search_key, connection):
                            # 判斷此商品價格類型
                            if len(product.find_elements(By.CLASS_NAME, "text-price-dash")) == 0:  # 單一價格
                                price = product.find_element(By.CLASS_NAME, "text-price-dollar")
                                price_int = int(price.text.replace(",", ""))
                                if price_int >= 20000:  # 沒貨
                                    continue
                            else:  # 範圍價格
                                price_range = product.find_elements(By.CLASS_NAME, "text-price-dollar")
                                low_price = int(price_range[0].text.replace(",", ""))
                                high_price = int(price_range[1].text.replace(",", ""))
                                price_int = (low_price + high_price) // 2
                                if low_price >= 20000:  # 沒貨
                                    continue
                                elif high_price >= 20000:  # 沒貨
                                    continue

                            products_price.append(price_int)  # 將商品資訊新增至商品資訊list

                # 存在有效搜尋結果
                if len(products_price) > 0:
                    no_result = False

                limit = pagination.find_elements(By.CLASS_NAME, "is-at-limit")

                # 檢查是否到達頁數極限
                for i in range(len(limit)):
                    # 檢查頁數極限是否為下一頁而非上一頁
                    if limit[i].find_element(By.TAG_NAME, "span").text == "下一頁":
                        has_next_page = False
                        break

                if has_next_page:
                    next_page = WebDriverWait(driver, 10).until(
                        ec.element_to_be_clickable((By.CSS_SELECTOR, "[aria-label='下一頁']"))
                    )
                    next_page.click()

                done_one_page_crawling = True
            except TimeoutException:
                # 無翻頁功能，代表無搜尋結果
                has_next_page = False
                done_one_page_crawling = True
            except WebDriverException:
                # 遇到out of memory等錯誤
                print("WebDriverException")  # 測試用
                # 等一下後重新整理
                time.sleep(5)
                driver.refresh()

    return products_price, no_result


# 清除快取
def clearcache(driver):
    driver.execute_script("window.open('https://www.google.com/');")
    driver.switch_to.window(driver.window_handles[1])
    driver.get("chrome://settings/clearBrowserData")
    time.sleep(5)

    shadow_host = driver.find_element(By.TAG_NAME, "settings-ui")
    shadow_root = shadow_host.shadow_root
    shadow_host = shadow_root.find_element(By.ID, "main")
    shadow_root = shadow_host.shadow_root
    shadow_host = shadow_root.find_element(By.CLASS_NAME, "cr-centered-card-container")
    shadow_root = shadow_host.shadow_root
    shadow_host = shadow_root.find_element(By.CSS_SELECTOR, "settings-privacy-page")
    shadow_root = shadow_host.shadow_root
    shadow_host = shadow_root.find_element(By.CSS_SELECTOR, "settings-clear-browsing-data-dialog")
    shadow_root = shadow_host.shadow_root
    clear_button = shadow_root.find_element(By.ID, "clearButton")
    clear_button.click()
    time.sleep(5)
    # 關閉分頁
    driver.close()
    driver.switch_to.window(driver.window_handles[0])


# 過濾商品
def productfilter(text, search_key, connection):
    connection.ping(reconnect=True)  # 確保資料庫連線正常
    # 用來操作資料庫的游標
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM `card` WHERE `search_key` = '{search_key} 球閃';")
        has_ball_shine_ver = cursor.fetchone()
    if has_ball_shine_ver:
        if "球閃" in text:
            return False

    name = search_key.split(" ", 1)[-1]  # name = search_key去除編號
    if "ex" not in name and "ex" in text:  # 在非ex寶可夢的搜尋結果中過濾掉ex寶可夢
        return False

    if "ex" in name and "ex" not in text:  # 在ex寶可夢的搜尋結果中過濾掉非ex寶可夢
        return False

    if "Ⅱ" in name:
        name = name.split("Ⅱ", 1)[0]  # name = name中"Ⅱ"以前的部分
        if name not in text:
            return False
    elif "(" in name:
        name = name.split("(", 1)[0]  # name = name中"("以前的部分
        if name not in text:
            return False
    elif "（" in name:
        name = name.split("（", 1)[0]  # name = name中"（"以前的部分
        if name not in text:
            return False
    elif contains_fullwidth_letters(name):  # name中存在全形字母
        name = fullwidth_to_halfwidth(name)  # 將全形字母換成半形
        if name not in text:
            return False
    elif "・" in name:
        name = name.split("・", 1)  # 將name分成"・"前後兩部分
        if name[0] not in text and name[1] not in text:  # 兩部分都沒出現在text中
            return False
    elif " " in name:
        if "球閃" in name:
            if "大師" in text:
                return False
            if "球閃" not in text:
                return False
        name = name.split()  # 將name用" "分成n段
        right_product = False
        for i in range(len(name)):
            if name[i] in text:
                right_product = True
                break
        if not right_product:  # 每一部分都沒出現在text中
            return False
    else:
        if name not in text:
            return False

    if "卡套" in text:
        return False
    elif "牌套" in text:
        return False
    elif "卡盒" in text:
        return False
    elif "牌盒" in text:
        return False
    elif "卡墊" in text:
        return False
    elif "牌墊" in text:
        return False
    elif "卡冊" in text:
        return False
    elif "指示物" in text:
        return False
    elif "硬幣" in text:
        return False
    elif "收納" in text:
        return False
    elif "保護" in text:
        return False
    elif "寶可夢中心" in text:
        return False
    elif "美版" in text:
        return False
    elif "日版" in text:
        return False
    elif "國際版" in text:
        return False
    elif "英文" in text:
        return False
    elif "日文" in text:
        return False
    elif "日本" in text:
        return False
    elif "桌布" in text:
        return False
    elif "公仔" in text:
        return False
    elif "卡磚" in text:
        return False
    elif "鑑定" in text:
        return False
    elif "PSA" in text:
        return False
    elif "BGS" in text:
        return False
    elif "GX" in text:
        return False
    elif "gx" in text:
        return False
    elif ("娃娃" in text and "怨影" not in text and "詛咒" not in text and
          "差不多" not in text):
        return False
    else:
        return True


# 全形轉半形
def fullwidth_to_halfwidth(s):
    # 建立對應表：全形 A-Z, a-z 對應 半形 A-Z, a-z
    fullwidth_chars = "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
    halfwidth_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    translation_table = str.maketrans(fullwidth_chars, halfwidth_chars)

    # 轉換字串
    return s.translate(translation_table)


# 是否包含全形字母
def contains_fullwidth_letters(s):
    return any(0xFF21 <= ord(c) <= 0xFF3A or 0xFF41 <= ord(c) <= 0xFF5A for c in s)


# ruten_crawler_main()
