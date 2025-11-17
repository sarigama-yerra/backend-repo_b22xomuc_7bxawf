import os
from typing import List, Literal, Optional
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Ride-Hailing Interactive Deck API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CityRow(BaseModel):
    city: str
    avg_weekly_hours: int
    avg_takehome_before_costs: int
    avg_takehome_after_costs: int
    pct_female_drivers: float
    pct_uninsured: float
    vehicle: Literal["car", "bike"] = "car"


# In a real app, fetch from DB; here we serve static sample data (no PII/persistence required)
SAMPLE_DATA: List[CityRow] = [
    CityRow(city="Islamabad", avg_weekly_hours=76, avg_takehome_before_costs=28000, avg_takehome_after_costs=19000, pct_female_drivers=1.0, pct_uninsured=78.0, vehicle="car"),
    CityRow(city="Lahore", avg_weekly_hours=82, avg_takehome_before_costs=30000, avg_takehome_after_costs=19500, pct_female_drivers=0.5, pct_uninsured=82.0, vehicle="car"),
    CityRow(city="Karachi", avg_weekly_hours=85, avg_takehome_before_costs=31500, avg_takehome_after_costs=20000, pct_female_drivers=0.7, pct_uninsured=80.0, vehicle="car"),
    # bike variations to enable vehicle filtering
    CityRow(city="Islamabad", avg_weekly_hours=70, avg_takehome_before_costs=24000, avg_takehome_after_costs=16500, pct_female_drivers=1.2, pct_uninsured=76.0, vehicle="bike"),
    CityRow(city="Lahore", avg_weekly_hours=78, avg_takehome_before_costs=25500, avg_takehome_after_costs=17000, pct_female_drivers=0.6, pct_uninsured=81.0, vehicle="bike"),
    CityRow(city="Karachi", avg_weekly_hours=80, avg_takehome_before_costs=26500, avg_takehome_after_costs=17400, pct_female_drivers=0.8, pct_uninsured=79.0, vehicle="bike"),
]


@app.get("/")
def read_root():
    return {"message": "Ride-Hailing Deck API is running"}


@app.get("/api/summary")
def summary():
    return {
        "labor": {
            "headline": "Precarity & long hours",
            "stat": ">75 hrs/week typical",
            "quote": "Drivers often work 12–14 hrs to meet costs.",
        },
        "safety": {
            "headline": "Gender & safety barriers",
            "stat": "<1% women drivers",
            "note": "Night travel perceived higher risk; safety features uneven.",
        },
        "algorithm": {
            "headline": "Algorithmic management",
            "note": "Visibility and earnings tied to ratings, GPS, and dispatch.",
        },
        "policy": {
            "headline": "Policy gaps",
            "note": "Limited social protection, transparency, and grievance routes.",
        },
    }


@app.get("/api/chart-data", response_model=List[CityRow])
def chart_data(city: Optional[str] = None, vehicle: Optional[str] = None):
    data = SAMPLE_DATA
    if city:
        data = [d for d in data if d.city.lower() == city.lower()]
    if vehicle:
        data = [d for d in data if d.vehicle == vehicle]
    return data


class SimInput(BaseModel):
    hours_online: int
    fuel_cost_per_liter: float
    km_driven: int
    base_fare_per_km: float
    algorithm_bonus: float = 0.0  # percentage e.g., 0.05 = +5%
    algorithm_penalty: float = 0.0  # percentage e.g., 0.10 = -10%


@app.post("/api/simulate")
def simulate_day(inp: SimInput):
    gross_income = inp.km_driven * inp.base_fare_per_km
    gross_income *= (1 + inp.algorithm_bonus)
    gross_income *= (1 - inp.algorithm_penalty)

    fuel_eff_km_per_l = 18 if inp.km_driven < 120 else 16
    liters = inp.km_driven / fuel_eff_km_per_l
    fuel_cost = liters * inp.fuel_cost_per_liter

    maintenance = 0.08 * gross_income
    platform_fee = 0.12 * gross_income

    net_takehome = gross_income - (fuel_cost + maintenance + platform_fee)

    # Simple stress index heuristic
    stress = 50
    if inp.hours_online > 10:
        stress += (inp.hours_online - 10) * 4
    if inp.algorithm_penalty > 0:
        stress += int(inp.algorithm_penalty * 100) // 2
    stress = max(0, min(100, stress))

    return {
        "gross_income": round(gross_income, 2),
        "fuel_cost": round(fuel_cost, 2),
        "maintenance": round(maintenance, 2),
        "platform_fee": round(platform_fee, 2),
        "net_takehome": round(net_takehome, 2),
        "stress_index": stress,
    }


@app.get("/api/platform-comparison")
def platform_comparison(
    scenario: Literal["short", "peak", "long"] = Query("short"),
    proposed_fare: float = Query(300.0, ge=50.0, le=3000.0),
):
    # Yango-like fixed fare model (simplified)
    base_per_km = 35.0
    km = 4.0 if scenario == "short" else (10.0 if scenario == "peak" else 18.0)
    surge = 1.0 if scenario == "short" else (1.35 if scenario == "peak" else 1.1)
    yango_fare = round(base_per_km * km * surge + 60, 0)

    # inDrive-like negotiation: acceptance probability declines away from a target range
    fair_range_low = 30 * km
    fair_range_high = 55 * km
    if proposed_fare < fair_range_low:
        acceptance = max(0.05, (proposed_fare / fair_range_low))
    elif proposed_fare > fair_range_high:
        # very high fare still accepted but capped
        acceptance = 0.95 - min(0.4, (proposed_fare - fair_range_high) / (fair_range_high))
    else:
        # sweet spot
        acceptance = 0.75 + 0.2 * ((proposed_fare - fair_range_low) / (fair_range_high - fair_range_low))

    beneficiary = "driver" if proposed_fare > yango_fare else ("passenger" if proposed_fare < yango_fare else "balanced")

    return {
        "scenario": scenario,
        "yango_fare": yango_fare,
        "indrive_proposed": proposed_fare,
        "acceptance_prob": round(acceptance, 2),
        "beneficiary": beneficiary,
        "km": km,
    }


@app.get("/api/voices")
def voices():
    return {
        "driver": "Most days I’m online 12 to 14 hours just to cover fuel and payments. A small change in fare or a low rating can wipe out my profit. I keep driving because there aren’t many options.",
        "female_rider": "Ride-hailing helps me move around the city, but nights are tricky. I check the driver rating, share my trip, and still feel uneasy. Safety features help, but trust is fragile.",
        "platform_rep": "We balance rider affordability and driver earnings using dynamic pricing and ratings. We’re testing safety tools and support features, but we’re also listening to feedback from local communities.",
    }


@app.get("/api/timeline")
def timeline():
    return [
        {"year": 2019, "label": "inDrive grows in major cities"},
        {"year": 2021, "label": "Fairwork reports highlight platform labor issues"},
        {"year": 2022, "label": "Women-only options expand; VSisters noted"},
        {"year": 2023, "label": "Yango expands; pricing algorithms mature"},
        {"year": 2024, "label": "New research on costs, hours, safety perceptions"},
        {"year": 2025, "label": "Policy debates on transparency & protections"},
    ]


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        from database import db
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = getattr(db, 'name', None) or ("✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set")
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
                response["connection_status"] = "Connected"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
    except Exception:
        pass
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
