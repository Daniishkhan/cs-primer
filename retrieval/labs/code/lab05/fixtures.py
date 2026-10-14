"""fixtures.py: the stand-in language model of Lab 5. GIVEN.

!! This is not a language model. !! It is a script: for each of the lab's questions it knows what a
quote-first model might plausibly write, INCLUDING the mistakes real models make, and it writes
that, quoting from whichever source label in the prompt holds the text. So every answer below is
real and reproducible, and each defect is placed where a particular gate has to catch it:

    q01 q02 q03 q04 q11 q12   faithful answers (some quote across a line break, a ligature, a
                              different case): a good verifier must ACCEPT them
    q05                       a quote with one number changed (25 pence became 30): fabricated
    q06                       a real quote under a label that is not in the prompt: bad pointer
    q07                       a real quote, a claim it does not support: unsupported
    q08                       a plausible slip ('start of the school year' for 'start of term')
                              that a crude support check cannot see: it gets through
    q09                       the model says the sources do not contain the answer: abstention
    q10                       no answer exists, so the model invents one around a real quote that
                              is not in the prompt
    q13                       a supported claim and a second claim with no citation at all
    q14                       a faithful answer, but retrieval never finds the document, so the model
                              quotes from memory under a label that holds other text

The model reads the prompt your code built: it finds the label of the context line that contains
each quote, so if your assemble() labels sources differently from the lab's contract the quotes
will not resolve. If the document it wants is not in the prompt at all, it quotes under S1, as a
model recalling text from memory would.
"""
import re
import unicodedata

from llm import RuleModel

SCRIPT = {
    "q01": [("The annual charge for a second vehicle is 120 pounds.", "parking",
             "The annual charge is 65 pounds for the first vehicle and 120 pounds for a second vehicle.")],
    "q02": [("Permits are issued online within 2 working days.", "parking",
             "Permits are issued online within 2 working days of a complete application.")],
    "q03": [("A third vehicle at the same address is not eligible.", "parking",
             "A third vehicle at the same address is not eligible for a permit.")],
    "q04": [("A lost or stolen permit can be replaced for a fee of 15 pounds.", "parking",
             "A lost or stolen permit can be replaced for a fee of 15 pounds"),
            ("The replacement is valid only until the end of the original permit year.", "parking",
             "the replacement is valid only until the end of the original permit year")],
    "q05": [("The late fee is 30 pence a day for each overdue book.", "library",
             "The late fee is 30 pence a day for each overdue book, capped at 5 pounds per item.")],
    "q06": [("Members may borrow up to 12 items at a time.", "library",
             "Members may borrow up to 12 items at a time", "S9")],
    "q07": [("Garden waste is free of charge.", "waste",
             "Garden waste collection is a paid service and costs 52 pounds a year per bin.")],
    "q08": [("Applications must be received at least 6 weeks before the start of the school year.", "school-travel",
             "Applications must be received at least 6 weeks before the start of term.")],
    "q09": None,
    "q10": [("A taxi licence costs 80 pounds a year.", "parking",
             "The annual charge is 65 pounds for the first vehicle and 120 pounds for a second vehicle.")],
    "q11": [("The final reply is sent within 20 working days.", "complaints",
             "the final reply is sent within 20 working days")],
    "q12": [("A single adult living alone gets a 25 per cent discount.", "council-tax",
             "A single adult living alone is entitled to a discount of 25 per cent.")],
    "q13": [("Children who live more than 3 miles from their nearest suitable school are eligible for a free travel pass.",
             "school-travel",
             "Children who live more than 3 miles from their nearest suitable school are eligible for a free travel pass.")],
    "q14": [("A lost pass can be replaced once a year for 10 pounds.", "school-travel",
             "A lost pass can be replaced once a year for 10 pounds.")],
}
UNCITED = {"q13": ["Pupils with an education plan may qualify at a shorter distance."]}


def _fold(s):
    return " ".join(unicodedata.normalize("NFKC", s).casefold().split())


def make_model(questions):
    """A RuleModel that answers the lab's questions from SCRIPT. `questions` is data.QUESTIONS."""
    by_text = {q[1]: q[0] for q in questions}

    def respond(match):
        prompt = match.string
        question = prompt.rsplit("Question:", 1)[1].strip()
        qid = by_text.get(question)
        if qid is None:
            return "<quotes>NONE</quotes><answer>I cannot find that in the sources.</answer>"
        entry = SCRIPT.get(qid)
        if entry is None:
            return "<quotes>NONE</quotes><answer>The sources do not say.</answer>"
        lines = re.findall(r"^\[(S\d+)\] \(([^)]*)\) (.*)$", prompt, re.M)
        quotes, answer = [], []
        for i, item in enumerate(entry, 1):
            claim, doc, quote = item[0], item[1], item[2]
            label = item[3] if len(item) > 3 else None
            if label is None:
                hit = [lab for lab, d, t in lines if _fold(quote) in _fold(t)]
                same_doc = [lab for lab, d, t in lines if d == doc]
                label = (hit or same_doc or ["S1"])[0]
            quotes.append(f'<quote id="q{i}" src="{label}">{quote}</quote>')
            answer.append(f"{claim} [q{i}]")
        answer += UNCITED.get(qid, [])
        return "<quotes>\n" + "\n".join(quotes) + "\n</quotes>\n<answer>\n" + " ".join(answer) + "\n</answer>"

    return RuleModel([(r"Question:", respond)])
