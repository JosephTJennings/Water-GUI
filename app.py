from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
from flask_socketio import SocketIO
import sqlite3
import csv
import os
from datetime import datetime, timedelta
from PIL import Image  # Pillow library for image processing

app = Flask(__name__)
socketio = SocketIO(app)
DATABASE = 'database.db'
CSV_FILE = 'plants.csv'
IMAGE_FOLDER = 'static/images/'

# Database setup
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS plants (
            id INTEGER PRIMARY KEY,
            name TEXT,
            image TEXT,
            last_watered DATE,
            watering_interval INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Load data from CSV into database
def load_csv_to_db():
    with open(CSV_FILE, 'r') as f:
        reader = csv.DictReader(f)
        plants = list(reader)
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        for plant in plants:
            cursor.execute('''
                INSERT OR IGNORE INTO plants (id, name, image, last_watered, watering_interval)
                VALUES (?, ?, ?, ?, ?)
            ''', (plant['id'], plant['name'], plant['image'], plant['last_watered'], plant['watering_interval']))
        conn.commit()
        conn.close()

load_csv_to_db()

# Helper function to resize image to 200x200
def resize_image(image_path):
    try:
        img = Image.open(image_path)
        img = img.resize((200, 200), Image.ANTIALIAS)
        img.save(image_path)
    except IOError:
        print(f"Unable to resize image {image_path}")

@app.route('/')
def index():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM plants')
    plants = cursor.fetchall()
    conn.close()
    return render_template('index.html', plants=plants)

@app.route('/add', methods=['GET', 'POST'])
def add_plant():
    if request.method == 'POST':
        name = request.form['name']
        image = request.files['image']
        last_watered = request.form['last_watered']
        watering_interval = int(request.form['watering_interval'])
        
        image_path = os.path.join(IMAGE_FOLDER, image.filename)
        image.save(image_path)
        
        resize_image(image_path)  # Resize the uploaded image
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO plants (name, image, last_watered, watering_interval)
            VALUES (?, ?, ?, ?)
        ''', (name, image.filename, last_watered, watering_interval))
        conn.commit()
        conn.close()
        
        # Update CSV
        with open(CSV_FILE, 'a') as f:
            writer = csv.writer(f)
            writer.writerow([name, image.filename, last_watered, watering_interval])
        
        socketio.emit('update', {'name': name, 'image': image.filename, 'last_watered': last_watered, 'watering_interval': watering_interval})
        return redirect(url_for('index'))
    return render_template('add_plant.html')


@app.route('/water/<int:plant_id>', methods=['PUT'])
def water_plant(plant_id):
    data = request.get_json()
    if 'lastWatered' not in data:
        return jsonify({"error": "Missing lastWatered in request body"}), 400

    last_watered = data['lastWatered']

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE plants
        SET last_watered = ?
        WHERE id = ?
    ''', (last_watered, plant_id))
    
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Plant not found"}), 404

    conn.commit()
    conn.close()
    return jsonify({"success": True}), 200


@app.route('/static/images/<filename>')
def uploaded_file(filename):
    return send_from_directory(IMAGE_FOLDER, filename)

@socketio.on('connect')
def handle_connect():
    print('Client connected')

if __name__ == '__main__':
    socketio.run(app, port=5000, debug=True)
