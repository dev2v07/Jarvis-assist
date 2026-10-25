import uuid
import requests
import base64
import io
from PIL import Image
from diffusers.utils import load_image

class AwesomeChatService:

    def __init__(self, huggingface_token=None):
        self.token = huggingface_token

        if self.token:
            self.headers = {
                "Authorization": f"Bearer {self.token}"
            }
        else:
            self.headers = {}

    # --------------------------------
    # IMAGE TO BYTES
    # --------------------------------

    def image_to_bytes(self, url):

        img_byte = io.BytesIO()

        load_image(url).save(img_byte, format="png")

        return img_byte.getvalue()

    # --------------------------------
    # TEXT → IMAGE
    # --------------------------------

    def text_to_image(self, model, text):

        api = f"https://api-inference.huggingface.co/models/{model}"

        response = requests.post(
            api,
            headers=self.headers,
            json={"inputs": text},
            timeout=60
        )

        image = Image.open(io.BytesIO(response.content))

        name = str(uuid.uuid4())[:6]

        path = f"public/images/{name}.png"

        image.save(path)

        return {
            "generated_image": path
        }

    # --------------------------------
    # IMAGE → TEXT
    # --------------------------------

    def image_to_text(self, model, image_url):

        api = f"https://api-inference.huggingface.co/models/{model}"

        image_bytes = self.image_to_bytes(image_url)

        response = requests.post(
            api,
            headers=self.headers,
            data=image_bytes
        )

        data = response.json()

        if isinstance(data, list):
            return {"generated_text": data[0].get("generated_text")}

        return data

    # --------------------------------
    # OBJECT DETECTION
    # --------------------------------

    def object_detection(self, model, image_url):

        api = f"https://api-inference.huggingface.co/models/{model}"

        image_bytes = self.image_to_bytes(image_url)

        response = requests.post(
            api,
            headers=self.headers,
            data=image_bytes
        )

        return response.json()

    # --------------------------------
    # TEXT GENERATION
    # --------------------------------

    def text_generation(self, model, text):

        api = f"https://api-inference.huggingface.co/models/{model}"

        response = requests.post(
            api,
            headers=self.headers,
            json={"inputs": text}
        )

        data = response.json()

        if isinstance(data, list):
            return {"generated_text": data[0].get("generated_text")}

        return data

    # --------------------------------
    # TEXT → SPEECH
    # --------------------------------

    def text_to_speech(self, model, text):

        api = f"https://api-inference.huggingface.co/models/{model}"

        response = requests.post(
            api,
            headers=self.headers,
            json={"inputs": text}
        )

        name = str(uuid.uuid4())[:6]

        path = f"public/audios/{name}.flac"

        with open(path, "wb") as f:
            f.write(response.content)

        return {
            "generated_audio": path
        }


awesome_chat = AwesomeChatService()