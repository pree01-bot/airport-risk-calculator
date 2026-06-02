from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.model import calculate_optimal_departure

app = FastAPI()

# this allows the portfolio website to talk to the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# defines what inputs the calculator accepts
class TripInput(BaseModel):
    travel_time_minutes: int
    risk_tolerance: str  # "tolerant", "moderate", "averse"

# maps risk tolerance labels to cost values
RISK_PROFILES = {
    "tolerant": 240,
    "moderate": 480,
    "averse": 960
}

@app.get("/")
def root():
    return {"status": "Airport Risk Calculator API is running"}

@app.post("/calculate")
def calculate(input: TripInput):
    cost_of_missing = RISK_PROFILES.get(input.risk_tolerance, 480)
    
    result = calculate_optimal_departure(
        base_travel_time=input.travel_time_minutes,
        cost_of_missing=cost_of_missing
    )
    
    return result