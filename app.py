import os
import io
from flask import Flask, request, jsonify, send_from_directory, render_template, send_file, session, Response
import subprocess
from searchkey_crawler import searchkey_crawler_main
from ruten_crawler import ruten_crawler_main
from flask_bcrypt import Bcrypt
from flask_session import Session
from datetime import datetime
from flask_cors import CORS
from graph_generator import gengraph_main
from classify import classifymain
from werkzeug.utils import secure_filename
from flask import redirect
import pandas as pd

app = Flask(__name__, template_folder=os.getcwd(), static_folder=os.getcwd())
app.secret_key = 'clove123'  # 用於加密 session（請換成安全的值）
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

UPLOAD_FOLDER = 'ptcg_cards/primitivephonephoto'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/<folder>/<path:filename>')
def serve_static(folder, filename):
    allowed_folders = ['css', 'js', 'img']
    if folder in allowed_folders:
        return send_from_directory(folder, filename)
    return 'Not Found', 404

@app.route('/display')
def display():
    return render_template('display.html')

@app.route('/testprogram')
def testprogram():
    if not session.get('logged_in'):
        return redirect('/login')
    return render_template('testprogram.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'clove' and password == '123':
            session['logged_in'] = True
            return jsonify({'message': '登入成功', 'redirect': '/testprogram'})
        else:
            return jsonify({'message': '帳密錯誤'}), 401
    return render_template('login.html')

@app.route('/logout') # 登出路由
def logout():
    session.clear()
    return redirect('/login')

# 只傳單一檔案上傳處理
@app.route('/upload_files', methods=['POST'])
def upload_files():
    file = request.files.get('files')
    saved_files = []

    if file and file.filename:
        save_path = os.path.join(UPLOAD_FOLDER, file.filename)
        pre_path = session.get('uploaded_image_path')
        if pre_path and os.path.exists(pre_path):
            os.remove(pre_path)
            print(pre_path + "已刪除")
        file.save(save_path)
        session['uploaded_image_path'] = save_path
        print(save_path + "已上傳")
        saved_files.append(file.filename)

    return jsonify({'📂files成功上傳': saved_files})

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# 首頁路由，顯示 index.html
@app.route('/')
def index():
    # 手動返回根目錄中的 index.html
    return render_template('index.html')  # 返回根目錄中的 index.html 文件

# 執行 Python 程式的路由
@app.route('/run-script', methods=['POST']) #原本是POST
def run_script():
    # 執行 Python 程式
    print("執行第一個程式碼")
    searchkey_crawler_main()
    return jsonify({'message': f'Python 程式碼已執行完畢'})

# 執行 Python 程式的路由
@app.route('/run-script-2', methods=['POST']) #原本是POST
def run_script2():
    # 執行 Python 程式
    print("執行第二個程式碼")
    ruten_crawler_main()#改成第二個程式碼
    return jsonify({'message': f'Python 程式碼已執行完畢'})

# 執行 Python 程式的路由
@app.route('/run-script-3', methods=['POST']) #原本是POST
def run_script3():
    # 執行 Python 程式
    print("執行第三個程式碼")
    classifymain()#改成第三個程式碼
    return jsonify({'message': f'Python 程式碼已執行'})

# 執行 Python 程式的路由
@app.route('/run-script-4', methods=['POST']) #原本是POST
def run_script4():
    # 執行 Python 程式
    print("執行第四個程式碼")
    img_path = session.get('uploaded_image_path')
    data = gengraph_main(img_path)#改成第四個程式碼
    for adate in data:
        for label in adate['product_week_line']['labels']:
            try:
                pd.to_datetime(label)
            except Exception as e:
                print('Invalid date:', label)
    os.remove(img_path)  # 刪除上傳的檔案
    print("done!")
    
    return jsonify(data)

# 啟動伺服器
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000 ,debug=True)
#pip install -r requirements.txt