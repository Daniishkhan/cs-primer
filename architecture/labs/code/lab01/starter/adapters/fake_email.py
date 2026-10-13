"""MILESTONE 5: a fake EmailSender that remembers what it was asked to send.

FakeEmail().send(to, subject, body) appends (to, subject, body) to self.sent.
"""


class FakeEmail:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, body):
        raise NotImplementedError("TODO milestone 5: FakeEmail.send")
