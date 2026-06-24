from fastapi import FastAPI
from src.schemas import PredictionRequest, PredictionResponse
from src.model import SentimentModel

app = FastAPI(title="SentimentAI", version="0.1.0")

# Le modÃ¨le est chargÃ© une seule fois au dÃ©marrage du serveur
model = SentimentModel()


@app.get("/health")
def health():
    """Endpoint de healthcheck utilisÃ© par Docker et les load balancers."""
    return {"status": "ok"}


@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest):
    """Analyse le sentiment du texte fourni et retourne un label + score."""
    return model.predict(request.text)
