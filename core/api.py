from fastapi import FastAPI
import uvicorn
import webbrowser

app = FastAPI()

@app.get("/command")
def command(text: str):

    print("Команда:", text)

    if "youtube" in text.lower():
        webbrowser.open("https://youtube.com")
        return {"answer": "Открываю YouTube"}

    return {"answer": "Команда не найдена"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)