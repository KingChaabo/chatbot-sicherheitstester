class FakeChatModel:
    """Test double for ChatModel: returns the given replies in order and records every call."""

    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.calls: list[dict] = []

    def chat(self, messages, *, json_schema=None, seed=None, temperature=None) -> str:
        self.calls.append(
            {
                "messages": messages,
                "json_schema": json_schema,
                "seed": seed,
                "temperature": temperature,
            }
        )
        if len(self.calls) > len(self.replies):
            raise AssertionError(
                f"FakeChatModel was called {len(self.calls)} times but only has "
                f"{len(self.replies)} replies"
            )
        return self.replies[len(self.calls) - 1]
