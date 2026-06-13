from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.model import calculate_optimal_departure, get_travel_time_from_google
from typing import Optional
from datetime import datetime
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
    flight_time: Optional[str] = None  # format "HH:MM" e.g. "18:30"
    flight_date: Optional[str] = None  # format "YYYY-MM-DD" e.g. "2024-06-15"

@app.post("/calculate")
def calculate(input: TripInput):
    # parse flight hour and day of week if provided
    flight_hour = None
    day_of_week = None

    if input.flight_time:
        try:
            flight_hour = int(input.flight_time.split(":")[0])
        except:
            pass

    if input.flight_date:
        try:
            day_of_week = datetime.strptime(input.flight_date, "%Y-%m-%d").weekday()
        except:
            pass

    # get travel time from Google Maps or manual input
    travel_time = None
    source = "manual"
    origin_address = None
    destination_address = None

    if input.origin and input.destination:
        maps_result = get_travel_time_from_google(input.origin, input.destination)
        if maps_result:
            travel_time = maps_result["travel_time"]
            origin_address = maps_result["origin_address"]
            destination_address = maps_result["destination_address"]
            source = "google_maps"

    if not travel_time:
        travel_time = input.travel_time_minutes or 30

    cost_of_missing = RISK_PROFILES.get(input.risk_tolerance, 480)

    result = calculate_optimal_departure(
        base_travel_time=travel_time,
        airport_buffer=input.airport_buffer,
        cost_of_missing=cost_of_missing,
        flight_hour=flight_hour,
        day_of_week=day_of_week
    )

    result['travel_time_used'] = travel_time
    result['travel_time_source'] = source
    result['origin_address'] = origin_address
    result['destination_address'] = destination_address
    
    return result
