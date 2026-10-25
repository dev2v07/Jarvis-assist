from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/command")
def command(text: str):

    if "youtube" in text.lower():
        return {"answer": "Открываю YouTube"}

    return {"answer": "Команда не найдена"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)