"""The ONLY way the Local AI can affect the game: by requesting whitelisted actions. The Set System validates
and executes (or rejects) each one and reports the outcome back to the conversation."""
from ..gameplay import npcs as npc_mod
from ..set_system import favors, recruitment, relationships as rel

WHITELIST = {
    "open_trade": "Offer to trade, if you are a merchant who is working now.",
    "share_rumor": "Share a piece of local news (the game supplies the true rumor).",
    "offer_favor": "Ask the player for the personal favor you need (only if you have one).",
    "check_favor": "Check whether the player has completed your favor.",
    "consider_joining": "The player asked you to join them: let the game check if you are willing and able.",
    "note_promise": "Record a promise the PLAYER made to you, with a short 'text'.",
    "set_tone": "Report how the player treated you this turn: 'tone' is kind, rude, flirty or neutral.",
    "end_conversation": "End the conversation.",
}
MAX_REQUESTS = 3


def execute(state, npc, request):
    """Validate and run one request. Returns {"action", "ok", "result", "ui"} where ui asks the scene to do
    something (e.g. open the shop or a recruitment confirmation)."""
    if not isinstance(request, dict):
        return {"action": "?", "ok": False, "result": "malformed request"}
    a = request.get("action")
    if a not in WHITELIST:
        return {"action": str(a)[:30], "ok": False, "result": "not allowed"}
    out = {"action": a, "ok": False, "result": "", "ui": None}
    if a == "open_trade":
        if not npc.get("shop"):
            out["result"] = "you are not a merchant"
        else:
            _, at_work = npc_mod.shopkeeper(state, state.location, npc["shop"])
            out.update(ok=at_work, result="shop opened" if at_work else "you are off work now", ui="trade" if at_work else None)
    elif a == "share_rumor":
        from . import fallback
        out.update(ok=True, result=fallback.rumor(npc, state))
    elif a == "offer_favor":
        ok, msg = favors.start(state, npc)
        out.update(ok=ok, result=msg)
    elif a == "check_favor":
        ok, msg = favors.complete(state, npc)
        out.update(ok=ok, result=msg)
    elif a == "consider_joining":
        ok, why = recruitment.can_recruit(state, npc)
        out.update(ok=ok, result="requirements met" if ok else f"not willing yet ({why})", ui="recruit" if ok else None)
    elif a == "note_promise":
        text = str(request.get("text", ""))[:120].strip()
        if not text:
            out["result"] = "empty promise"
        else:
            state.memory.record(npc["id"], "promise", f"{state.player.name} promised {npc['name']}: {text}",
                                day=state.clock.day_index, minute=state.clock.total_minutes % 1440, importance=3,
                                related=["player"], location=state.location, source="local_ai")
            out.update(ok=True, result="promise remembered")
    elif a == "set_tone":
        d = rel.apply_tone(state, npc, str(request.get("tone", "neutral")))
        out.update(ok=True, result=f"relationship change {d}" if d else "no change")
    elif a == "end_conversation":
        out.update(ok=True, result="goodbye", ui="end")
    return out


def execute_all(state, npc, requests):
    if not isinstance(requests, list):
        return []
    return [execute(state, npc, r) for r in requests[:MAX_REQUESTS]]
