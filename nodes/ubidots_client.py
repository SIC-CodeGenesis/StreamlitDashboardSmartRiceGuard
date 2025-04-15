import requests
import json
import logging


# Konfigurasi logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Output ke console
        logging.FileHandler('ubidots_client.log')  # Output ke file
    ]
)

logger = logging.getLogger(__name__)

class ubidots():
    def __init__(self, token, device_label):
        self.token = token
        self.device_label = device_label
        self.url = f"https://industrial.api.ubidots.com/api/v1.6/devices/{self.device_label}"
        self.headers = {
            "X-Auth-Token": self.token,
            "Content-Type": "application/json"
        }
    def send_data(self, dict_value):
        """
        Send data to Ubidots.
            :param value: The value to send
            :return: Response from the Ubidots API
        """
        try:
            response = requests.post(self.url, headers=self.headers, json=dict_value)
            response.raise_for_status()  # Raise an error for bad responses
            logger.info("Data sent successfully: %s", response.json())
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error("Error sending data to Ubidots: %s", e)
            return None