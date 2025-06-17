from flask import Flask, request, jsonify, render_template,send_file
import json
import os
import threading
import time
import pandas as pd
from datetime import datetime

app = Flask(__name__)
DATA_FILE = 'population.json'
EXCEL_FILE = 'population_log.xlsx'
BUILDINGS = ["Room1", "Cafeteria", "Gym"]

# JSON 파일 불러오기
def load_population():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# JSON 파일 저장
def save_population(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 주기적으로 엑셀 저장
def save_to_excel_periodically():
    while True:
        time.sleep(600)  # 10분 주기
        data = load_population()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        row = {"timestamp": timestamp}
        for b in BUILDINGS:
            row[b] = data.get(b, 0)

        df_new = pd.DataFrame([row])

        if os.path.exists(EXCEL_FILE):
            existing_df = pd.read_excel(EXCEL_FILE)
            df_new = pd.concat([existing_df, df_new], ignore_index=True)

        df_new.to_excel(EXCEL_FILE, index=False)
        print(f"[{timestamp}] Excel 저장 완료.")

# 인원 조회 API
@app.route('/population')
def get_population():
    data = load_population()
    return jsonify(data)

# 일반 수동 업데이트 API
@app.route('/update', methods=['POST'])
def update_population():
    content = request.json
    building = content.get("building")
    direction = content.get("direction")

    data = load_population()
    if building not in data:
        data[building] = 0

    if direction == "in":
        data[building] += 1
    elif direction == "out" and data[building] > 0:
        data[building] -= 1

    save_population(data)
    return jsonify(success=True, updated=data[building])

@app.route('/lora', methods=['POST'])
def update_from_lora():
    try:
        # 핵심: TTGO가 보내는 text/plain 데이터 받기
        content = request.get_data(as_text=True).strip()
        print(f"수신 데이터: {content}")

        # 수정된 데이터 형식 파싱
        building, value = content.split(":")
        building = building.strip()
        value = int(value.strip())

        data = load_population()
        if building not in data:
            data[building] = 0

        data[building] += value

        # 인원수는 음수로 떨어지지 않게 제한
        if data[building] < 0:
            data[building] = 0

        save_population(data)
        return jsonify(success=True, updated=data[building])
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400
    
@app.route('/upload_image/<location>', methods=['POST'])
def upload_image(location):
    location = location.lower()  # 소문자로 통일
    file = request.files['file']
    save_dir = 'static/realtime'
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"{location}.jpg")
    file.save(save_path)
    return jsonify(success=True)


@app.route('/graph')
def graph_page():
    return render_template('graph.html')

@app.route('/history')
def get_history():
    if not os.path.exists(EXCEL_FILE):
        return jsonify({"error": "No data"}), 404

    limit = request.args.get('limit', default=10, type=int)  
    df = pd.read_excel(EXCEL_FILE)
    df = df.tail(limit)

    result = {
        "timestamp": df["timestamp"].tolist(),
        "Room1": df["Room1"].tolist(),
        "Cafeteria": df["Cafeteria"].tolist(),
        "Gym": df["Gym"].tolist()
    }
    return jsonify(result)


@app.route('/history_view')
def history_page():
    return render_template('history.html')

@app.route('/cctv')
def cctv_page():
    return render_template('cctv.html')

@app.route('/download_log')
def download_log():
    return send_file('population_log.xlsx', as_attachment=True)

# 기본 메인 페이지
@app.route('/')
def map_page():
    data = load_population()
    return render_template('map.html', data=data)

# 서버 실행
if __name__ == '__main__':
    thread = threading.Thread(target=save_to_excel_periodically, daemon=True)
    thread.start()
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
