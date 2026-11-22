"""The world graph: 29 locations connected by routes with distance and terrain."""
import heapq
import math

KM_PER_UNIT = 1.5

# km/h multiplier for each route terrain
TERRAIN_SPEED = {
    "road": 1.15, "grassland": 1.0, "forest": 0.8, "hills": 0.8, "mountain": 0.6, "snow": 0.55,
    "desert": 0.7, "coast": 0.9, "swamp": 0.55, "canyon": 0.75, "volcanic": 0.6, "moor": 0.8, "ruins": 0.7,
}


class WorldMap:
    def __init__(self, data):
        self.data = data
        self.adj = {lid: {} for lid in data.locations}
        for a, b, terrain in data.routes:
            km = round(self.straight_km(a, b) * 1.15, 1)  # roads wind a little
            self.adj[a][b] = {"km": km, "terrain": terrain}
            self.adj[b][a] = {"km": km, "terrain": terrain}

    def pos(self, lid):
        return self.data.location(lid)["pos"]

    def straight_km(self, a, b):
        (x1, y1), (x2, y2) = self.pos(a), self.pos(b)
        return math.hypot(x2 - x1, y2 - y1) * KM_PER_UNIT

    def neighbors(self, lid):
        return sorted(self.adj[lid], key=lambda n: self.data.location(n)["name"])

    def route(self, a, b):
        return self.adj[a].get(b)

    def danger(self, lid):
        loc = self.data.location(lid)
        return loc.get("danger", 0)

    def route_danger(self, a, b):
        return max(self.danger(a), self.danger(b), 1)

    def direction(self, a, b):
        """Unit vector on the map from a toward b (y down)."""
        (x1, y1), (x2, y2) = self.pos(a), self.pos(b)
        dx, dy = x2 - x1, y2 - y1
        d = math.hypot(dx, dy) or 1.0
        return dx / d, dy / d

    def shortest_path(self, a, b):
        dist, prev = {a: 0.0}, {}
        pq = [(0.0, a)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == b:
                break
            if d > dist.get(u, 1e18):
                continue
            for v, r in self.adj[u].items():
                nd = d + r["km"]
                if nd < dist.get(v, 1e18):
                    dist[v], prev[v] = nd, u
                    heapq.heappush(pq, (nd, v))
        if b not in dist:
            return None, None
        path, cur = [b], b
        while cur != a:
            cur = prev[cur]
            path.append(cur)
        return list(reversed(path)), dist[b]
