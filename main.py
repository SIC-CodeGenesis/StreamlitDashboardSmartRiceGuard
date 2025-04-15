import streamlit as st
import asyncio
import websockets
import base64
from PIL import Image
import io
import logging
import queue
import threading
import time
import atexit
import uuid
from utils.camera_util import get_wifi_ip, scan_camera, Camera
from utils.display import display_dict_to_ui
import pandas as pd
from dotenv import load_dotenv
import os
from nodes.mqtt_client import MyMQTTClient
from nodes.ubidots_client import ubidots

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('streamlit_app.log')
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# ***************** Constanta *******
RESOLUTION_DICT = {
    "96x96": 0,
    "QQVGA(160x120)": 1,
    "128x128": 2,
    "QCIF(176x144)": 3,
    "HQVGA(240x176)": 4,
    "240x240": 5,
    "QVGA(320x240)": 6,
    "CIF(400x296)": 7,
    "HVGA(480x320)": 8,
    "VGA(640x480)": 9,
    "SVGA(800x600)": 10,
    "XGA(1024x768)": 11,
    "HD(1280x720)": 12,
    "SXGA(1280x1024)": 13,
    "UXGA(1600x1200)": 14,
}

REVERSED_RESOLUTION_DICT = {v: k for k, v in RESOLUTION_DICT.items()}
BROKER = os.environ.get("BROKER")
PORT = os.environ.get("BROKER_PORT")
USERNAME = os.environ.get("BROKER_USERNAME")
PASSWORD = os.environ.get("BROKER_PASSWORD")
DEVICE_ID = os.environ.get("UBIDOTS_DEVICE_ID")
TOKEN = os.environ.get("UBIDOTS_TOKEN")

# Fungsi untuk membersihkan koneksi MQTT
def cleanup_mqtt_client():
    if "mqtt_client" in st.session_state and st.session_state.mqtt_client is not None:
        try:
            st.session_state.mqtt_client.client.loop_stop()
            st.session_state.mqtt_client.client.disconnect()
            logger.info("MQTT client disconnected and loop stopped")
        except Exception as e:
            logger.error("Error cleaning up MQTT client: %s", e)
        finally:
            st.session_state.mqtt_client = None

# Daftarkan pembersihan saat aplikasi dihentikan
atexit.register(cleanup_mqtt_client)

# ***************** Util Function *******
def start_camera():
    st.session_state.start_camera = True
    st.session_state.stop_camera = False
    st.session_state.frame_counter = 0
    if "last_frame" in st.session_state:
        del st.session_state.last_frame

def stop_camera():
    st.session_state.start_camera = False
    st.session_state.stop_camera = True
    if "frame_queue" in st.session_state:
        st.session_state.frame_queue.queue.clear()
    if "last_frame" in st.session_state:
        del st.session_state.last_frame

async def st_scan_camera(ip):
    st.session_state.scan_camera = True
    st.session_state.camera_list = scan_camera(ip)
    st.session_state.scan_camera = False

def st_cek_camera_config():
    camera_ip = st.session_state.camera_ip
    if not camera_ip:
        st.warning("Masukkan alamat IP kamera.")
        return
    camera = Camera(camera_ip)
    camera_config = camera.cek_camera_configuration()
    if camera_config:
        st.session_state.camera_configuration = camera_config
    else:
        st.error("Gagal mengambil konfigurasi kamera. Pastikan alamat IP benar dan kamera terhubung.")

def set_camera_resolution():
    camera_ip = st.session_state.camera_ip
    if not camera_ip:
        st.warning("Masukkan alamat IP kamera.")
        return
    camera = Camera(camera_ip)
    resolution = st.session_state.resolution
    resolution_int = RESOLUTION_DICT.get(resolution, 12)
    if camera.set_camera_resolution(resolution_int):
        st.success(f"Resolusi kamera diatur ke {resolution}.")
    else:
        st.error("Gagal mengatur resolusi kamera. Pastikan alamat IP benar dan kamera terhubung.")

def set_camera_xclk():
    camera_ip = st.session_state.camera_ip
    if not camera_ip:
        st.warning("Masukkan alamat IP kamera.")
        return
    camera = Camera(camera_ip)
    xclk = st.session_state.xclk
    if camera.set_camera_xclk(xclk):
        st.success(f"XCLK diatur ke {xclk}.")
    else:
        st.error("Gagal mengatur XCLK. Pastikan alamat IP benar dan kamera terhubung.")

async def receive_frame(websocket_uri, frame_queue):
    reconnect_delay = 1
    max_reconnect_delay = 30
    while not st.session_state.get("stop_camera", False):
        try:
            async with websockets.connect(websocket_uri, ping_interval=10, ping_timeout=20) as websocket:
                logger.info("Connected to WebSocket")
                reconnect_delay = 1
                while not st.session_state.get("stop_camera", False):
                    try:
                        data = await asyncio.wait_for(websocket.recv(), timeout=10)
                        if not data:
                            logger.warning("Received empty data")
                            continue
                        try:
                            img_bytes = base64.b64decode(data)
                            if len(img_bytes) < 100:
                                logger.warning("Received data too small to be an image")
                                continue
                            try:
                                image = Image.open(io.BytesIO(img_bytes))
                                image.verify()
                                image = Image.open(io.BytesIO(img_bytes))
                                while not frame_queue.empty():
                                    try:
                                        frame_queue.get_nowait()
                                        frame_queue.task_done()
                                    except queue.Empty:
                                        break
                                frame_queue.put_nowait((image, None))
                                logger.debug("Frame queued")
                            except Exception as e:
                                logger.error(f"Invalid image data: {e}")
                                frame_queue.put_nowait((None, f"Invalid image data: {e}"))
                                continue
                        except base64.binascii.Error as e:
                            logger.error(f"Base64 decode error: {e}")
                            frame_queue.put_nowait((None, f"Base64 decode error: {e}"))
                            continue
                    except asyncio.TimeoutError:
                        logger.warning("WebSocket receive timeout")
                        continue
                    except websockets.exceptions.ConnectionClosed as e:
                        logger.error(f"WebSocket connection closed: {e}")
                        break
                    except Exception as e:
                        logger.error(f"Error processing frame: {e}")
                        frame_queue.put_nowait((None, f"Error processing frame: {e}"))
                        continue
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            if st.session_state.get("stop_camera", False):
                break
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
            logger.info(f"Attempting to reconnect in {reconnect_delay} seconds...")

def run_websocket_loop(websocket_uri, frame_queue):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(receive_frame(websocket_uri, frame_queue))
    except Exception as e:
        logger.error(f"Websocket loop error: {e}")
    finally:
        loop.close()

def update_ui(placeholder, frame_queue):
    try:
        if not frame_queue.empty():
            image, error = frame_queue.get_nowait()
            if error:
                placeholder.error(error)
            elif image:
                st.session_state.last_frame = image
                placeholder.image(image, channels="RGB", caption="Live Feed")
                st.session_state.frame_counter += 1
            frame_queue.task_done()
        elif "last_frame" in st.session_state:
            placeholder.image(st.session_state.last_frame, channels="RGB", caption="Live Feed")
        else:
            placeholder.write("No frames received yet...")
    except queue.Empty:
        if "last_frame" in st.session_state:
            placeholder.image(st.session_state.last_frame, channels="RGB", caption="Live Feed")
        else:
            placeholder.write("No frames received yet...")

# Fungsi Speaker Config
def display_notification(placeholder, notification_key):
    if notification_key in st.session_state:
        message, msg_type, timestamp = st.session_state[notification_key]
        if time.time() - timestamp < 3:
            if msg_type == "success":
                placeholder.success(message)
            else:
                placeholder.error(message)
        else:
            del st.session_state[notification_key]

def play_test_sound():
    if st.session_state.mqtt_client:
        result = st.session_state.mqtt_client.publish_play_sound()
        st.session_state.play_notification = (
            "Playing test sound." if result["success"] else "Failed to play test sound.",
            "success" if result["success"] else "error",
            time.time()
        )
    else:
        st.session_state.play_notification = (
            "MQTT client not initialized.",
            "error",
            time.time()
        )

def stop_test_sound():
    if st.session_state.mqtt_client:
        result = st.session_state.mqtt_client.publish_stop_sound()
        st.session_state.stop_notification = (
            "Stopping test sound." if result["success"] else "Failed to stop test sound.",
            "success" if result["success"] else "error",
            time.time()
        )
    else:
        st.session_state.stop_notification = (
            "MQTT client not initialized.",
            "error",
            time.time()
        )

def set_volume():
    if st.session_state.mqtt_client:
        volume = st.session_state.volume_slider
        result = st.session_state.mqtt_client.publish_set_volume_speaker(volume)
        st.session_state.volume_notification = (
            f"Volume set to {volume}." if result["success"] else "Failed to set volume.",
            "success" if result["success"] else "error",
            time.time()
        )
        st.session_state.ubidots_client.send_data({
            "speaker_volume": volume
        })
    else:
        st.session_state.volume_notification = (
            "MQTT client not initialized.",
            "error",
            time.time()
        )

def set_sound_file():
    if st.session_state.mqtt_client:
        sound_file = st.session_state.sound_file_number
        result = st.session_state.mqtt_client.publish_set_default_sound(sound_file)
        st.session_state.set_sound_notification = (
            f"Sound file set to {sound_file}." if result["success"] else "Failed to set sound file.",
            "success" if result["success"] else "error",
            time.time()
        )
        st.session_state.ubidots_client.send_data({
            "current_audio": sound_file
        })
    else:
        st.session_state.set_sound_notification = (
            "MQTT client not initialized.",
            "error",
            time.time()
        )

def play_sound_file():
    if st.session_state.mqtt_client:
        sound_file = st.session_state.play_sound_file_number
        result = st.session_state.mqtt_client.publish_play_sound_file(sound_file)
        st.session_state.play_file_notification = (
            f"Playing sound file {sound_file}." if result["success"] else "Failed to play sound file.",
            "success" if result["success"] else "error",
            time.time()
        )
    else:
        st.session_state.play_file_notification = (
            "MQTT client not initialized.",
            "error",
            time.time()
        )

# Inisialisasi session_state
if "sidebar_value" not in st.session_state:
    st.session_state.sidebar_value = "Dashboard"
if "camera_list" not in st.session_state:
    st.session_state.camera_list = []
if "scan_camera" not in st.session_state:
    st.session_state.scan_camera = False
if "start_camera" not in st.session_state:
    st.session_state.start_camera = False
if "stop_camera" not in st.session_state:
    st.session_state.stop_camera = False
if "frame_queue" not in st.session_state:
    st.session_state.frame_queue = queue.Queue(maxsize=10)
if "frame_counter" not in st.session_state:
    st.session_state.frame_counter = 0

# **************** Variable ***************
wifi_ip = get_wifi_ip()
websocket_uri = "ws://localhost:8765"

if "ubidots_client" not in st.session_state:
    st.session_state.ubidots_client = ubidots(
        token=TOKEN,
        device_label=DEVICE_ID
    )

# Inisiasi MQTT Client dengan Client ID unik
if "mqtt_client" not in st.session_state or st.session_state.mqtt_client is None:
    cleanup_mqtt_client()  # Bersihkan instance lama
    try:
        if not all([BROKER, PORT, USERNAME, PASSWORD]):
            logger.error("Missing MQTT credentials")
            st.error("Konfigurasi MQTT tidak lengkap. Periksa file .env.")
            raise ValueError("Incomplete MQTT configuration")
        # Tambahkan Client ID unik ke logger untuk tracking
        client_id = f"dashboard-{uuid.uuid4()}"
        logger.info("Initializing MQTT client with Client ID: %s", client_id)
        st.session_state.mqtt_client = MyMQTTClient(BROKER, int(PORT), USERNAME, PASSWORD)
        logger.info("MQTT client initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize MQTT client: %s", e)
        st.error(f"Gagal menginisiasi koneksi MQTT: {e}")
        st.session_state.mqtt_client = None

# **************** Util functions ***************
def sidebar_button(label):
    if st.button(label, use_container_width=True):
        st.session_state.sidebar_value = label

def create_middle_part():
    cols = st.columns([1, 2, 1])
    return cols[1]

# *************** SIDEBAR ***************
with st.sidebar:
    with create_middle_part():
        st.image("assets/codegenesislogo.jpeg", width=150)
    with create_middle_part():
        st.markdown("# 🚀 Menu 🚀")
    sidebar_button("Dashboard")
    sidebar_button("Live Cam")
    sidebar_button("Speaker Config")
    sidebar_button("Camera Config")

# *************** MAIN AREA ***************
st.title("Smart Farmer Dashboard")

selected = st.session_state.sidebar_value

if selected == "Dashboard":
    st.subheader("📊 Dashboard")
    st.write("Konten untuk dashboard di sini...")

elif selected == "Live Cam":
    st.subheader("📺 Live Cam")
    col1, col2 = st.columns(2)
    with col1:
        st.button("Start Camera", key="start_camera_button", on_click=start_camera)
    with col2:
        st.button("Stop Camera", key="stop_camera_button", on_click=stop_camera)
    placeholder = st.empty()

    if st.session_state.start_camera and not st.session_state.get("stop_camera", False):
        if "websocket_thread" not in st.session_state or not st.session_state.websocket_thread.is_alive():
            st.session_state.frame_queue = queue.Queue(maxsize=10)
            st.session_state.websocket_thread = threading.Thread(
                target=run_websocket_loop,
                args=(websocket_uri, st.session_state.frame_queue),
                daemon=True
            )
            st.session_state.websocket_thread.start()
            logger.info("WebSocket thread started")
        
        update_ui(placeholder, st.session_state.frame_queue)
        
        if not st.session_state.get("stop_camera", False):
            time.sleep(0.2)
            st.rerun()

    else:
        placeholder.write("Camera feed stopped.")

elif selected == "Speaker Config":
    st.subheader("🔊 Speaker Configuration")
    
    # Speaker Test
    st.write("## Speaker Test")
    play_placeholder = st.empty()
    display_notification(play_placeholder, "play_notification")
    col1, col2 = st.columns(2)
    with col1:
        st.button("Play test", key="play_speaker_button", on_click=play_test_sound)
    with col2:
        display_notification(play_placeholder, "stop_notification")
        st.button("Stop test", key="stop_speaker_button", on_click=stop_test_sound)
    
    # Speaker Config
    st.write("## Speaker Config")
    volume_placeholder = st.empty()
    display_notification(volume_placeholder, "volume_notification")
    st.slider("Volume", 0, 30, 30, key="volume_slider")
    st.button("Set Volume", key="set_volume_button", on_click=set_volume)
    
    # Choose Sound File
    st.write("## Choose Sound File")
    set_sound_placeholder = st.empty()
    display_notification(set_sound_placeholder, "set_sound_notification")
    st.number_input("Sound File", 0, 100, 1, key="sound_file_number")
    st.button("Set Sound File", key="set_sound_file_button", on_click=set_sound_file)
    
    # Play Sound File
    st.write("## Play Sound File")
    play_file_placeholder = st.empty()
    display_notification(play_file_placeholder, "play_file_notification")
    st.number_input("Sound File Number", 0, 100, 1, key="play_sound_file_number")
    st.button("Play Sound File", key="play_sound_file_button", on_click=play_sound_file)

elif selected == "Camera Config":
    if "camera_configuration" not in st.session_state:
        st.session_state.camera_configuration = {}
    st.subheader("⚙️ Camera Configuration")
    if st.button("Scan Camera", key="scan_camera_button"):
        with st.spinner("Scanning for cameras..."):
            asyncio.run(st_scan_camera(wifi_ip))
    if st.session_state.camera_list:
        st.write("Cameras found:")
        camera_df = pd.DataFrame(st.session_state.camera_list)
        st.dataframe(camera_df, use_container_width=True)
    st.text_input("Enter Camera IP Address", value="", key="camera_ip")
    tab1, tab2 = st.tabs(["Camera Config", "Camera Status"])
    with tab1:
        cols = st.columns(2)
        with cols[0]:
            st.number_input("Xclk", value=20, key="xclk", min_value=20, max_value=40, step=1)
        st.button("Set", key="set_camera_xclk_button", on_click=set_camera_xclk, disabled=not bool(st.session_state.camera_ip))
        cols = st.columns(2)
        with cols[0]:
            st.selectbox("Resolution", options=list(RESOLUTION_DICT.keys()), index=12, key="resolution")
        st.button("Set", key="set_camera_resolution_button", on_click=set_camera_resolution, disabled=not bool(st.session_state.camera_ip))
    with tab2:
        st.button("Cek Config", key="check_config_button", on_click=st_cek_camera_config, disabled=not bool(st.session_state.camera_ip))
        if st.session_state.camera_configuration:
            st.success("Kamera terhubung dan konfigurasi berhasil diambil.")
            display_dict_to_ui(st.session_state.camera_configuration, title="Camera Configuration", expandable=True)