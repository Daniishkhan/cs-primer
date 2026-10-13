"""Private: how much does a parcel cost?"""


def cost_cents(grams):
    return 500 + (grams // 100) * 20
