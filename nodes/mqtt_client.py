import time
import paho.mqtt.client as paho
from paho import mqtt
import os
from dotenv import load_dotenv
import logging

# Konfigurasi logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Output ke console
        logging.FileHandler('mqtt_client.log')  # Output ke file
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

class MyMQTTClient:
    def __init__(self, broker, port, username, password):
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.client = self.connect_mqtt()
        self.client.loop_start()
        self.timer = time.time()
        self.max_time = 5

    def connect_mqtt(self):
        def on_connect(client, userdata, flags, rc, properties=None):
            if rc == 0:
                logger.info("Connected to MQTT broker with code %s", rc)
            else:
                logger.error("CONNACK received with code %s", rc)

        def on_publish(client, userdata, mid, properties=None):
            logger.debug("Published message with mid: %s", mid)

        def on_subscribe(client, userdata, mid, granted_qos, properties=None):
            logger.info("Subscribed: mid=%s, granted_qos=%s", mid, granted_qos)

        def on_message(client, userdata, msg):
            logger.info("Received message: topic=%s, qos=%s, payload=%s", 
                       msg.topic, msg.qos, msg.payload.decode())

        def on_disconnect(client, userdata, rc, properties=None):
            FIRST_RECONNECT_DELAY = 1
            RECONNECT_RATE = 2
            MAX_RECONNECT_COUNT = 12
            MAX_RECONNECT_DELAY = 60
            logger.warning("Disconnected with result code: %s", rc)
            reconnect_count, reconnect_delay = 0, FIRST_RECONNECT_DELAY
            while reconnect_count < MAX_RECONNECT_COUNT:
                logger.info("Reconnecting in %d seconds...", reconnect_delay)
                time.sleep(reconnect_delay)

                try:
                    client.reconnect()
                    logger.info("Reconnected successfully!")
                    return
                except Exception as err:
                    logger.error("Reconnect failed: %s. Retrying...", err)

                reconnect_delay *= RECONNECT_RATE
                reconnect_delay = min(reconnect_delay, MAX_RECONNECT_DELAY)
                reconnect_count += 1
            logger.critical("Reconnect failed after %s attempts. Exiting...", reconnect_count)

        client = paho.Client(client_id="dashboard", userdata=None, protocol=paho.MQTTv5)
        client.on_connect = on_connect

        # Enable TLS for secure connection
        client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
        # Set username and password
        client.username_pw_set(self.username, self.password)
        # Connect to broker
        try:
            client.connect(self.broker, int(self.port))
            logger.info("Initiated connection to broker %s:%s", self.broker, self.port)
        except Exception as e:
            logger.error("Failed to connect to broker: %s", e)
            raise

        # Setting callbacks
        client.on_subscribe = on_subscribe
        client.on_message = on_message
        client.on_publish = on_publish
        return client

    def publish_play_sound(self):
        topic = "control/sawah1/mp3player/play"
        payload = "{\"action\": \"play sound test\"}"
        try:
            result = self.client.publish(topic, payload, qos=1)
            self.timer = time.time()
            status = result[0]
            if status == 0:
                logger.info("Successfully published to %s", topic)
                return {"success": True, "message": "Success play test sound"}
            else:
                logger.error("Failed to publish to %s, status: %s", topic, status)
                return {"success": False, "message": "Failed to send message to topic " + topic}
        except Exception as e:
            logger.error("Error publishing to %s: %s", topic, e)
            return {"success": False, "message": "Error publishing message"}
        
    def publish_stop_sound(self):
        topic = "control/sawah1/mp3player/stop"
        payload = "{\"action\": \"stop sound\"}"
        try:
            result = self.client.publish(topic, payload, qos=1)
            status = result[0]
            if status == 0:
                logger.info("Successfully stopped sound")
                return {"success": True, "message": "Success stop sound"}
            else:
                logger.error("Failed to publish to %s, status: %s", topic, status)
                return {"success": False, "message": "Failed to send message to topic " + topic}
        except Exception as e:
            logger.error("Error publishing to %s: %s", topic, e)
            return {"success": False, "message": "Error publishing message"}

    def publish_set_default_sound(self, filenumber):
        topic = "setting/sawah1/mp3player/default_filenumber"
        payload = "{\"filenumber\":%d}" % filenumber
        try:
            result = self.client.publish(topic, payload, qos=1)
            status = result[0]
            if status == 0:
                logger.info("Successfully set default sound to filenumber %d", filenumber)
                return {"success": True, "message": "Success set default sound"}
            else:
                logger.error("Failed to publish to %s, status: %s", topic, status)
                return {"success": False, "message": "Failed to send message to topic " + topic}
        except Exception as e:
            logger.error("Error publishing to %s: %s", topic, e)
            return {"success": False, "message": "Error publishing message"}

    def publish_set_volume_speaker(self, volume):
        topic = "control/sawah1/mp3player/set_volume"
        payload = "{\"value\":%d}" % volume
        try:
            result = self.client.publish(topic, payload, qos=1)
            status = result[0]
            if status == 0:
                logger.info("Successfully set volume to %d", volume)
                return {"success": True, "message": "Success set volume speaker"}
            else:
                logger.error("Failed to publish to %s, status: %s", topic, status)
                return {"success": False, "message": "Failed to send message to topic " + topic}
        except Exception as e:
            logger.error("Error publishing to %s: %s", topic, e)
            return {"success": False, "message": "Error publishing message"}

    def publish_play_sound_file(self, filenumber):
        topic = "control/sawah1/mp3player/play"
        payload = "{\"action\": \"play sound file\", \"filenumber\":%d}" % filenumber
        try:
            result = self.client.publish(topic, payload, qos=1)
            status = result[0]
            if status == 0:
                logger.info("Successfully played sound file %d", filenumber)
                return {"success": True, "message": "Success play sound with file number " + str(filenumber)}
            else:
                logger.error("Failed to publish to %s, status: %s", topic, status)
                return {"success": False, "message": "Failed to send message to topic " + topic}
        except Exception as e:
            logger.error("Error publishing to %s: %s", topic, e)
            return {"success": False, "message": "Error publishing message"}