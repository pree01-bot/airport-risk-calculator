import numpy as np
import requests
import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_MAPS_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

def get_travel_time_from_google(origin, destination):
    """
    Calls Google Maps Distance Matrix API to get real travel time
    between origin and destination in minutes.
    Returns None if the call fails.
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
            return round(duration["value"] / 60)  # convert seconds to minutes
        return None
    except Exception:
        return None


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


def calculate_optimal_departure(
    base_travel_time,
    airport_buffer=90,
    cost_of_missing=480,
    cost_per_minute_early=1
):
    """
    Calculates the optimal departure time given travel time and risk parameters.
    Returns recommendation plus full cost curve data for the chart.
    """
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
    prob_miss_at_optimal = np.mean(simulated_times > (optimal_buffer - airport_buffer)) * 100
    expected_wait = max(0, optimal_buffer - base_travel_time - airport_buffer)

    return {
        'optimal_departure_minutes': int(optimal_buffer),
        'probability_of_missing': round(float(prob_miss_at_optimal), 2),
        'expected_wait_minutes': int(expected_wait),
        'departure_buffers': departure_buffers.tolist(),
        'expected_costs': [round(c, 2) for c in expected_costs]
    }