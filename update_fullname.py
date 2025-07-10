import mysql.connector
def update_full_name():
    connection = mysql.connector.connect(host="127.0.0.1",
                                            port="3306",
                                            user="root",
                                            password="PokemonTCG",
                                            database="PTCG")

    with connection.cursor() as cursor:
        cursor.execute("SELECT `search_key`, `from_where` FROM `card` WHERE `full_name` IS NULL;")
        all_result = cursor.fetchall()

    for result in all_result:
        search_key = result[0]
        from_where = result[1]
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT `label` FROM `booster_pack` WHERE `from_where` = '{from_where}';")
            result = cursor.fetchone()
        if result:  # 有對應的label
            label = result[0]
        else:  # 沒有對應的label
            label = ""

        num, name = search_key.split(' ', 1)
        num = num.split('/')[0]
        full_name = label + ' ' + num + ' ' + name
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE `card` SET `full_name` = '{full_name}' WHERE `search_key` = '{search_key}' AND `from_where` = '{from_where}';")
            connection.commit()

    connection.close()

# update_full_name()