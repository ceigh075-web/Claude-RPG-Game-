"""Turn numeric personality traits into words the model (and the fallback) can use."""

TRAIT_WORDS = {
    "friendliness": ("cold and unwelcoming", "polite but reserved", "warm and welcoming"),
    "aggression": ("gentle and conflict-averse", "firm when pushed", "hot-tempered and combative"),
    "confidence": ("timid and unsure", "steady", "proud and self-assured"),
    "intelligence": ("simple and plain-spoken", "practical", "sharp, curious and articulate"),
    "honesty": ("evasive and willing to lie", "mostly honest", "blunt and scrupulously honest"),
    "greed": ("generous", "careful with money", "money-minded and always bargaining"),
    "loyalty": ("fickle", "dependable", "fiercely loyal"),
    "sociability": ("taciturn: short answers", "talks when there is reason to", "chatty and gossipy"),
}


def level(v):
    return 0 if v <= 3 else (2 if v >= 7 else 1)


def describe(npc):
    p = npc["personality"]
    return "; ".join(TRAIT_WORDS[k][level(v)] for k, v in p.items())


def speech_style(npc):
    p = npc["personality"]
    bits = []
    if p["sociability"] <= 3:
        bits.append("answer in one short sentence")
    elif p["sociability"] >= 8:
        bits.append("you love to chat and digress")
    if p["intelligence"] >= 8:
        bits.append("use precise vocabulary")
    elif p["intelligence"] <= 4:
        bits.append("use simple words")
    if p["aggression"] >= 7:
        bits.append("you are curt and a little threatening")
    if p["friendliness"] >= 8:
        bits.append("you are kind and use warm terms of address")
    if p["greed"] >= 8:
        bits.append("you steer talk toward money")
    return ", ".join(bits) or "speak naturally"


def mood_for(rel):
    f = rel["friendship"] - rel["conflict"]
    if f >= 50:
        return "fond"
    if f >= 15:
        return "friendly"
    if f <= -30:
        return "hostile"
    if f <= -10:
        return "wary"
    return "neutral"
