from flask import Flask, request, jsonify, render_template
import json
import os

app = Flask(__name__)
DATA_FILE = 'population.json'

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

@app.route('/update', methods=['POST'])
def update_population():
    content = request.json
    building = content.get("building")
    direction = content.get("direction")  # "in" or "out"

    data = load_population()
    if building not in data:
        data[building] = 0

    if direction == "in":
        data[building] += 1
    elif direction == "out" and data[building] > 0:
        data[building] -= 1

    save_population(data)
    return jsonify(success=True, updated=data[building])

@app.route('/')
def map_page():
    data = load_population()
    return render_template('map.html', data=data)

if __name__ == '__main__':
    app.run(debug=True)
