from flask import Flask, request, jsonify, render_template,send_file
import json
import os
import threading
import time
import pandas as pd
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode
from datetime import datetime, timedelta




AES_KEY = b'kmhhsyhguiot1234'  # 16-byte key
BLOCK_SIZE = 16

app = Flask(__name__)
DATA_FILE = 'population.json'
EXCEL_FILE = 'population_log.xlsx'
BUILDINGS = ["Room1", "Cafeteria", "Gym"]


def decrypt_lora_message(encrypted_base64):
    try:
        cipher = AES.new(AES_KEY, AES.MODE_ECB)
        decrypted = cipher.decrypt(b64decode(encrypted_base64))
        unpadded = unpad(decrypted, BLOCK_SIZE)
        return unpadded.decode('utf-8')
    except Exception as e:
        app.logger.error(f"[복호화 오류] {e}")
        return None

def is_recent_timestamp(ts_str):
    try:
        now = datetime.now()
        msg_time = datetime.strptime(ts_str, "%d%H%M%S")
        msg_time = msg_time.replace(year=now.year, month=now.month)
        return abs((now - msg_time).total_seconds()) <= 30
    except Exception:
        return False
    

def load_population():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_population(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_to_excel_periodically():
    while True:
        time.sleep(600) 
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

@app.route('/population')
def get_population():
    data = load_population()
    return jsonify(data)

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
        encrypted_b64 = request.get_data(as_text=True).strip()
        app.logger.info(f"[LoRa 수신] (암호문): {encrypted_b64}") 

        decrypted = decrypt_lora_message(encrypted_b64)
        if not decrypted or '/' not in decrypted:
            app.logger.warning(f"복호화 실패 또는 포맷 오류: {decrypted}")
            return jsonify(success=False, error="복호화 실패 또는 포맷 오류"), 400

        payload, timestamp = decrypted.split('/')
        app.logger.info(f"복호화 결과 : {payload} | {timestamp} ")

        # ✅ timestamp 보정 및 유효성 검사
        now = datetime.now()
        try:
            msg_time = datetime.strptime(timestamp, "%d%H%M%S")
            msg_time = msg_time.replace(year=now.year, month=now.month)
            msg_time -= timedelta(hours=9)  # 9시간 보정 (KST → UTC)

            delta = abs((now - msg_time).total_seconds())
            if delta > 30:
                app.logger.warning(
                    f"유효하지 않은 timestamp 수신: {timestamp} | "
                    f"기준 시간: {now.strftime('%Y-%m-%d %H:%M:%S')} | "
                    f"보정된 msg_time: {msg_time.strftime('%Y-%m-%d %H:%M:%S')} | "
                    f"차이: {delta:.2f}초"
                )
                return jsonify(success=False, error="유효하지 않은 timestamp (30초 초과)"), 400
        except Exception as e:
            app.logger.warning(f"timestamp 파싱 실패: {timestamp} | 오류: {e}")
            return jsonify(success=False, error="timestamp 포맷 오류"), 400

        building, value = payload.split(':')
        building = building.strip()
        value = int(value.strip())

        app.logger.info(f"처리 대상 → building: {building}, value: {value}, timestamp: {timestamp}")

        data = load_population()
        if building not in data:
            data[building] = 0

        data[building] += value
        if data[building] < 0:
            data[building] = 0

        save_population(data)
        app.logger.info(f"인원 업데이트 완료: {building} = {data[building]}")
        return jsonify(success=True, updated=data[building])
    except Exception as e:
        app.logger.error(f"[LoRa 처리 오류] {str(e)}")
        return jsonify(success=False, error=str(e)), 400


    
@app.route('/upload_image/<location>', methods=['POST'])
def upload_image(location):
    location = location.lower() 
    file = request.files['file']
    save_dir = 'static/realtime'
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"{location}.png")
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

@app.route('/')
def map_page():
    data = load_population()
    return render_template('map.html', data=data)

if __name__ == '__main__':
    thread = threading.Thread(target=save_to_excel_periodically, daemon=True)
    thread.start()
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
