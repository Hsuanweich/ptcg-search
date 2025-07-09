import mysql.connector
from modelv1 import modelmain
import plotly.graph_objects as go
import base64
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
import numpy as np


def get_primary_key(file_name):
    isball = False
    if '-ball' in file_name:
        file_name = file_name.replace('-ball', '')
        isball = True
    temp = file_name.replace('_', '/')
    temp = temp.replace('.jpg', '')
    search_key_id = temp.split('+', 1)[0]
    from_where_id = temp.split('+', 1)[1]
    # 建立與資料庫的連線
    connection = mysql.connector.connect(host="127.0.0.1",
                                         port="3306",
                                         user="root",
                                         password="PokemonTCG",
                                         database="PTCG")
    connection.ping(reconnect=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT `from_where` FROM `booster_pack` WHERE `id` = %s;", (from_where_id,))
        from_where = cursor.fetchone()[0]
    if isball:
        connection.ping(reconnect=True)
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT `search_key` FROM `card` WHERE `search_key` LIKE '{search_key_id}%' AND `search_key` LIKE '%球閃%'"
                        f" AND `from_where` = %s;", (from_where,))
            search_key = cursor.fetchone()[0]
    else:
        connection.ping(reconnect=True)
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT `search_key` FROM `card` WHERE `search_key` LIKE '{search_key_id}%' AND `search_key` NOT LIKE '%球閃%'"
                        f" AND `from_where` = %s;", (from_where,))
            search_key = cursor.fetchone()[0]

    connection.close()  # 關閉與資料庫的連線
    return search_key, from_where


def gen_bar_graph(labels, values, search_key, time_range):
    if 0 < len(labels) < 6:
        last = labels[-1]
        last = int(last.split('~')[1])
        start = last + 1
        end = last + 10
        for i in range(6 - len(labels)):
            labels.append(f'{start+10*i}~{end+10*i}')
            values.append(0)
    # 設定每根 bar 想要的畫面寬度（像素）
    bar_pixel_width = 40*1.5
    bar_gap_pixel = 20*1.5  # 間隔寬度
    total_width = len(labels) * (bar_pixel_width + bar_gap_pixel)*1.5
    min_width = 300*1.5  # 圖最小寬度
    figure_width = max(total_width, min_width)

    # 建立圖表
    fig = go.Figure(data=[
        go.Bar(x=labels, y=values, width=0.4)  # width 是相對比例（0~1），固定值會搭配圖寬影響實際視覺寬度
    ])

    if len(labels) == 0:
        title = f'{search_key}<br>{time_range}價格統計圖 查無結果'
    else:
        title = f'{search_key}<br>{time_range}價格統計圖'

    # 美化與寬度設定
    fig.update_layout(
        title=dict(
            text=title,
            x=0.5,   # 水平置中
        ),
        width=figure_width,
        height=400*1.5,
        bargap=0.3,  # 控制 bar 與 bar 間的比例間距
        font=dict(family='Noto Sans TC, Source Han Sans TC, sans-serif', size=20),
        title_font=dict(size=24),
        xaxis_title='價格範圍'
    )

    fig.add_annotation(
        text="數<br>量",
        xref="paper", yref="paper",
        x=-0.1, y=0.5,  # 位置視圖大小調整，x 負一點會往左
        showarrow=False,
        font=dict(family='Noto Sans TC, Source Han Sans TC, sans-serif', size=24),
        align="center"
    )

    return fig


def gen_line_chart(price_date, q1, median, q3, search_key):
    fig = go.Figure()

    # 第三四分位數線
    fig.add_trace(go.Scatter(x=price_date, y=q3, mode='lines+markers', name='第三四分位數'))

    # 中位數線
    fig.add_trace(go.Scatter(x=price_date, y=median, mode='lines+markers', name='中位數'))

    # 第一四分位數線
    fig.add_trace(go.Scatter(x=price_date, y=q1, mode='lines+markers', name='第一四分位數'))

    xaxis_config = {
        "ticklabelmode": "period",  # ticklabel 對齊區段
        "tickformat": "%Y-%m-%d"
    }

    if len(price_date) == 1:
        start = price_date[0] - timedelta(days=1)
        end = price_date[0] + timedelta(days=1)
        #xaxis_config["range"] = [start, end]

    # 圖表設定
    fig.update_layout(
        title=dict(
            text=f'{search_key}<br>價格隨時間的四分位數折線圖',
            x=0.5,  # 水平置中
        ),
        height=600,
        font=dict(family='Noto Sans TC, Source Han Sans TC, sans-serif', size=20),
        title_font=dict(size=24),
        xaxis_title='日期',
        legend_title='四分位數',
        xaxis=xaxis_config
    )

    fig.add_annotation(
        text="價<br>格",
        xref="paper", yref="paper",
        x=-0.17, y=0.5,  # 位置視圖大小調整，x 負一點會往左
        showarrow=False,
        font=dict(family='Noto Sans TC, Source Han Sans TC, sans-serif', size=24),
        align="center"
    )

    return fig


def get_q1q2q3(search_key, from_where):
    # 建立與資料庫的連線
    connection = mysql.connector.connect(host="127.0.0.1",
                                         port="3306",
                                         user="root",
                                         password="PokemonTCG",
                                         database="PTCG")

    connection.ping(reconnect=True)
    with connection.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT `price_date`, `q1`, `median`, `q3`, `highest`, `lowest` FROM `product_week` "
                       "WHERE `search_key` = %s AND `from_where` = %s ORDER BY `price_date` ASC;", (search_key, from_where))
        results = cursor.fetchall()
    connection.close()
    price_date = [row['price_date'] for row in results]
    q1 = [row['q1'] for row in results]
    median = [row['median'] for row in results]
    q3 = [row['q3'] for row in results]
    highest = [row['highest'] for row in results]
    lowest = [row['lowest'] for row in results]
    return price_date, q1, median, q3, highest, lowest


def get_labels_values(search_key, from_where, table_name):
    # 建立與資料庫的連線
    connection = mysql.connector.connect(host="127.0.0.1",
                                         port="3306",
                                         user="root",
                                         password="PokemonTCG",
                                         database="PTCG")

    # 取得product的columns名稱
    connection.ping(reconnect=True)
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table_name}'"
                       " AND DATA_TYPE IN ('int');")
        product_columns = cursor.fetchall()
    labels = [col[0] for col in product_columns]

    if len(labels) == 0:
        connection.close()
        return [], []
    
    columns_str = ", ".join([f"`{label}`" for label in labels])

    #  取得該column中的值
    connection.ping(reconnect=True)
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {columns_str} FROM `{table_name}` WHERE `search_key` = %s AND"
                        f" `from_where` = %s;", (search_key, from_where))
        result = cursor.fetchone()

    connection.close()  # 關閉與資料庫的連線

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


def get_image(search_key, from_where):
    # 建立與資料庫的連線
    connection = mysql.connector.connect(host="127.0.0.1",
                                         port="3306",
                                         user="root",
                                         password="PokemonTCG",
                                         database="PTCG")

    search_key_id = search_key.replace('/', '_').split()[0]

    # 取得product的columns名稱
    connection.ping(reconnect=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT `id` from `booster_pack` WHERE `from_where` = %s", (from_where,))
        from_where_id = cursor.fetchone()[0]
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

def get_cardfullname(search_key, from_where):
    # 建立與資料庫的連線
    connection = mysql.connector.connect(host="127.0.0.1",
                                         port="3306",
                                         user="root",
                                         password="PokemonTCG",
                                         database="PTCG")
    connection.ping(reconnect=True)
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT `label` FROM `booster_pack` WHERE `from_where` = '{from_where}';")
        result = cursor.fetchone()
    if result:  # 有對應的label
        label = result[0]
    else:  # 沒有對應的label
        label = ""
    connection.close()  # 關閉與資料庫的連線
    num, name = search_key.split(' ', 1)
    num = num.split('/')[0]
    keyword = label + ' ' + num + ' ' + name
    return keyword

def get_price(search_key, from_where, table_name):
    # 建立與資料庫的連線
    connection = mysql.connector.connect(host="127.0.0.1",
                                         port="3306",
                                         user="root",
                                         password="PokemonTCG",
                                         database="PTCG")

    # 取得product的columns名稱
    connection.ping(reconnect=True)
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
    connection.ping(reconnect=True)
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {columns_str} FROM `{table_name}` WHERE `search_key` = %s AND"
                        f" `from_where` = %s;", (search_key, from_where))
        result = cursor.fetchone()

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
    data = []
    file_paths = modelmain(qq)
    """file_paths = ['/home/ptcg/PTCGHTML/official_card_image/001+1.jpg', '/home/ptcg/PTCGHTML/official_card_image/002+1.jpg',
                  '/home/ptcg/PTCGHTML/official_card_image/003+1.jpg', '/home/ptcg/PTCGHTML/official_card_image/004+1.jpg',
                  '/home/ptcg/PTCGHTML/official_card_image/005+1.jpg']"""
    '''
    for file_path in file_paths:
        file_name = file_path.rsplit('/', 1)[-1]  # 取得檔名
        search_key, from_where = get_primary_key(file_name)
        card_fullname = get_cardfullname(search_key, from_where)
        product_labels, product_values = get_labels_values(search_key, from_where, "product")
        product_history_labels, product_history_values = get_labels_values(search_key, from_where, "product_history")
        price_date, q1, median, q3 = get_q1q2q3(search_key, from_where)
        recommended_price = cal_recommended_price(product_labels, product_values)
        product_fig = gen_bar_graph(product_labels, product_values, search_key, "本週")
        product_history_fig = gen_bar_graph(product_history_labels, product_history_values, search_key, "歷史")
        product_line_fig = gen_line_chart(price_date, q1, median, q3, search_key)
        card_image_data = get_image(search_key, from_where)
        card_info = {
            "card_image": f"data:image/jpeg;base64,{card_image_data}",
            "this_week_bar": product_fig.to_dict(),
            "history_bar": product_history_fig.to_dict(),
            "line_chart": product_line_fig.to_dict(),
            "recommended_price": recommended_price
        }
        data.append(card_info)
    '''
    for file_path in file_paths:
        file_name = file_path.rsplit('/', 1)[-1]  # 取得檔名
        search_key, from_where = get_primary_key(file_name)
        card_fullname = get_cardfullname(search_key, from_where)
        product_columns, product_values = get_labels_values(search_key, from_where, "product")
        product_labels, product_data = get_price(search_key, from_where, "product")
        product_history_labels, product_history_data = get_price(search_key, from_where, "product_history")
        price_date, q1, median, q3, highest, lowest = get_q1q2q3(search_key, from_where)
        recommended_price = cal_recommended_price(product_columns, product_values)
        card_image_data = get_image(search_key, from_where)
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
