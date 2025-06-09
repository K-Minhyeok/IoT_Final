from flask import Flask, request, jsonify, render_template
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

def save_to_excel_periodically():
    while True:
        time.sleep(10)  # 또는 테스트용으로 10
        data = load_population()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 각 건물 값이 없으면 0으로 채움
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

# 인원 업데이트 API
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

# Lora 입력 처리 API
@app.route('/lora', methods=['POST'])
def update_from_lora():
    content = request.get_data(as_text=True).strip()
    print(content)
    try:
        building, direction = content.split(":")
        building = building.strip()
        direction = direction.strip()

        data = load_population()
        if building not in data:
            data[building] = 0

        if direction == "in":
            data[building] += 1
            print(f"{building}: {data[building]} In")
        elif direction == "out" and data[building] > 0:
            data[building] -= 1
            print(f"{building}: {data[building]} Out")

        save_population(data)
        return jsonify(success=True, updated=data[building])
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400

# 지도 페이지
@app.route('/')
def map_page():
    data = load_population()
    return render_template('map.html', data=data)

# Flask 실행
if __name__ == '__main__':
    # 스레드 직접 실행
    thread = threading.Thread(target=save_to_excel_periodically, daemon=True)
    thread.start()
    app.run(debug=True, use_reloader=False)
