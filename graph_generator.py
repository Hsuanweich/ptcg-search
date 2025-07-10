import mysql.connector
from mysql.connector import pooling
from modelv1 import modelmain
import plotly.graph_objects as go
import base64
from decimal import Decimal, ROUND_HALF_UP
import numpy as np


def get_primary_key(file_name, pool):
    isball = False
    if '-ball' in file_name:
        file_name = file_name.replace('-ball', '')
        isball = True
    temp = file_name.replace('_', '/')
    temp = temp.replace('.jpg', '')
    search_key_id = temp.split('+', 1)[0]
    from_where_id = temp.split('+', 1)[1]

    connection = pool.get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT `from_where` FROM `booster_pack` WHERE `id` = %s;", (from_where_id,))
            from_where = cursor.fetchone()[0]
        if isball:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT `search_key` FROM `card` WHERE `search_key` LIKE '{search_key_id}%' AND `search_key` LIKE '%球閃%'"
                            f" AND `from_where` = %s;", (from_where,))
                search_key = cursor.fetchone()[0]
        else:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT `search_key` FROM `card` WHERE `search_key` LIKE '{search_key_id}%' AND `search_key` NOT LIKE '%球閃%'"
                            f" AND `from_where` = %s;", (from_where,))
                search_key = cursor.fetchone()[0]
    finally:
        connection.close()
    return search_key, from_where


def get_q1q2q3(search_key, from_where, pool):
    connection = pool.get_connection()
    try:
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT `price_date`, `q1`, `median`, `q3`, `highest`, `lowest` FROM `product_week` "
                        "WHERE `search_key` = %s AND `from_where` = %s ORDER BY `price_date` ASC;", (search_key, from_where))
            results = cursor.fetchall()
    finally:
        connection.close()
    price_date = [row['price_date'] for row in results]
    q1 = [row['q1'] for row in results]
    median = [row['median'] for row in results]
    q3 = [row['q3'] for row in results]
    highest = [row['highest'] for row in results]
    lowest = [row['lowest'] for row in results]
    return price_date, q1, median, q3, highest, lowest


def get_labels_values(search_key, from_where, pool):
    # 取得product的columns名稱
    connection = pool.get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'product'"
                        " AND DATA_TYPE IN ('int');")
            product_columns = cursor.fetchall()
        labels = [col[0] for col in product_columns]

        if len(labels) == 0:
            connection.close()
            return [], []
        
        columns_str = ", ".join([f"`{label}`" for label in labels])

        #  取得該column中的值
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT {columns_str} FROM `product` WHERE `search_key` = %s AND"
                            f" `from_where` = %s;", (search_key, from_where))
            result = cursor.fetchone()
    finally:
        connection.close()

    values = []
    valid_labels = []
    if result:
        for i, value in enumerate(result):
            if value is not None:
                values.append(value)
                valid_labels.append(labels[i])
    if len(values) == 0:
        return [], []
    paired = list(zip(valid_labels, values))
    paired.sort(key=lambda x: int(x[0].split('~')[0]))  # 排序labels和values
    labels, values = zip(*paired)
    return list(labels), list(values)


def get_image(search_key, from_where, pool):
    search_key_id = search_key.replace('/', '_').split()[0]

    # 取得product的columns名稱
    connection = pool.get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT `id` from `booster_pack` WHERE `from_where` = %s", (from_where,))
            from_where_id = cursor.fetchone()[0]
    finally:
        connection.close()  # 關閉與資料庫的連線
    if '球閃' in search_key:
        file_name = f"{search_key_id}+{from_where_id}-ball.jpg"
    else:
        file_name = f"{search_key_id}+{from_where_id}.jpg"
    file_path = f"official_card_image/{file_name}"
    with open(file_path, 'rb') as f:
        img_base64 = base64.b64encode(f.read()).decode('utf-8')
    return img_base64


def cal_recommended_price(columns, values):
    recommended_price = 0
    value_num = 0
    i = 0
    for column in columns:
        value_num += values[i]
        price = int(column.split('~')[0]) + 4
        recommended_price += price * values[i]
        i += 1
    if recommended_price > 0:
        recommended_price /= value_num
    recommended_price = Decimal(str(recommended_price)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return recommended_price

def get_cardfullname(search_key, from_where, pool):
    connection = pool.get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT `full_name` FROM `card` WHERE `search_key` = '{search_key}' AND `from_where` = '{from_where}';")
            result = cursor.fetchone()
        if result:
            full_name = result[0]
        else:
            full_name = ""
    finally:
        connection.close()

    return full_name

def get_price(search_key, from_where, table_name, pool):
    # 取得product的columns名稱
    connection = pool.get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table_name}'"
                        " AND DATA_TYPE IN ('int');")
            product_columns = cursor.fetchall()
        columns = [col[0] for col in product_columns]   

        
        if len(columns) == 0:
            connection.close()
            return [], []
        
        columns_str = ", ".join([f"`{column}`" for column in columns])

        #  取得該column中的值
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT {columns_str} FROM `{table_name}` WHERE `search_key` = %s AND"
                            f" `from_where` = %s;", (search_key, from_where))
            result = cursor.fetchone()
    finally:
        connection.close()  # 關閉與資料庫的連線

    data = []
    if result:
        for i, value in enumerate(result):
            if value is not None:
                price = int(columns[i].split('~')[0]) + 4
                for _ in range(value):
                    # 將價格加入data中，重複value次
                    data.append(price)

    if len(data) == 0:
        return [], []
    
    num_bins = 6

    # 自動分箱，hist 是各區間數量，bin_edges 是區間邊界
    hist, bin_edges = np.histogram(data, bins=num_bins)

    # 產生區間標籤，例如 "$100-$400"
    labels = []
    for i in range(num_bins):
        labels.append(f"${int(bin_edges[i])}-${int(bin_edges[i+1])}")
    
    return labels, hist.tolist()  # 將hist轉換為列表返回

def gengraph_main(qq):
    dbconfig = {
        "host": "127.0.0.1",
        "port": "3306",
        "user": "root",
        "password": "PokemonTCG",
        "database": "PTCG"
    }
    pool = pooling.MySQLConnectionPool(pool_name="mypool", pool_size=5, **dbconfig)
    data = []
    file_paths = modelmain(qq)

    for file_path in file_paths:
        file_name = file_path.rsplit('/', 1)[-1]  # 取得檔名
        search_key, from_where = get_primary_key(file_name, pool)
        card_fullname = get_cardfullname(search_key, from_where, pool)
        product_columns, product_values = get_labels_values(search_key, from_where, pool)
        product_labels, product_data = get_price(search_key, from_where, "product", pool)
        product_history_labels, product_history_data = get_price(search_key, from_where, "product_history", pool)
        price_date, q1, median, q3, highest, lowest = get_q1q2q3(search_key, from_where, pool)
        recommended_price = cal_recommended_price(product_columns, product_values)
        card_image_data = get_image(search_key, from_where, pool)
        product_bar = {
            "labels": product_labels,
            "datasets": [{
                    "label": "價格分布",
                    "data": product_data,
                    "backgroundColor": "rgba(25, 118, 210, 0.8)",
                    "borderColor": "#0D47A1",
                    "hoverBackgroundColor": "rgba(25, 118, 210, 1)",
                    "hoverBorderColor": "#0D47A1",
                    "borderWidth": 2
            }]
        }

        product_history_bar = {
            "labels": product_history_labels,
            "datasets": [{
                "label": "價格分布",
                "data": product_history_data,
                "backgroundColor": "rgba(255, 152, 0, 0.8)",
                "borderColor": "#E65100",
                "hoverBackgroundColor": "rgba(255, 152, 0, 1)",
                "hoverBorderColor": "#E65100",
                "borderWidth": 2
            }]
        }

        product_week_line = {
            "labels": price_date,
            "datasets": [
                {"label": "最高價", "data": highest},
                {"label": "第三四分位數", "data": q3},
                {"label": "中位數", "data": median},
                {"label": "第一四分位數", "data": q1},
                {"label": "最低價", "data": lowest},
            ]
        }

        card_info = {
            "card_image": f"data:image/jpeg;base64,{card_image_data}",
            "recommended_price": recommended_price,
            "card_fullname": card_fullname,
            "product_bar": product_bar,
            "product_history_bar": product_history_bar,
            "product_week_line": product_week_line
        }
        
        data.append(card_info)
    return data
