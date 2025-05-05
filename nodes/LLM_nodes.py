import cv2
import numpy as np
import requests
from io import BytesIO
from PIL import Image
import logging
from typing import Iterator
import uuid
import os
import base64
from openai import OpenAI
from streamlit import secrets

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RicePlantAnalyzer:
    """Class to analyze rice plant conditions using ESP32 camera images and xAI Grok-2 Vision API."""
    def __init__(self, max_retries: int = 3, timeout: int = 10):
        self.max_retries = max_retries
        self.timeout = timeout
        self.api_key = secrets.get("XAI_API_KEY")
        if not self.api_key:
            raise ValueError("XAI_API_KEY environment variable not set.")
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.x.ai/v1"
        )
        self.session_id = str(uuid.uuid4())
        logger.info(f"Initialized RicePlantAnalyzer with session ID: {self.session_id}")

    def _fetch_image(self, camera_ip: str) -> np.ndarray:
        """Fetch image from ESP32 camera web server."""
        if not camera_ip:
            raise ValueError("Camera IP must be provided.")
        url = f"http://{camera_ip}/capture"
        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, timeout=self.timeout)
                response.raise_for_status()
                image = Image.open(BytesIO(response.content))
                image = np.array(image)
                if len(image.shape) == 2:  # Convert grayscale to RGB
                    image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
                logger.info("Image fetched successfully.")
                return image
            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed to fetch image: {str(e)}")
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"Failed to fetch image after {self.max_retries} attempts.")

    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        try:
            image = image / 255.0
            # Ensure correct format (H, W, C)
            if image.shape[-1] != 3:
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            logger.info("Image preprocessed successfully.")
            return image
        except Exception as e:
            logger.error(f"Image preprocessing failed: {str(e)}")
            raise

    def infer_plant_condition(self, camera_ip: str) -> Iterator[str]:
        try:
            image = self._fetch_image(camera_ip)
            processed_image = self._preprocess_image(image)
            _, buffer = cv2.imencode('.jpg', (image * 255).astype(np.uint8))
            image_base64 = base64.b64encode(buffer).decode('utf-8')
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}",
                                "detail": "high"
                            }
                        },
                        {
                            "type": "text",
                            "text": """
You are an expert agronomist analyzing a top-down image of a rice plant. Based on that image, provide a detailed description of the rice plant's condition. Include observations about its appearance, such as leaf color, structure, and any visible signs of stress or abnormalities. Discuss possible causes of the observed condition and recommend actions to improve or maintain the plant's health. Format your response in markdown for clarity, ensuring it is comprehensive and suitable for farmers or agricultural experts. Answer with objectivity and precision, avoiding any subjective language or personal opinions. Your response should be informative and actionable, providing clear guidance on how to address the plant's condition. Use bullet points or numbered lists where appropriate to enhance readability. answer with short and clear sentences.
"""
                        }
                    ]
                }
            ]

            try:
                stream = self.client.chat.completions.create(
                    model="grok-2-vision-latest",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=500,
                    stream=True
                )

                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        yield content
                        logger.debug("Streamed chunk of analysis.")

                logger.info("Plant condition analysis completed.")
            except Exception as e:
                logger.error(f"API request failed: {str(e)}")
                raise RuntimeError(f"Failed to get response from Grok-2 Vision API: {str(e)}")

        except Exception as e:
            logger.error(f"Error during inference: {str(e)}")
            raise