import streamlit as st
import logging
import time
from dotenv import load_dotenv
import os
import uuid
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
BROKER = os.environ.get("BROKER")
PORT =  os.environ.get("BROKER_PORT")
USERNAME =  os.environ.get("BROKER_USERNAME")
PASSWORD =  os.environ.get("BROKER_PASSWORD")
DEVICE_ID =  os.environ.get("UBIDOTS_DEVICE_ID")
TOKEN =  os.environ.get("UBIDOTS_TOKEN")

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

# **************** Variable ***************
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
        st.button("Start Camera", key="start_camera_button")
    with col2:
        st.button("Stop Camera", key="stop_camera_button")
    placeholder = st.empty()
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
    st.subheader("⚙️ Camera Configuration")
    st.button("Scan Camera", key="scan_camera_button")
    st.text_input("Enter Camera IP Address", value="", key="camera_ip")
    tab1, tab2 = st.tabs(["Camera Config", "Camera Status"])
    with tab1:
        cols = st.columns(2)
        with cols[0]:
            st.number_input("Xclk", value=20, key="xclk", min_value=20, max_value=40, step=1)
        st.button("Set", key="set_camera_xclk_button", disabled=True)
        cols = st.columns(2)
        with cols[0]:
            st.selectbox("Resolution", options=["96x96", "QQVGA(160x120)", "128x128", "QCIF(176x144)", 
                                              "HQVGA(240x176)", "240x240", "QVGA(320x240)", "CIF(400x296)", 
                                              "HVGA(480x320)", "VGA(640x480)", "SVGA(800x600)", "XGA(1024x768)", 
                                              "HD(1280x720)", "SXGA(1280x1024)", "UXGA(1600x1200)"], 
                         index=12, key="resolution")
        st.button("Set", key="set_camera_resolution_button", disabled=True)
    with tab2:
        st.button("Cek Config", key="check_config_button", disabled=True)