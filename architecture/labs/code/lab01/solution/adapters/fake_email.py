"""A fake email sender that remembers what it was asked to send."""


class FakeEmail:
    def __init__(self):
        self.sent = []                           # (to, subject, body)

    def send(self, to, subject, body):
        self.sent.append((to, subject, body))
