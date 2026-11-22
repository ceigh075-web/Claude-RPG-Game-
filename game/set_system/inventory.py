"""Item stacks, weight and equipment slots."""


class InventoryError(Exception):
    pass


class Inventory:
    def __init__(self, data=None):
        self.items = {}  # item_id -> qty (insertion order = display order)
        self.data = data

    def bind(self, data):
        self.data = data
        return self

    def count(self, item_id):
        return self.items.get(item_id, 0)

    def has(self, item_id, qty=1):
        return self.count(item_id) >= qty

    def add(self, item_id, qty=1):
        if qty <= 0:
            return
        if self.data is not None:
            self.data.item(item_id)  # raises on unknown item
        self.items[item_id] = self.items.get(item_id, 0) + qty

    def remove(self, item_id, qty=1):
        have = self.count(item_id)
        if qty > have:
            raise InventoryError(f"not enough {item_id}: have {have}, need {qty}")
        if have == qty:
            del self.items[item_id]
        else:
            self.items[item_id] = have - qty

    def total_weight(self):
        if self.data is None:
            return 0.0
        return round(sum(self.data.item(i)["weight"] * q for i, q in self.items.items()), 2)

    def total_value(self):
        return sum(self.data.item(i)["value"] * q for i, q in self.items.items())

    def by_type(self, *types):
        return [(i, q) for i, q in self.items.items() if self.data.item(i)["type"] in types]

    def to_dict(self):
        return dict(self.items)

    @classmethod
    def from_dict(cls, d, data=None):
        inv = cls(data)
        inv.items = {k: int(v) for k, v in d.items() if v > 0}
        return inv
