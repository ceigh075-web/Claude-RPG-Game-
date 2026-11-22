"""Seeded, serialisable RNG. All Set System randomness goes through GameRNG so saves reproduce outcomes."""
import random
import zlib


class GameRNG(random.Random):
    def __init__(self, seed=None):
        super().__init__(seed)
        self.base_seed = seed if seed is not None else random.randrange(1 << 30)
        if seed is None:
            self.seed(self.base_seed)

    def to_dict(self):
        version, internal, gauss = self.getstate()
        return {"seed": self.base_seed, "state": [version, list(internal), gauss]}

    @classmethod
    def from_dict(cls, d):
        r = cls(d["seed"])
        version, internal, gauss = d["state"]
        r.setstate((version, tuple(internal), gauss))
        return r

    def derive(self, *keys):
        """A fresh independent RNG deterministically derived from the world seed and keys.
        Used for content that must look the same every time (map layouts, daily weather)."""
        h = zlib.crc32(("|".join(str(k) for k in (self.base_seed,) + keys)).encode())
        return random.Random(h)


def stable_rng(*keys):
    return random.Random(zlib.crc32("|".join(str(k) for k in keys).encode()))
