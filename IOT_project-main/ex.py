import M5
from M5 import *
import time
import uhashlib
import binascii
import network
import ntptime
import urequests
from umqtt.simple import MQTTClient


WIFI_SSID = "sanjudell"
WIFI_PASSWORD = "1234567890"

SECRET_KEY = "MyIoTPass"
# For the QR Code (Public Internet for passenger phones)
QR_BASE_URL   = "https://ambition-basil-smelting.ngrok-free.dev"

# For the M5Stack (Fast Local Network to your Flask PC)
API_BASE_URL  = "http://192.168.137.1:5000"

MQTT_BROKER = "192.168.137.1"
MQTT_PORT = 1883
MQTT_TOPIC = b"bus/passenger_count"

IST_OFFSET = 19800


mqtt = None
clock_label = None
count_label = None


def setup_wifi():
    wlan = network.WLAN(network.STA_IF)

    wlan.active(False)
    time.sleep(1)

    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    print("Connecting WiFi...")

    while not wlan.isconnected():
        pass

    print("WiFi Connected:", wlan.ifconfig()[0])

    return wlan


def sync_time():
    try:
        ntptime.settime()
        print("Time Synced")
    except Exception as e:
        print("Time Sync Failed:", e)


def setup_mqtt():
    global mqtt

    mqtt = MQTTClient(
        "M5StackBusDevice",
        MQTT_BROKER,
        port=MQTT_PORT
    )

    mqtt.connect()

    print("MQTT Connected")


def get_local_time():
    return time.localtime(
        time.time() + IST_OFFSET
    )


def generate_token():
    t = get_local_time()

    slot = t[5] // 20

    token_string = "{}{}{}{}{}{}".format(
        t[0],
        t[1],
        t[2],
        t[3],
        t[4],
        slot
    )

    hash_obj = uhashlib.sha256(
        (SECRET_KEY + token_string).encode()
    )

    return binascii.hexlify(
        hash_obj.digest()
    ).decode()[:10]


def generate_qr_url():
    # Changed BASE_URL to QR_BASE_URL
    return QR_BASE_URL + "/enter?t=" + generate_token()


def display_qr(url):
    Lcd.fillRect(
        0,
        0,
        320,
        220,
        0xFFFFFF
    )

    Widgets.QRCode(
        url,
        10,
        5,
        210,
        5
    )


def fetch_live_count(retries=3):
    for attempt in range(retries):
        try:
            # Changed BASE_URL to API_BASE_URL
            response = urequests.get(API_BASE_URL + "/get_count")
            count = response.text.strip()
            response.close()
            return count
        except Exception as e:
            print("Fetch attempt {} failed: {}".format(attempt + 1, e))
            time.sleep(1)
    return None

def reset_server_count():
    try:
        # Changed BASE_URL to API_BASE_URL
        response = urequests.get(API_BASE_URL + "/reset_count")
        print("Server Reset:", response.text)
        response.close()
    except Exception as e:
        print("Reset Error:", e)

def send_data_to_server(count):
    try:
        time_str = get_time_str()
        payload = '{{"{}": {}}}'.format(time_str, count)
        # Changed BASE_URL to API_BASE_URL
        response = urequests.post(
            API_BASE_URL + "/data",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        print("Data Sent:", response.text)
        response.close()
    except Exception as e:
        print("Send Data Error:", e)


def publish_count(count):
    try:
        time_str = get_time_str()
        # Manually format a JSON string (no ujson library needed)
        payload = '{{"time": "{}", "count": {}}}'.format(time_str, count)
        
        mqtt.publish(MQTT_TOPIC, payload)
        print("MQTT Published:", payload)
    except Exception as e:
        print("MQTT Error:", e)


def setup_ui():
    global clock_label
    global count_label

    Lcd.fillScreen(0xFFFFFF)

    Lcd.fillRect(
        0,
        220,
        320,
        20,
        0x0078D7
    )

    clock_label = Widgets.Label(
        "00:00",
        0,
        222,
        1.0,
        0xFFFFFF,
        0x0078D7,
        Widgets.FONTS.DejaVu12
    )

    count_label = Widgets.Label(
        "Total: 0",
        200,
        222,
        1.0,
        0xFFFFFF,
        0x0078D7,
        Widgets.FONTS.DejaVu12
    )


def update_clock():
    t = get_local_time()

    clock_label.setText(
        "{:02d}:{:02d}".format(
            t[3],
            t[4]
        )
    )


def update_count():
    count = fetch_live_count()

    count_label.setText(
        "Total: " + count
    )

    return count


def refresh_qr():
    url = generate_qr_url()

    display_qr(url)

    print("QR Updated:", url)


def initialize():
    M5.begin()
    setup_wifi()
    sync_time()
    setup_mqtt()
    setup_ui()
    refresh_qr()


def main():
    initialize()

    last_slot = -1
    last_fetch = 0
    last_publish = time.time()

    while True:
        M5.update()

        update_clock()

        current_time = get_local_time()
        current_slot = current_time[5] // 20

        if current_slot != last_slot:
            refresh_qr()
            last_slot = current_slot

        if time.time() - last_fetch >= 5:
            update_count()
            last_fetch = time.time()

        if time.time() - last_publish >= 60:
            count = fetch_live_count()
            publish_count(count)
            reset_server_count()
            last_publish = time.time()

        time.sleep(1)


main()