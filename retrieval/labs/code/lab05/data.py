"""data.py: the document collection and the question set of Lab 5. GIVEN.

Six short policy documents of the invented Harbourside Council (the same council as Lab 6), written
as a document-conversion step would hand them over: titles on their own line, a sentence broken
across a line, a double space, a non-breaking space, a ligature ("ﬁ" for "fi") and a curly
apostrophe. Those are the formatting accidents a verbatim-quote check has to survive.

Everything here is constructed for teaching. Fourteen questions are an illustration of the
mechanics, not evidence about any real system (chapter 5 says how large a judged set must be).
"""

DOCS = {
    "parking": (
        "Residents' Parking Permits\n\n"
        "A resident whose home is inside a controlled parking zone may apply for one permit for each vehicle "
        "registered at that address. The annual charge is 65 pounds for the first vehicle and 120 pounds for a "
        "second vehicle. A third vehicle at the same address is not eligible for a permit. Permits are issued "
        "online within 2 working days of a complete\napplication. A lost or stolen permit can be replaced for a "
        "fee of 15 pounds,  and the replacement is valid only until the end of the original permit year. Visitor "
        "vouchers are sold in books of ten and each voucher is valid for one day."
    ),
    "library": (
        "Library Loans and Fines\n\n"
        "Members may borrow up to 12 items at a time, and each item can be renewed twice online. Books are lent "
        "for 21 days and DVDs for 7 days. The late fee is 25 pence a day for each overdue book, capped at "
        "5 pounds per item. Fees for children's books are waived. A member who owes more than 10 pounds cannot "
        "borrow until the balance is paid. Lost items are charged at the replacement price shown in the catalogue."
    ),
    "waste": (
        "Household Waste and Recycling\n\n"
        "Rubbish is collected every second week, and recycling and food waste are collected every week. Garden "
        "waste collection is a paid service and costs 52 pounds a year per bin. Bins must be on the pavement by "
        "7am on collection day. Bulky items such as sofas and fridges are collected for a charge of 20 pounds "
        "for up to three items, and booking is required at least 3 working days ahead. The last collection "
        "before a bank holiday takes place the day after."
    ),
    "school-travel": (
        "School Travel Passes\n\n"
        "Children who live more than 3 miles from their nearest suitable school are eligible for a free travel "
        "pass. Applications must be received at least 6 weeks before the start of term. A lost pass can be "
        "replaced once a year for 10 pounds. Passes are valid on all council-contracted buses. Pupils with an "
        "education plan may qualify at a shorter distance, and the council will review each case."
    ),
    "complaints": (
        "Making a Complaint\n\n"
        "A complaint is acknowledged within 5 working days, and the ﬁnal reply is sent within 20 working "
        "days. You must make a complaint within 12 months of the event that caused it. Complaints about council "
        "tax bills are handled by the revenues team, not by the complaints oﬃce. If you are not "
        "satisﬁed with the reply, you can ask for a review by a director. The ombudsman can only be "
        "contacted after the council’s own process has ended."
    ),
    "council-tax": (
        "Council Tax Payments\n\n"
        "Council tax is due in 10 monthly instalments from April to January. Payment by direct debit can be "
        "made on the 1st, 15th or 28th of the month. A single adult living alone is entitled to a discount of "
        "25 per cent. Households in which everyone is a full-time student pay nothing. An unpaid bill triggers "
        "a reminder after 14 days and a final notice after 28 days. Court action begins only after the final "
        "notice has been ignored."
    ),
}
DOCS["parking"] = DOCS["parking"].replace("2 working days", "2 working days")      # a non-breaking space

# qid, question, answerable, a phrase a correct answer must contain (lower case), the document that holds it
QUESTIONS = [
    ("q01", "How much is a residents' parking permit for a second vehicle?", True, "120 pounds", "parking"),
    ("q02", "How soon is a parking permit issued after applying?", True, "2 working days", "parking"),
    ("q03", "Can I get a parking permit for a third vehicle?", True, "not eligible", "parking"),
    ("q04", "What does a replacement parking permit cost, and how long does it last?", True, "15 pounds", "parking"),
    ("q05", "What is the late fee for an overdue library book?", True, "25 pence", "library"),
    ("q06", "How many items can a library member borrow at once?", True, "12 items", "library"),
    ("q07", "Is garden waste collection free?", True, "52 pounds", "waste"),
    ("q08", "When must a school travel pass application be received?", True, "start of term", "school-travel"),
    ("q09", "Does the council offer free bicycle repairs?", False, None, None),
    ("q10", "How much does a taxi licence cost for a year?", False, None, None),
    ("q11", "How long until a complaint gets its final reply?", True, "20 working days", "complaints"),
    ("q12", "What discount does a single adult living alone get on council tax?", True, "25 per cent", "council-tax"),
    ("q13", "Who is eligible for a school travel pass?", True, "3 miles", "school-travel"),
    ("q14", "What does a replacement for a stolen season ticket cost?", True, "10 pounds", "school-travel"),
]
