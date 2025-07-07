# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import re
import os
import requests
import shutil

# 設置 ChromeDriver
service = Service(ChromeDriverManager().install())  # 自動下載對應版本的 ChromeDriver
options = webdriver.ChromeOptions()
options.add_argument("--disable-gpu")
options.add_argument("window-size=1920x1080")
options.add_argument('--ignore-certificate-errors')
options.add_argument('--incognito')
# options.add_argument("--headless")  # 如果不需要開啟瀏覽器，可取消註解
driver = webdriver.Chrome(service=service, options=options)  # 這裡加上 options

# 目標網址
url = "https://asia.pokemon-card.com/tw/card-search/"
driver.get(url)

# 點擊搜尋按鈕
search_button = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "searchButton")))
search_button.click()

# 等待網頁加載完成
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "imageContainer")))

# 解析 HTML 取得總頁數
soup = BeautifulSoup(driver.page_source, 'html.parser')
result_total_page_element = soup.find("p", class_="resultTotalPages")

# 確保能夠成功取得頁數
if result_total_page_element:
    match = re.search(r'\d+', result_total_page_element.get_text())
    totalpage = int(match.group()) if match else 1
else:
    print("未找到頁數資訊，預設為 1 頁")
    totalpage = 1

# 設定下載目錄
save_directory = "C:/Users/User/Downloads/ptcgpicture"

# 清空並準備目錄
def prepare_directory(save_directory):
    if os.path.exists(save_directory):
        shutil.rmtree(save_directory)  
    os.makedirs(save_directory)  

prepare_directory(save_directory)

# **下載圖片的函式（包含重試機制）**
def download_image(img_url, save_path, retries=3, delay=5):
    for attempt in range(retries):
        try:
            response = requests.get(img_url, stream=True, timeout=10)
            response.raise_for_status()
            with open(save_path, 'wb') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
            print(f"下載成功: {img_url} -> {save_path}")
            return
        except requests.exceptions.RequestException as e:
            print(f"下載失敗，重試 {attempt+1}/{retries}：{e}")
            time.sleep(delay)
    print(f"最終下載失敗: {img_url}")

# 爬取所有頁面
for page in range(totalpage):  
    if page != 0:
        try:
            next_btn = driver.find_element(By.CLASS_NAME, "next")
            next_link = next_btn.find_element(By.TAG_NAME, "a").get_attribute("href")
            driver.get(next_link)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "imageContainer")))
        except Exception as e:
            print(f"無法找到下一頁按鈕或發生錯誤: {e}")

    # 解析當前頁面
    soup = BeautifulSoup(driver.page_source, "html.parser")
    image_containers = soup.find_all("div", class_="imageContainer")

    # 下載圖片
    for index, container in enumerate(image_containers):
        img_elem = container.find("img", class_="lazy")
        if img_elem and 'data-original' in img_elem.attrs:
            img_url = img_elem['data-original']
            file_path = os.path.join(save_directory, f'image_{page}_{index}.jpg')
            download_image(img_url, file_path)
        else:
            print("未找到圖片或圖片的 URL")

# 關閉 WebDriver
driver.quit()