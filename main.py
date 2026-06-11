from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.model import calculate_optimal_departure, get_travel_time_from_google
from typing import Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RISK_PROFILES = {
    "tolerant": 240,
    "moderate": 480,
    "averse": 960
}

class TripInput(BaseModel):
    origin: Optional[str] = None
    destination: Optional[str] = None
    travel_time_minutes: Optional[int] = None
    risk_tolerance: str = "moderate"
    airport_buffer: int = 90

@app.get("/")
def root():
    return {"status": "Airport Risk Calculator API is running"}

@app.post("/calculate")
def calculate(input: TripInput):
    # use Google Maps if origin and destination provided
    travel_time = None
    source = "manual"

    if input.origin and input.destination:
        travel_time = get_travel_time_from_google(input.origin, input.destination)
        if travel_time:
            source = "google_maps"

    # fall back to manual input if Google Maps fails or not provided
    if not travel_time:
        travel_time = input.travel_time_minutes or 30

    cost_of_missing = RISK_PROFILES.get(input.risk_tolerance, 480)

    result = calculate_optimal_departure(
        base_travel_time=travel_time,
        airport_buffer=input.airport_buffer,
        cost_of_missing=cost_of_missing
    )

    result['travel_time_used'] = travel_time
    result['travel_time_source'] = source

    return result