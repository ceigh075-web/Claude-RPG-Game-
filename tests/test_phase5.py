"""Phase 5: Local AI integration (with a fake local model server), action validation, Set AI consistency,
favors, recruitment requirements, relationships and romance."""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from game.core.data import GameData
from game.core.state import GameState
from game.local_ai import context
from game.local_ai.client import LLMClient
from game.local_ai.dialogue import DialogueEngine, parse_reply
from game.set_system import favors, recruitment, relationships as rel

DATA = GameData()


def new_state():
    return GameState.new_game(DATA, "Tess", "human", {"race": "human"}, "she/her", seed=11)


class FakeModel:
    """A tiny local HTTP server speaking the Ollama and OpenAI chat APIs with scripted replies."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"models": []}')

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append((self.path, body))
                content = outer.replies.pop(0) if outer.replies else '{"say": "..."}'
                if self.path == "/api/chat":
                    out = {"message": {"role": "assistant", "content": content}}
                else:
                    out = {"choices": [{"message": {"role": "assistant", "content": content}}]}
                data = json.dumps(out).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(data)

        self.server = HTTPServer(("127.0.0.1", 0), H)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def client(self, backend="ollama"):
        return LLMClient({"enabled": True, "backend": backend, "endpoint": f"http://127.0.0.1:{self.port}",
                          "model": "test", "timeout_seconds": 5})

    def close(self):
        self.server.shutdown()


class TestAI(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_reply('blah {"say": "Hi", "requests": []} trailing')["say"], "Hi")
        self.assertIsNone(parse_reply("no json"))
        self.assertIsNone(parse_reply('{"mood": "x"}'))
        self.assertEqual(parse_reply('{"say": "Hi", "requests": "bad"}')["requests"], [])

    def test_ai_reply_and_validated_actions(self):
        s = new_state()
        npc = DATA.npcs["hessa"]
        s.clock.minutes = 10 * 60
        fm = FakeModel(['{"say": "Of course, dear.", "mood": "friendly", "requests": ['
                        '{"action": "open_trade"}, {"action": "give_gold", "amount": 999},'
                        '{"action": "note_promise", "text": "bring me apples"}]}'])
        try:
            eng = DialogueEngine(s, npc, client=fm.client())
            gold = s.gold
            out = eng.respond("Can I buy something?")
            self.assertEqual(out["source"], "ai")
            self.assertEqual(out["say"], "Of course, dear.")
            res = {r["action"]: r for r in out["results"]}
            self.assertTrue(res["open_trade"]["ok"])
            self.assertFalse(res["give_gold"]["ok"])          # not whitelisted
            self.assertEqual(s.gold, gold)                     # AI cannot create money
            self.assertTrue(any(m["source"] == "local_ai" and "apples" in m["description"]
                                for m in s.memory.about("hessa")))
            sysmsg = fm.requests[0][1]["messages"][0]["content"]
            self.assertIn("Hessa Moorweld", sysmsg)
            self.assertIn("Reply ONLY with JSON", sysmsg)
        finally:
            fm.close()

    def test_openai_backend(self):
        s = new_state()
        fm = FakeModel(['{"say": "Hm.", "requests": []}'])
        try:
            out = DialogueEngine(s, DATA.npcs["grint"], client=fm.client("openai")).respond("Hello")
            self.assertEqual(out["say"], "Hm.")
            self.assertEqual(fm.requests[0][0], "/v1/chat/completions")
        finally:
            fm.close()

    def test_dead_npc_consistency_guard(self):
        s = new_state()
        s.memory.set_fact("npc:garrow:alive", False, 0)
        fm = FakeModel(['{"say": "Garrow is doing well, he sends his regards."}',
                        '{"say": "Old Garrow sends his regards from the fence line."}'])
        try:
            out = DialogueEngine(s, DATA.npcs["tobin"], client=fm.client()).respond("How is Garrow?")
            self.assertEqual(out["source"], "fallback")       # both model replies contradicted history
            self.assertIn("DEAD", context.system_prompt(s, DATA.npcs["tobin"]))
        finally:
            fm.close()

    def test_fallback_when_model_unreachable(self):
        s = new_state()
        c = LLMClient({"enabled": True, "endpoint": "http://127.0.0.1:9", "backend": "ollama"})
        out = DialogueEngine(s, DATA.npcs["wren"], client=c).respond("Who are you?", "about")
        self.assertEqual(out["source"], "fallback")
        self.assertTrue(out["say"])

    def test_threaded_path_touches_state_only_on_main_thread(self):
        import time
        s = new_state()
        fm = FakeModel(['{"say": "Busy.", "requests": [{"action": "note_promise", "text": "help later"}]}'])
        try:
            for client in (fm.client(), LLMClient({"enabled": False})):
                eng = DialogueEngine(s, DATA.npcs["ruda"], client=client)
                eng.start("Hello", None)
                out = None
                for _ in range(200):
                    out = eng.poll()
                    if out:
                        break
                    time.sleep(0.01)
                self.assertIsNotNone(out)
                self.assertTrue(out["say"])
            self.assertTrue(any("help later" in m["description"] for m in s.memory.about("ruda")))
        finally:
            fm.close()

    def test_tone_is_bounded_daily(self):
        s = new_state()
        npc = DATA.npcs["lysa"]
        a = rel.apply_tone(s, npc, "rude")
        b = rel.apply_tone(s, npc, "rude")
        self.assertTrue(a)
        self.assertEqual(b, {})
        self.assertEqual(rel.get(s, "lysa")["friendship"], -4)

    def test_memories_in_context(self):
        s = new_state()
        s.memory.record("wren", "gift", "Tess gave Wren a flower.", day=0, importance=2, related=["player"])
        self.assertIn("gave Wren a flower", context.system_prompt(s, DATA.npcs["wren"]))


class TestFavorsRecruitment(unittest.TestCase):
    def test_deliver_favor_unlocks_recruit(self):
        s = new_state()
        npc = DATA.npcs["wren"]
        self.assertFalse(recruitment.can_recruit(s, npc)[0])
        ok, _ = favors.start(s, npc)
        self.assertTrue(ok)
        self.assertFalse(favors.complete(s, npc)[0])
        s.player.inventory.add("mirelight_herb", 3)
        ok, _ = favors.complete(s, npc)
        self.assertTrue(ok)
        self.assertEqual(s.player.inventory.count("mirelight_herb"), 0)
        rel.change(s, "wren", friendship=40)
        self.assertTrue(recruitment.can_recruit(s, npc)[0])

    def test_gold_requirement(self):
        s = new_state()
        npc = DATA.npcs["pell"]
        s.gold = 10
        self.assertFalse(recruitment.can_recruit(s, npc)[0])
        s.gold = 60
        self.assertTrue(recruitment.can_recruit(s, npc)[0])

    def test_clear_favor(self):
        s = new_state()
        npc = DATA.npcs["aubric"]
        favors.start(s, npc)
        ls = s.location_state("duskmoor")
        ls["group_count"] = 2
        ls["groups"] = {"duskmoor:0": {"defeated_at": s.clock.total_minutes + 5}}
        self.assertFalse(favors.progress(s, "aubric_husks")[0])
        ls["groups"]["duskmoor:1"] = {"defeated_at": s.clock.total_minutes + 9}
        self.assertTrue(favors.progress(s, "aubric_husks")[0])

    def test_alt_path(self):
        s = new_state()
        npc = DATA.npcs["black_ren"]
        self.assertFalse(recruitment.can_recruit(s, npc)[0])
        s.reputation["hollow"] = 60
        rel.change(s, "black_ren", respect=60)
        self.assertEqual(recruitment.can_recruit(s, npc), (True, "alt"))

    def test_every_npc_has_a_reachable_path(self):
        defs = favors.defs(DATA)
        for npc in DATA.npcs.values():
            req = npc["recruit"]
            if "favor" in req:
                self.assertIn(req["favor"], defs, npc["id"])


class TestRelationships(unittest.TestCase):
    def test_gifts(self):
        s = new_state()
        npc = DATA.npcs["wren"]  # likes herbs, dislikes weapons
        s.player.inventory.add("herbs", 2)
        ok, msg, d = rel.gift(s, npc, "herbs")
        self.assertTrue(ok)
        self.assertGreater(d["friendship"], 5)
        ok, msg, d = rel.gift(s, npc, "herbs")
        self.assertFalse(ok)  # one gift a day
        s.clock.advance(1440)
        s.player.inventory.add("dagger_rustite")
        ok, msg, d = rel.gift(s, npc, "dagger_rustite")
        self.assertLess(d["friendship"], 0)

    def test_romance_progression_and_jealousy(self):
        s = new_state()
        lysa, wren = DATA.npcs["lysa"], DATA.npcs["wren"]
        rel.note(s, "kindness", 10)
        rel.change(s, "lysa", affection=55, trust=55)
        self.assertEqual(rel.get(s, "lysa")["romance"], "interested")
        ok, _ = rel.ask_out(s, lysa)
        self.assertTrue(ok)
        self.assertFalse(rel.commit(s, lysa)[0])  # too soon / not enough affection
        rel.change(s, "lysa", affection=30)
        s.clock.advance(8 * 1440)
        self.assertTrue(rel.commit(s, lysa)[0])
        rel.change(s, "wren", affection=60)
        rel.ask_out(s, wren)
        self.assertLess(rel.get(s, "lysa")["affection"], 85)    # jealousy
        self.assertTrue(rel.breakup(s, "wren")[0])
        self.assertEqual(rel.get(s, "wren")["romance"], "broken")

    def test_unromanceable(self):
        s = new_state()
        rel.change(s, "garrow", affection=90)
        self.assertEqual(rel.get(s, "garrow")["romance"], "none")


if __name__ == "__main__":
    unittest.main()
