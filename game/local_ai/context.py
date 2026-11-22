"""Builds the model prompt for one NPC: who they are, what they know (Set AI memories, ranked by
importance), hard world facts that must not be contradicted, and the action whitelist."""
from ..core.clock import format_stamp
from ..set_system import factions, favors, relationships as rel
from . import personality
from .actions import WHITELIST

MEMORY_LIMIT = 8
HISTORY_TURNS = 6


def dead_npcs(state):
    facts = state.memory.facts_with_prefix("npc:")
    return [state.data.npcs[k.split(":")[1]]["name"] for k, v in facts.items()
            if k.endswith(":alive") and v is False and k.split(":")[1] in state.data.npcs]


def world_facts(state, npc):
    data = state.data
    loc = data.location(state.location)
    out = [f"Today is {state.clock.date_str()}, {state.clock.time_str()}. You are in {loc['name']}."]
    dead = dead_npcs(state)
    if dead:
        out.append("These people are DEAD (never speak of them as alive): " + ", ".join(dead) + ".")
    for k, label in (("hollow_broken", "The Hollow outlaws have been broken; Black Ren no longer leads them."),
                     ("peace_crown_thornblood", "The Crown and the Thornblood Clans have made peace."),
                     ("outpost_founded", "The player has founded an outpost at Widow's Crossing.")):
        if state.flags.get(k):
            out.append(label)
    for e in getattr(state, "world", {}).get("active_events", [])[-4:]:
        out.append("Current news: " + e.get("headline", ""))
    if npc.get("faction"):
        r = state.reputation.get(npc["faction"], 0)
        out.append(f"Your faction ({data.factions[npc['faction']]['name']}) regards the player as "
                   f"{factions.standing_label(r)}.")
    companions = [data.npcs[i]["name"] for i in state.companions] if hasattr(state, "companions") else []
    if companions:
        out.append("The player travels with: " + ", ".join(companions) + ".")
    return out


def memory_lines(state, npc):
    lines = []
    for m in state.memory.about(npc["id"], limit=MEMORY_LIMIT):
        lines.append(f"- ({format_stamp(m['day'])}) {m['description']}")
    for m in state.memory.about("player", limit=4, min_importance=3):
        line = f"- (heard) {m['description']}"
        if line not in lines:
            lines.append(line)
    for c in state.memory.chatter(npc["id"], 3):
        lines.append(f"- (small talk) {c['text']}")
    return lines


def system_prompt(state, npc):
    data = state.data
    r = rel.get(state, npc["id"])
    race = data.races[npc["race"]]["name"]
    fac = data.factions[npc["faction"]]["name"] if npc.get("faction") else "no faction"
    fid = favors.favor_of(npc)
    favor_line = ""
    if fid:
        st = favors.status(state, fid)
        d = favors.defs(data)[fid]
        favor_line = f"You need a favor: {d['desc']} (status: {st or 'not yet asked'})."
    p = state.player
    lines = [
        f"You are {npc['name']}, a {npc['age']}-year-old {race} {npc['occupation']} ({npc['pronouns']}) of {fac}, "
        f"in the world of Kindred Roads.",
        f"Background: {npc['background']}",
        f"Personality: {personality.describe(npc)}. Style: {personality.speech_style(npc)}.",
        f"You like {', '.join(npc['likes'])}; you dislike {', '.join(npc['dislikes'])}.",
        favor_line,
        f"The player is {p.name}, a {data.races[p.race]['name']} ({p.pronouns}), level {p.level}.",
        f"Your feelings toward them: friendship {r['friendship']}, trust {r['trust']}, affection {r['affection']}, "
        f"respect {r['respect']}, conflict {r['conflict']} (scale -100..100); romance: {r['romance']}; "
        f"mood: {personality.mood_for(r)}.",
        "FACTS (true, never contradict):", *world_facts(state, npc),
        "YOUR MEMORIES (true, most important first):", *(memory_lines(state, npc) or ["- You have not met before."]),
        "RULES: Speak only as yourself, in 1-3 sentences. Do not narrate the player's actions. You cannot give or "
        "take items, money, change stats, or invent past events; if something must happen in the game, request an "
        "action. Only use actions from this list:",
        *[f"  {k}: {v}" for k, v in WHITELIST.items()],
        'Reply ONLY with JSON: {"say": "...", "mood": "friendly|neutral|wary|hostile|fond", '
        '"requests": [{"action": "...", ...}]}',
    ]
    return "\n".join(l for l in lines if l)


def build_messages(state, npc, history, player_line, results=None):
    msgs = [{"role": "system", "content": system_prompt(state, npc)}]
    for turn in history[-HISTORY_TURNS:]:
        msgs.append({"role": "user", "content": turn["player"]})
        msgs.append({"role": "assistant", "content": turn["raw"]})
    content = player_line
    if results:
        content = "[game: results of your last requests: " + "; ".join(f"{r['action']} -> {r['result']}" for r in results) \
                  + "]\n" + player_line
    msgs.append({"role": "user", "content": content})
    return msgs
