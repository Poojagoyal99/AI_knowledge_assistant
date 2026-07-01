class ChatMemory:

    def __init__(self, max_pairs=3):
        self.history = []
        self.max_pairs = max_pairs

    def add_message(self, role, text):

        self.history.append(
            f"{role}: {text}"
        )

        # Keep only the last N question-answer pairs (2 messages per pair)
        max_messages = self.max_pairs * 2
        if len(self.history) > max_messages:
            self.history = self.history[-max_messages:]

    def get_history(self):

        return "\n".join(self.history)

    def clear(self):
        self.history = []
