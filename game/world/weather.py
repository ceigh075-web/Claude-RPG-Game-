"""Deterministic daily weather per biome, derived from the world seed."""

WEATHER = {
    "clear":    {"name": "Clear",    "speed": 1.0,  "water": 1.0,  "event_bonus": 0.0},
    "overcast": {"name": "Overcast", "speed": 1.0,  "water": 0.9,  "event_bonus": 0.0},
    "rain":     {"name": "Rain",     "speed": 0.85, "water": 0.7,  "event_bonus": 0.01},
    "storm":    {"name": "Storm",    "speed": 0.6,  "water": 0.8,  "event_bonus": 0.03},
    "snow":     {"name": "Snow",     "speed": 0.7,  "water": 0.9,  "event_bonus": 0.02},
    "heat":     {"name": "Scorching","speed": 0.9,  "water": 1.6,  "event_bonus": 0.0},
    "fog":      {"name": "Fog",      "speed": 0.85, "water": 0.9,  "event_bonus": 0.03},
}

BIOME_TABLES = {
    "grassland": [("clear", 45), ("overcast", 25), ("rain", 22), ("storm", 8)],
    "forest":    [("clear", 35), ("overcast", 30), ("rain", 25), ("fog", 10)],
    "hills":     [("clear", 40), ("overcast", 30), ("rain", 20), ("storm", 10)],
    "mountain":  [("clear", 35), ("overcast", 25), ("snow", 25), ("storm", 15)],
    "snow":      [("snow", 45), ("clear", 30), ("overcast", 15), ("storm", 10)],
    "desert":    [("clear", 50), ("heat", 38), ("storm", 12)],
    "coast":     [("clear", 40), ("overcast", 25), ("rain", 20), ("storm", 10), ("fog", 5)],
    "swamp":     [("rain", 35), ("overcast", 30), ("fog", 20), ("clear", 15)],
    "canyon":    [("clear", 50), ("heat", 35), ("storm", 15)],
    "volcanic":  [("heat", 55), ("overcast", 30), ("storm", 15)],
    "moor":      [("fog", 40), ("overcast", 30), ("rain", 20), ("clear", 10)],
    "ruins":     [("clear", 35), ("overcast", 30), ("fog", 20), ("rain", 15)],
    "cave":      [("overcast", 100)],
    "crystal":   [("clear", 60), ("overcast", 25), ("snow", 15)],
    "road":      [("clear", 45), ("overcast", 25), ("rain", 22), ("storm", 8)],
}


def weather_for(state, biome, day=None):
    day = state.clock.day_index if day is None else day
    table = BIOME_TABLES.get(biome, BIOME_TABLES["grassland"])
    r = state.rng.derive("weather", biome, day)
    total = sum(w for _, w in table)
    roll = r.uniform(0, total)
    for wid, w in table:
        roll -= w
        if roll <= 0:
            break
    if state.clock.season == "winter" and wid == "rain":
        wid = "snow"
    if state.clock.season == "summer" and wid == "snow" and biome not in ("snow", "mountain"):
        wid = "rain"
    return wid


def info(wid):
    return WEATHER[wid]
