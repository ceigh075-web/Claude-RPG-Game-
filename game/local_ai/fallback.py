"""Template dialogue used when the local model is unavailable (and as the Phase-2 dialogue layer).

Lines are shaped by personality so NPCs still sound different without the model.
"""
from ..core.rng import stable_rng


def _p(npc, trait):
    return npc["personality"][trait]


def tone(npc):
    f, a, c = _p(npc, "friendliness"), _p(npc, "aggression"), _p(npc, "confidence")
    if a >= 7 and f <= 4:
        return "hostile"
    if f >= 8:
        return "warm"
    if c >= 8 and f <= 5:
        return "proud"
    if _p(npc, "sociability") <= 3:
        return "terse"
    if _p(npc, "greed") >= 8:
        return "mercenary"
    return "neutral"


OPENERS = {
    "warm": ["Good to see you again!", "Oh, it's you! Come, sit a moment.", "There you are."],
    "hostile": ["You again.", "What now?", "Make it quick."],
    "proud": ["Hm. Back again?", "You have my attention. Briefly.", "Well?"],
    "terse": ["...Yes?", "Mm.", "What is it."],
    "mercenary": ["Ah, a returning customer, I hope.", "Time is marks, friend.", "Back with coin?"],
    "neutral": ["Hello again.", "Back again, then?", "Afternoon."],
}

ABOUT_FRAMES = {
    "warm": "Oh, me? Well... {bg}",
    "hostile": "Why do you care? Fine. {bg}",
    "proud": "You haven't heard of me? {bg}",
    "terse": "{bg_short}",
    "mercenary": "My story's worth more than you're paying, but here: {bg}",
    "neutral": "Not much to tell. {bg}",
}

PLACE_FRAMES = {
    "warm": "{desc} I love it here, honestly. You should try: {acts}.",
    "hostile": "{desc} Don't cause trouble.",
    "proud": "{desc} Best place in the region, if you ask me. People come for: {acts}.",
    "terse": "{desc}",
    "mercenary": "{desc} Money to be made, if you're sharp: {acts}.",
    "neutral": "{desc} Folks mostly come for: {acts}.",
}


def greeting(npc, state, first_meeting):
    if first_meeting:
        return npc["greeting"]
    r = stable_rng(npc["id"], state.clock.day_index, state.clock.hour)
    return r.choice(OPENERS[tone(npc)])


def about(npc):
    t = tone(npc)
    bg = npc["background"]
    return ABOUT_FRAMES[t].format(bg=bg, bg_short=bg.split(".")[0] + ".")


def place(npc, state):
    loc = state.data.location(npc["home"])
    acts = ", ".join(a.lower() for a in loc.get("activities", [loc.get("reason", "the quiet")]))
    return PLACE_FRAMES[tone(npc)].format(desc=loc["description"], acts=acts)


def rumor(npc, state):
    r = stable_rng(npc["id"], "rumor", state.clock.day_index)
    line = r.choice(state.data.rumors)
    if _p(npc, "honesty") <= 3:
        return f"Between you and me... {line} Or so I'd have you believe."
    if _p(npc, "sociability") >= 8:
        return f"Oh, have you heard? {line}"
    return line


def recruit_hint(npc):
    rq = npc["recruit"]
    t = tone(npc)
    bits = []
    if "gold" in rq:
        bits.append(f"I don't work for free. {rq['gold']} marks, and I'm yours.")
    if "favor_desc" in rq:
        bits.append(f"If you want me along: {rq['favor_desc']}")
    if "friendship" in rq and not bits:
        bits.append("Travel with you? Maybe. Once I know you better.")
    if "respect" in rq and not any("marks" in b for b in bits):
        bits.append("Show me you can handle yourself first.")
    if "rep" in rq:
        fac = next(iter(rq["rep"]))
        bits.append(f"My people would have to trust you first. ({fac.title()} standing {rq['rep'][fac]}+)")
    if not bits:
        bits.append("Maybe one day.")
    prefix = {"hostile": "Ha! ", "warm": "Oh! ", "terse": ""}.get(t, "")
    return prefix + " ".join(bits)


def farewell(npc):
    return {"warm": "Take care of yourself out there!", "hostile": "Finally.", "proud": "You may go.",
            "terse": "Bye.", "mercenary": "Come back with more coin.", "neutral": "Safe travels."}[tone(npc)]
