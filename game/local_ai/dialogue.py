"""Dialogue engine: asks the local model for an NPC's reply (on a worker thread), validates it, executes the
requested actions through the Set System, and falls back to template dialogue when the model is missing,
slow, or produces something unusable."""
import json
import re
import threading

from ..core.rng import stable_rng
from ..set_system import favors, recruitment, relationships as rel
from . import actions, context, fallback
from .client import LLMClient, LLMError

DEATH_WORDS = ("dead", "died", "death", "killed", "late ", "grave", "buried", "passed", "mourn", "miss ", "funeral", "rest in")


def parse_reply(text):
    """Extract the JSON object from model output. Returns dict or None."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(d, dict) or not isinstance(d.get("say"), str) or not d["say"].strip():
        return None
    d["say"] = d["say"].strip()[:500]
    if not isinstance(d.get("requests"), list):
        d["requests"] = []
    return d


def consistent(dead_names, reply):
    """Reject replies that speak of the dead as if alive (Set AI history wins over the model)."""
    text = reply["say"].lower()
    titles = ("Old", "Sir", "Captain", "Warden", "Father", "Sister", "Master", "Guildmaster", "Archmage", "Warchief",
              "Queen", "Forewoman", "Sergeant")
    for name in dead_names:
        parts = name.split()
        key = (parts[1] if parts[0] in titles and len(parts) > 1 else parts[0]).lower()
        if key in text and not any(w in text for w in DEATH_WORDS):
            return False
    return True


class DialogueEngine:
    def __init__(self, state, npc, config=None, client=None):
        self.state = state
        self.npc = npc
        self.client = client or LLMClient((config or {}).get("ai"))
        self.history = []
        self.pending = None
        self.last_results = []
        self.source = "fallback"

    def ai_ready(self):
        return self.client.enabled and self.client.available()

    # ------------------------------------------------------------ model call (safe to run on a worker thread)
    def fetch(self, msgs, dead_names):
        """Network only: returns a validated reply dict or None. Touches no game state."""
        if not (self.client.enabled and self.client.available()):
            return None
        for _ in range(2):  # one retry on bad / inconsistent output
            try:
                raw = self.client.chat(msgs)
            except LLMError:
                return None
            reply = parse_reply(raw)
            if reply and consistent(dead_names, reply):
                reply["raw"] = raw
                return reply
        return None

    # ------------------------------------------------------------ main-thread completion
    def finish(self, player_line, topic, reply):
        """Validate/execute requests through the Set System and record memory. Main thread only."""
        if reply is None:
            reply = self.fallback_reply(player_line, topic)
            self.source = "fallback"
        else:
            self.source = "ai"
        results = actions.execute_all(self.state, self.npc, reply.get("requests", []))
        self.last_results = results
        self.history.append({"player": player_line, "raw": reply.get("raw") or json.dumps({"say": reply["say"]})})
        rel.talk(self.state, self.npc)
        self.state.memory.add_chatter(self.npc["id"], f"{self.state.player.name}: {player_line[:80]}",
                                      self.state.clock.day_index)
        for r in results:  # surface Set System outcomes the player should see
            if r["action"] in ("offer_favor", "check_favor") or (r["action"] == "share_rumor" and self.source == "ai"):
                if r["result"] and r["result"] not in reply["say"]:
                    reply["say"] += " " + r["result"]
        return {"say": reply["say"].strip(), "mood": reply.get("mood", "neutral"), "results": results,
                "source": self.source}

    def prepare(self, player_line):
        return (context.build_messages(self.state, self.npc, self.history, player_line, self.last_results),
                context.dead_npcs(self.state))

    def respond(self, player_line, topic=None):
        """Blocking convenience (tests, tools)."""
        msgs, dead = self.prepare(player_line)
        return self.finish(player_line, topic, self.fetch(msgs, dead))

    # ------------------------------------------------------------ async wrapper for the UI
    def start(self, player_line, topic=None):
        msgs, dead = self.prepare(player_line)
        box = {"done": False, "reply": None, "line": player_line, "topic": topic}
        self.pending = box

        def work():
            try:
                box["reply"] = self.fetch(msgs, dead)
            except Exception:  # never let a worker crash the game; fall back to templates
                box["reply"] = None
            box["done"] = True
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        box = self.pending
        if box and box["done"]:
            self.pending = None
            return self.finish(box["line"], box["topic"], box["reply"])
        return None

    # ------------------------------------------------------------ fallback (template) dialogue
    def fallback_reply(self, line, topic=None):
        npc, st = self.npc, self.state
        low = line.lower()
        req = []
        if topic == "about" or "who are you" in low or "yourself" in low:
            say = fallback.about(npc)
        elif topic == "place" or "this place" in low or "town" in low:
            say = fallback.place(npc, st)
        elif topic == "rumor" or any(w in low for w in ("news", "rumor", "rumour", "heard")):
            say = fallback.rumor(npc, st)
        elif topic == "trade" or any(w in low for w in ("trade", "buy", "sell", "shop")):
            say = "Let's see what you need." if npc.get("shop") else "I'm no merchant."
            if npc.get("shop"):
                req.append({"action": "open_trade"})
        elif topic == "favor" or any(w in low for w in ("favor", "favour", "help you", "need anything", "job")):
            fid = favors.favor_of(npc)
            if fid and favors.status(st, fid) == "active":
                req.append({"action": "check_favor"})
                say = "Have you done what I asked?"
            elif fid and not favors.status(st, fid):
                req.append({"action": "offer_favor"})
                say = "Since you ask... there is something."
            else:
                say = "I'm fine, thank you." if not fid else "You've already helped me more than enough."
        elif topic == "join" or any(w in low for w in ("join", "come with", "travel with", "recruit")):
            ok, _ = recruitment.can_recruit(st, npc)
            say = "Yes. I'll come with you." if ok else fallback.recruit_hint(npc)
            req.append({"action": "consider_joining"})
        elif any(w in low for w in ("bye", "farewell", "later")):
            say = fallback.farewell(npc)
            req.append({"action": "end_conversation"})
        else:
            tone = "rude" if any(w in low for w in ("idiot", "stupid", "shut up", "ugly", "hate")) else (
                "kind" if any(w in low for w in ("thank", "please", "friend", "kind", "sorry")) else "neutral")
            req.append({"action": "set_tone", "tone": tone})
            r = stable_rng(npc["id"], st.clock.day_index, len(self.history))
            if tone == "rude":
                say = {"hostile": "Say that again. I dare you.", "warm": "That... wasn't kind."}.get(fallback.tone(npc), "Mind your tongue.")
            elif tone == "kind":
                say = r.choice(["That's kind of you.", "I appreciate that.", "You're all right, you know."])
            else:
                say = r.choice(fallback.OPENERS[fallback.tone(npc)]) + " " + r.choice(
                    ["What else is on your mind?", "Anything else?", "Go on.", "Hm."])
        return {"say": say, "mood": "neutral", "requests": req}
