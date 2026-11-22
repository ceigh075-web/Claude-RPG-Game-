"""Minimal HTTP client for a locally running model. Supports Ollama and OpenAI-compatible servers
(llama.cpp `llama-server`, LM Studio, KoboldCpp, vLLM...). Standard library only; never blocks the game
loop (callers run it on a worker thread)."""
import json
import time
import urllib.error
import urllib.request

DEFAULTS = {"enabled": True, "backend": "ollama", "endpoint": "http://localhost:11434", "model": "llama3.2:3b",
            "timeout_seconds": 20, "temperature": 0.8, "max_tokens": 220}


class LLMError(Exception):
    pass


class LLMClient:
    def __init__(self, config=None):
        cfg = dict(DEFAULTS)
        cfg.update(config or {})
        self.cfg = cfg
        self._avail = None
        self._avail_t = 0.0

    @property
    def enabled(self):
        return bool(self.cfg.get("enabled"))

    def _post(self, path, payload, timeout):
        url = self.cfg["endpoint"].rstrip("/") + path
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError) as e:
            raise LLMError(str(e)) from e

    def available(self, ttl=60.0):
        """Quick, cached reachability check (1.5 s timeout)."""
        if not self.enabled:
            return False
        now = time.time()
        if self._avail is not None and now - self._avail_t < ttl:
            return self._avail
        path = "/api/tags" if self.cfg["backend"] == "ollama" else "/v1/models"
        try:
            with urllib.request.urlopen(self.cfg["endpoint"].rstrip("/") + path, timeout=1.5) as r:
                self._avail = r.status == 200
        except (urllib.error.URLError, OSError, ValueError):
            self._avail = False
        self._avail_t = now
        return self._avail

    def chat(self, messages):
        """Send chat messages; return the assistant's text (expected to be JSON)."""
        t = self.cfg["timeout_seconds"]
        if self.cfg["backend"] == "ollama":
            out = self._post("/api/chat", {"model": self.cfg["model"], "messages": messages, "stream": False,
                                           "format": "json", "options": {"temperature": self.cfg["temperature"],
                                                                         "num_predict": self.cfg["max_tokens"]}}, t)
            try:
                return out["message"]["content"]
            except (KeyError, TypeError) as e:
                raise LLMError(f"unexpected Ollama response: {out!r:.200}") from e
        out = self._post("/v1/chat/completions", {"model": self.cfg["model"], "messages": messages,
                                                  "temperature": self.cfg["temperature"],
                                                  "max_tokens": self.cfg["max_tokens"],
                                                  "response_format": {"type": "json_object"}}, t)
        try:
            return out["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError(f"unexpected OpenAI-style response: {out!r:.200}") from e
