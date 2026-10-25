import uuid
import torch
from transformers import pipeline
from diffusers import StableDiffusionPipeline
from PIL import Image
import flask
from flask import request, jsonify
from flask_cors import CORS

app = flask.Flask(__name__)
CORS(app)

print("Loading models...")

caption_model = pipeline(
    "image-to-text",
    model="ydshieh/vit-gpt2-coco-en"
)

object_model = pipeline(
    "object-detection",
    model="facebook/detr-resnet-50"
)

asr_model = pipeline(
    "automatic-speech-recognition",
    model="openai/whisper-base"
)

sd_model = StableDiffusionPipeline.from_pretrained(
    "runwayml/stable-diffusion-v1-5",
    torch_dtype=torch.float16
)

sd_model.to("cuda")

print("Models loaded")


@app.route("/caption", methods=["POST"])
def caption():

    image_path = request.json["image"]

    result = caption_model(image_path)

    return jsonify(result)


@app.route("/detect", methods=["POST"])
def detect():

    image_path = request.json["image"]

    result = object_model(image_path)

    return jsonify(result)


@app.route("/generate_image", methods=["POST"])
def generate():

    prompt = request.json["text"]

    image = sd_model(prompt).images[0]

    filename = f"public/images/{uuid.uuid4().hex}.png"

    image.save(filename)

    return jsonify({"image": filename})


@app.route("/speech_to_text", methods=["POST"])
def speech():

    audio_path = request.json["audio"]

    result = asr_model(audio_path)

    return jsonify(result)


@app.route("/running")
def running():

    return {"status": "ok"}


if __name__ == "__main__":

    app.run(port=5005)