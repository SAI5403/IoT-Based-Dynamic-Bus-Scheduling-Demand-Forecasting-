import time
from flask import Flask, request, jsonify, render_template_string
import hashlib
from datetime import datetime, timezone, timedelta
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt
import json
import threading

app = Flask(__name__)
# Initialize WebSockets
socketio = SocketIO(app, cors_allowed_origins="*")

# ==================================
# CONFIGURATION & GLOBALS
# ==================================
SECRET_KEY    = "MyIoTPass"
passenger_count = 0
used_tokens   = set()
IST = timezone(timedelta(hours=5, minutes=30))

count_array = []
time_array  = []

# ==================================
# MQTT LISTENER THREAD
# ==================================
# This runs in the background, constantly listening to Mosquitto
def on_connect(client, userdata, flags, rc):
    print("MQTT Listener Connected to Broker")
    client.subscribe("bus/passenger_count")

def on_message(client, userdata, msg):
    global count_array, time_array
    try:
        # 1. Catch the message from M5Stack
        payload = msg.payload.decode('utf-8')
        data = json.loads(payload)
        
        time_str = data.get("time")
        count = int(data.get("count"))
        
        # 2. Save it to our arrays
        time_array.append(time_str)
        count_array.append(count)
        
        print(f"MQTT Received - Time: {time_str}, Count: {count}")
        
        # 3. INSTANTLY broadcast it to any open web browsers
        socketio.emit('new_data', {'time': time_str, 'count': count, 'total': sum(count_array)})
        
    except Exception as e:
        print("MQTT Parsing Error:", e)

def start_mqtt_thread():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect("192.168.137.1", 1883, 60)
    client.loop_forever()

# Boot the MQTT listener in a separate thread so it doesn't block Flask
threading.Thread(target=start_mqtt_thread, daemon=True).start()


# ==================================
# CORE ROUTES (Same as before)
# ==================================
def get_expected_hash():
    t    = datetime.now(IST)
    slot = t.second // 20
    time_str = f"{t.year}{t.month}{t.day}{t.hour}{t.minute}{slot}"
    return hashlib.sha256((SECRET_KEY + time_str).encode()).hexdigest()[:10]

@app.route('/enter')
def enter():
    global passenger_count
    token = request.args.get('t')
    if not token: return "<h1>Invalid QR</h1>", 403
    if token != get_expected_hash(): return "<h1>QR Expired</h1>", 403

    ip = request.remote_addr
    device_id  = f"{ip}|{request.headers.get('User-Agent', 'unknown')}"
    scan_key   = f"{token}|{device_id}"

    if scan_key in used_tokens: return "<h1>Already Scanned</h1>", 200

    used_tokens.add(scan_key)
    passenger_count += 1
    return f"<h1>✅ Entry Successful</h1><p>Passenger #{passenger_count} boarded.</p>"

@app.route('/get_count')
def get_count():
    return str(passenger_count)

@app.route('/reset_count')
def reset_count():
    global passenger_count, used_tokens
    passenger_count = 0
    used_tokens.clear()
    return "Reset Done"


# ==================================
# DASHBOARD ROUTE & HTML
# ==================================
@app.route('/data', methods=['GET'])
def data():
    return render_template_string(DASHBOARD_HTML, 
                                  time_array=time_array, 
                                  count_array=count_array, 
                                  total=sum(count_array), 
                                  points=len(count_array))

# Notice the added Socket.io script at the bottom of the HTML
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Bus Occupancy Monitor</title>
  <link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap" rel="stylesheet"/>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
  <style>
    /* ... (KEEP ALL YOUR EXISTING CSS EXACTLY THE SAME) ... */
    :root { --bg: #08090d; --surface: #0f1117; --border: #1e2330; --accent: #00d4aa; --accent2: #7ee8a2; --warn: #f59e0b; --text: #e2e8f0; --muted: #4a5568; --mono: 'Space Mono', monospace; --sans: 'Syne', sans-serif; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: var(--bg); color: var(--text); font-family: var(--mono); min-height: 100vh; padding: 0; }
    header { display: flex; align-items: center; justify-content: space-between; padding: 20px 36px; border-bottom: 1px solid var(--border); background: var(--surface); }
    .logo { font-family: var(--sans); font-weight: 800; font-size: 1.1rem; letter-spacing: 0.15em; color: var(--accent); text-transform: uppercase; }
    .logo span { color: var(--text); }
    .live-badge { display: flex; align-items: center; gap: 8px; font-size: 0.7rem; letter-spacing: 0.12em; color: var(--accent2); }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent2); animation: pulse 1.4s ease-in-out infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.75); } }
    main { max-width: 1100px; margin: 0 auto; padding: 36px 24px; }
    .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 28px; }
    .card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 24px 28px; position: relative; overflow: hidden; }
    .card::before { content: ''; position: absolute; top: 0; left: 0; width: 3px; height: 100%; background: var(--accent); }
    .card.warn::before { background: var(--warn); }
    .card-label { font-size: 0.65rem; letter-spacing: 0.18em; color: var(--muted); text-transform: uppercase; margin-bottom: 10px; }
    .card-value { font-family: var(--sans); font-size: 2.2rem; font-weight: 800; color: var(--accent); line-height: 1; }
    .card.warn .card-value { color: var(--warn); }
    .card-sub { font-size: 0.65rem; color: var(--muted); margin-top: 6px; }
    .chart-section { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 28px 32px; }
    .chart-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 24px; }
    .chart-title { font-family: var(--sans); font-weight: 700; font-size: 0.95rem; letter-spacing: 0.08em; color: var(--text); }
    .chart-meta { font-size: 0.65rem; letter-spacing: 0.1em; color: var(--muted); }
    .no-data { text-align: center; padding: 80px 0; color: var(--muted); font-size: 0.8rem; letter-spacing: 0.15em; }
    .no-data p { margin-top: 8px; font-size: 0.65rem; }
    footer { text-align: center; padding: 24px; font-size: 0.6rem; letter-spacing: 0.12em; color: var(--muted); border-top: 1px solid var(--border); margin-top: 48px; }
  </style>
</head>
<body>

<header>
  <div class="logo">Bus<span>Occupancy</span></div>
  <div class="live-badge"><div class="dot"></div>LIVE MONITOR</div>
</header>

<main>
  <div class="stats">
    <div class="card">
      <div class="card-label">Total Boarded (all time)</div>
      <div class="card-value" id="total-val">{{ total }}</div>
      <div class="card-sub" id="points-val">across {{ points }} reporting intervals</div>
    </div>
    <div class="card warn">
      <div class="card-label">Latest Count</div>
      <div class="card-value" id="latest-val">{{ count_array[-1] if count_array else 0 }}</div>
      <div class="card-sub" id="time-val">{{ time_array[-1] if time_array else "Listening for MQTT..." }}</div>
    </div>
  </div>

  <div class="chart-section">
    <div class="chart-header">
      <div class="chart-title">Passenger Count Over Time</div>
      <div class="chart-meta">Live updates via WebSockets</div>
    </div>
    <canvas id="lineChart" height="90"></canvas>
  </div>
</main>

<script>
  // Initialize Chart.js
  const ctx = document.getElementById('lineChart').getContext('2d');
  const grad = ctx.createLinearGradient(0, 0, 0, 300);
  grad.addColorStop(0, 'rgba(0, 212, 170, 0.18)');
  grad.addColorStop(1, 'rgba(0, 212, 170, 0.01)');

  const myChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: {{ time_array | tojson }},
      datasets: [{
        label: 'Passengers',
        data: {{ count_array | tojson }},
        borderColor: '#00d4aa', backgroundColor: grad, borderWidth: 2,
        pointBackgroundColor: '#00d4aa', pointBorderColor: '#08090d', pointBorderWidth: 2,
        pointRadius: 5, pointHoverRadius: 8, tension: 0.4, fill: true,
      }]
    },
    options: {
      responsive: true,
      scales: {
        x: { ticks: { color: '#4a5568', font: { family: 'Space Mono', size: 10 } }, grid: { color: '#1e2330' } },
        y: { beginAtZero: true, ticks: { color: '#4a5568', font: { family: 'Space Mono', size: 10 }, stepSize: 1 }, grid: { color: '#1e2330' } }
      }
    }
  });

  // 2. Connect WebSockets and listen for the "new_data" event
  const socket = io();
  socket.on('new_data', function(msg) {
      console.log("Live data received:", msg);
      
      // Update DOM Text
      document.getElementById('latest-val').innerText = msg.count;
      document.getElementById('time-val').innerText = msg.time;
      document.getElementById('total-val').innerText = msg.total;
      
      // Push new data into Chart.js
      myChart.data.labels.push(msg.time);
      myChart.data.datasets[0].data.push(msg.count);
      
      // Update points count text
      document.getElementById('points-val').innerText = "across " + myChart.data.labels.length + " reporting intervals";
      
      // Redraw the chart smoothly
      myChart.update();
  });
</script>
</body>
</html>
"""

if __name__ == '__main__':
    # Use socketio.run instead of app.run to enable WebSockets
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)