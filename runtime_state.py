from collections import deque


class MessageDeduper:
    def __init__(self, max_ids: int = 512):
        self._max_ids = max_ids
        self._order = deque()
        self._seen = set()

    def seen(self, message_id: str) -> bool:
        if message_id in self._seen:
            return True
        self._seen.add(message_id)
        self._order.append(message_id)
        while len(self._order) > self._max_ids:
            oldest = self._order.popleft()
            self._seen.discard(oldest)
        return False
