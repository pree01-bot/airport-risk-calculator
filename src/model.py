import numpy as np
import requests
import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_MAPS_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# ── DELAY DATA FROM BTS ANALYSIS ────────────────────────────────────────────
# average delays by hour and day from BTS analysis
# these come directly from the EDA in Phase 3

DELAY_BY_HOUR = {
    0:15, 1:20, 2:12, 3:11, 4:6, 5:11, 6:8, 7:9,
    8:13, 9:14, 10:15, 11:16, 12:17, 13:18, 14:19,
    15:19, 16:19, 17:21, 18:21, 19:22, 20:22, 21:17, 22:15, 23:15
}

DELAY_BY_DAY = {
    0:18.4, 1:20.6, 2:11.1, 3:10.0, 4:17.5, 5:14.7, 6:16.1
}


# ── GOOGLE MAPS ──────────────────────────────────────────────────────────────

def get_travel_time_from_google(origin, destination):
    """
    Calls Google Maps Distance Matrix API to get real travel time
    between origin and destination in minutes.
    Also returns the resolved addresses Google Maps used.
    """
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": origin,
        "destinations": destination,
        "departure_time": "now",
        "traffic_model": "best_guess",
        "key": GOOGLE_MAPS_KEY
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        element = data["rows"][0]["elements"][0]
        if element["status"] == "OK":
            duration = element.get("duration_in_traffic", element["duration"])
            return {
                "travel_time": round(duration["value"] / 60),
                "origin_address": data.get("origin_addresses", [""])[0],
                "destination_address": data.get("destination_addresses", [""])[0]
            }
        return None
    except Exception:
        return None


# ── DYNAMIC BUFFER ───────────────────────────────────────────────────────────

def calculate_dynamic_buffer(flight_hour, day_of_week, base_buffer=90):
    """
    Adjusts the airport buffer based on real flight delay patterns.
    Higher delay risk at this hour/day means a larger buffer is recommended.
    """
    hour_delay = DELAY_BY_HOUR.get(flight_hour, 15)
    day_delay = DELAY_BY_DAY.get(day_of_week, 15)

    combined_delay = (hour_delay + day_delay) / 2
    baseline_delay = 15
    scaling_factor = combined_delay / baseline_delay
    dynamic_buffer = int(base_buffer * scaling_factor)

    # cap between 60 and 150 minutes
    dynamic_buffer = max(60, min(150, dynamic_buffer))

    return dynamic_buffer, round(hour_delay, 1), round(day_delay, 1)


# ── TRAVEL TIME DISTRIBUTION ─────────────────────────────────────────────────

def get_travel_time_distribution(base_travel_time, std_dev=None, n_samples=10000):
    """
    Generates a log-normal distribution of travel times.
    Standard deviation scales with travel time if not provided.
    """
    if std_dev is None:
        std_dev = max(5, base_travel_time * 0.33)
    mu = np.log(base_travel_time**2 / np.sqrt(base_travel_time**2 + std_dev**2))
    sigma = np.sqrt(np.log(1 + (std_dev**2 / base_travel_time**2)))
    np.random.seed(42)
    return np.random.lognormal(mu, sigma, n_samples)


# ── MAIN MODEL ───────────────────────────────────────────────────────────────

def calculate_optimal_departure(
    base_travel_time,
    airport_buffer=90,
    cost_of_missing=480,
    cost_per_minute_early=1,
    flight_hour=None,
    day_of_week=None
):
    """
    Calculates the optimal departure time given travel time and risk parameters.
    If flight_hour and day_of_week are provided, dynamically adjusts airport
    buffer based on real BTS delay patterns from Phase 3 analysis.
    """
    # use dynamic buffer if flight time provided
    if flight_hour is not None and day_of_week is not None:
        airport_buffer, hour_delay, day_delay = calculate_dynamic_buffer(
            flight_hour, day_of_week, airport_buffer
        )
        delay_context = {
            'dynamic_buffer_used': airport_buffer,
            'avg_delay_this_hour': hour_delay,
            'avg_delay_this_day': day_delay
        }
    else:
        delay_context = {
            'dynamic_buffer_used': airport_buffer,
            'avg_delay_this_hour': None,
            'avg_delay_this_day': None
        }

    simulated_times = get_travel_time_distribution(base_travel_time)
    departure_buffers = np.arange(30, 300, 1)
    expected_costs = []

    for buffer in departure_buffers:
        expected_wait = buffer - base_travel_time - airport_buffer
        prob_miss = np.mean(simulated_times > (buffer - airport_buffer))
        expected_wait_cost = max(0, expected_wait) * cost_per_minute_early
        expected_miss_cost = prob_miss * cost_of_missing
        total_cost = expected_wait_cost + expected_miss_cost
        expected_costs.append(total_cost)

    optimal_idx = np.argmin(expected_costs)
    optimal_buffer = departure_buffers[optimal_idx]
    prob_miss_at_optimal = np.mean(
        simulated_times > (optimal_buffer - airport_buffer)
    ) * 100
    expected_wait = max(0, optimal_buffer - base_travel_time - airport_buffer)

    return {
        'optimal_departure_minutes': int(optimal_buffer),
        'probability_of_missing': round(float(prob_miss_at_optimal), 2),
        'expected_wait_minutes': int(expected_wait),
        'departure_buffers': departure_buffers.tolist(),
        'expected_costs': [round(c, 2) for c in expected_costs],
        **delay_context
    }