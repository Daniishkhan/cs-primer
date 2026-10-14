"""Builds the judged collection for Lab 3: corpus.json, queries.json, qrels.txt.

    python3 make_data.py

Everything is written by hand or generated from a fixed seed, so the files never change.
The collection is CONSTRUCTED FOR TEACHING (about 330 short passages, 60 queries). It is
built so that four kinds of query behave differently:

    code     an exact identifier (an error code, a part number, a clause) in the query. Lexical
             matching is strong, sub-word similarity blurs near-identical identifiers.
    variant  the query uses another surface form of the document's words (cancelling / cancel,
             a typo, "e mail"). Sub-word similarity is strong, exact word matching is blind.
    order    two passages use the same words in opposite order ("from checking to savings"
             against "from savings to checking"). Neither first-stage retriever can tell them
             apart; a model that reads the pair can.
    plain    ordinary overlap in both words and sub-words; both retrievers do well.

Grades follow chapter 4: 3 answers the query, 2 good, 1 partly useful, 0 judged and not
relevant (a hard distractor). Passages that are not mentioned for a query are unjudged (0).
"""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
rng = random.Random(20261014)

DOCS = {}          # id -> text
QUERIES = []       # (qid, text, kind)
QRELS = {}         # qid -> {docid: grade}


def add_case(kind, text, docs):
    """docs: list of (grade, passage). Each case gets its own passages (ids c<qnum>-<i>)."""
    qid = f"q{len(QUERIES) + 1:02d}"
    QUERIES.append((qid, text, kind))
    QRELS[qid] = {}
    for i, (grade, passage) in enumerate(docs, 1):
        did = f"{qid}-{i}"
        DOCS[did] = passage
        QRELS[qid][did] = grade


# -----------------------------------------------------------------------------
# kind "code": 14 identifiers, each with near-identical neighbours that mean something else
# -----------------------------------------------------------------------------
CODES = [
    ("E4021", "payment gateway", "the card was declined because the billing address did not match", "Re-enter the address exactly as your bank holds it."),
    ("E5107", "report exporter", "the export ran out of memory on a very wide table", "Export fewer columns or split the date range."),
    ("KX-7731", "label printer", "the thermal head needs cleaning", "Wipe the head with an isopropyl swab and print a test label."),
    ("INV-20418", "billing team", "the invoice was issued twice by mistake", "Ignore the duplicate; the credit note is raised automatically."),
    ("TS-884", "network switch", "the uplink port is running at half duplex", "Replace the cable or force the port to full duplex."),
    ("clause 14.2", "supplier contract", "either side may end the agreement with ninety days written notice", "Send the notice to the registered address."),
    ("ORA-04031", "database server", "the shared pool is too small for the workload", "Raise the shared pool size and restart the instance."),
    ("HTTP 429", "public API", "the caller has sent too many requests in the window", "Back off and retry after the time in the Retry-After header."),
    ("form SA-302", "tax office", "the annual self assessment summary was generated", "Check the figures and keep the form for six years."),
    ("part 55-1204", "pump assembly", "the shaft seal is the replacement for the older model", "Fit the seal with the lip facing the fluid."),
    ("VPN-619", "remote access gateway", "the certificate has expired", "Install the renewed certificate from the self service page."),
    ("SKU 90417-B", "winter jacket", "the size chart is for the slim fit in blue", "Order one size up for layering."),
    ("CVE-2024-3094", "compression library", "a backdoor was found in two release tarballs", "Downgrade to a clean release and rotate exposed keys."),
    ("DX-9006", "door controller", "the badge reader lost contact with the controller", "Check the wiring at the reader and power cycle the controller."),
]
OTHER = [
    "the session timed out while waiting for a response", "the disk is almost full", "the licence key is not recognised",
    "the firmware update is waiting for a restart", "the request body is larger than the limit", "the account is locked after repeated failures",
    "the scheduled job was skipped because the previous run was still going", "the queue is paused by an administrator",
    "the connection was reset by the remote side", "the file type is not supported",
]


def neighbours(code):
    """Identifiers that look almost the same: change the last character, or the last two."""
    out = []
    head, last = code[:-1], code[-1]
    if last.isdigit():
        for delta in (1, 2, 7):
            out.append(head + str((int(last) + delta) % 10))
        out.append(code[:-2] + code[-1] + code[-2])
    else:
        out += [head + c for c in "ACD" if c != last][:3]
    seen, uniq = {code}, []
    for c in out:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq[:3]


for code, thing, meaning, action in CODES:
    near = neighbours(code)
    pool = rng.sample(OTHER, 3)
    docs = [(3, f"{code} on the {thing}: {meaning}. {action}")]
    for c, m in zip(near, pool):
        docs.append((0, f"{c} on the {thing}: {m}. Contact support if it persists."))
    docs.append((1, f"Codes for the {thing} are listed by family. The first letters name the subsystem and the digits name the condition."))
    add_case("code", rng.choice([f"what does {code} mean", f"{code} {thing}", f"how to fix {code}"]), docs)

# -----------------------------------------------------------------------------
# kind "variant": the query uses other surface forms of the passage's words
# -----------------------------------------------------------------------------
VARIANT = [
    ("cancelling subscriptions ahead of renewals",
     "To cancel a subscription, open Billing and choose Cancel plan. Cancel at least two days before the renewal date and no further charge is made.",
     "A subscription renews automatically at the end of its term unless it has been cancelled.",
     "Cancel an order within one hour of placing it; after that the parcel is already being packed."),
    ("reimbursment for damagd parcels",
     "If your parcel arrives damaged, send a photo within seven days and we will reimburse the item or send a replacement.",
     "Damage in transit is covered by the carrier, and claims are handled by our returns team.",
     "Parcels are tracked from dispatch to delivery, and you will see every scan on the tracking page."),
    ("pasword reseting mail never arrives",
     "If the password reset email does not arrive, check your spam folder and request a new link. Reset links expire after one hour.",
     "Choose a password of at least twelve characters; a passphrase of four words works well.",
     "Reset the router by holding the button for ten seconds; the wifi password returns to the one on the label."),
    ("recieve notifcations via e mail",
     "Choose how you receive notifications: email, text message or push alert, under Settings and then Notifications.",
     "Email is sent from the no-reply address, so add it to your contacts to keep it out of spam.",
     "Notification of a change to the terms is given at least thirty days before it takes effect."),
    ("invoicing reminders and lateness fees",
     "Customers who pay late receive a reminder after seven days and a late fee after thirty days; the invoice shows both.",
     "Payment terms are thirty days from the invoice date unless the contract says otherwise.",
     "Invoice numbers run in sequence and are never reused, even for a cancelled invoice."),
    ("renewing passports from abroad",
     "A passport can be renewed from outside the country through the nearest embassy; allow eight weeks for the renewal.",
     "Passport photographs must be recent, in colour, with a plain light background and no glasses.",
     "Visa renewals are handled separately and take longer than a passport renewal."),
    ("employers terminating contracts without warning",
     "An employer who terminates a contract without giving the notice required must pay the notice period instead.",
     "The notice period is stated in the employment contract and increases with length of service.",
     "Employees may be terminated at once for gross misconduct, after a documented hearing."),
    ("withdrawing consents to market mailings",
     "You can withdraw your consent to marketing emails at any time with the unsubscribe link in each message.",
     "We keep a record of when consent was given and what you were told, as the law requires.",
     "Service emails, such as receipts and password resets, are not marketing and are always sent."),
    ("rescheduling an appointment two times",
     "An appointment can be rescheduled twice free of charge; after that a booking fee applies.",
     "Appointments can be booked up to ninety days ahead, online or by phone.",
     "Missed appointments are charged at the full rate unless twenty-four hours notice was given."),
    ("deleting accounts and personal data",
     "To delete your account, open Privacy and choose Delete account. We erase your personal data within thirty days.",
     "Some records, such as invoices, must be kept for seven years and are not erased on request.",
     "Deleting a file moves it to the bin for thirty days before it is permanently removed."),
    ("stocktakes at the warehouses",
     "Stocktaking is carried out each quarter: count every shelf, compare the count with the system and record the differences.",
     "Differences over two percent of a line's value are investigated by the warehouse manager.",
     "Warehouse staff must wear safety shoes and high visibility vests on the picking floor."),
    ("unlocking a locked-out profile",
     "If you are locked out after five failed attempts, the profile unlocks automatically after fifteen minutes.",
     "To avoid lockouts, use the password manager and the saved sign-in on trusted devices.",
     "Profiles that are inactive for two years are archived and can be restored on request."),
    ("refilling a prescription online",
     "Repeat prescriptions can be refilled online: choose the medicine and a pharmacy for collection.",
     "A repeat prescription is reviewed by the doctor once a year, and the review is booked automatically.",
     "Prescriptions for controlled medicines cannot be repeated and need a new appointment."),
    ("international shipments and customs duty",
     "International orders may be charged customs duties on delivery; the duty depends on the destination country.",
     "We ship to forty countries. Delivery takes five to ten working days depending on the destination.",
     "Customs forms are completed for you; you do not need to attach anything to the parcel."),
    ("refundable deposits for tenants",
     "The deposit is refundable at the end of the tenancy, minus lawful deductions for damage or unpaid rent.",
     "The landlord must protect the deposit in an approved scheme within thirty days of receiving it.",
     "A holding deposit reserves the property for fifteen days and is not part of the tenancy deposit."),
    ("encrypted backup at rest",
     "Backups are encrypted at rest with AES-256 and the keys are stored separately from the data.",
     "Backups run nightly and are kept for thirty days in a second region.",
     "Encryption in transit uses TLS 1.3 between the application and the database."),
    ("authentication via hardware key",
     "Authentication with a hardware key is supported under Settings and Security, alongside an authenticator app.",
     "If you lose your hardware key, use one of your recovery codes to sign in and register a new key.",
     "Keys for the API are created under Developer settings and shown once at creation."),
    ("scheduling maintenance windows",
     "Maintenance windows are scheduled for Sundays between 02:00 and 04:00; services may be briefly unavailable.",
     "Planned work is announced on the status page at least five days in advance.",
     "Unplanned outages are posted to the status page within fifteen minutes of detection."),
]
for q, rel, part, dist in VARIANT:
    add_case("variant", q, [(3, rel), (1, part), (0, dist)])

# -----------------------------------------------------------------------------
# kind "order": the same words, opposite direction
# -----------------------------------------------------------------------------
ORDER = [
    ("move money from checking to savings",
     "To move money from {a} to {b}, open Transfers and choose {a} as the source and {b} as the destination.",
     "checking", "savings", "Transfers between your own accounts are instant and free."),
    ("send stock from the Leeds warehouse to the Bristol warehouse",
     "Request a stock transfer from the {a} warehouse to the {b} warehouse using form ST-2; stock leaves {a} on the next run.",
     "Leeds", "Bristol", "Transfers between sites are collected on weekdays and arrive the next working day."),
    ("migrate a database from MySQL to PostgreSQL",
     "Guide to migrating a database from {a} to {b}: export the schema, convert the types, then load the data into {b}.",
     "MySQL", "PostgreSQL", "Before any migration, take a full backup and agree a rollback plan."),
    ("upgrade from the basic plan to the premium plan",
     "To change from the {a} plan to the {b} plan, open Billing and pick Change plan; the new price applies from the same day.",
     "basic", "premium", "Plan changes are prorated, so you only pay for the days you use."),
    ("translate documents from German into Japanese",
     "Translate documents from {a} into {b} with the Language menu; the original {a} text is kept beside the {b} version.",
     "German", "Japanese", "Machine translation should be reviewed by a person before a document is sent to a customer."),
    ("convert euros to dollars on the travel card",
     "On the travel card, convert {a} to {b} in the Currency tab; the rate is fixed for one hour once you convert {a} to {b}.",
     "euros", "dollars", "Fees for currency exchange are shown before you confirm."),
    ("convert meeting times from London time to Tokyo time",
     "Convert meeting times from {a} time to {b} time with the Calendar settings; invitations show both {a} and {b} times.",
     "London", "Tokyo", "Daylight saving changes on different dates in different countries, so check dates near the change."),
    ("forward requests from the proxy to the origin server",
     "Configure the gateway to forward requests from the {a} to the {b}, and to forward the response from the {b} back through the {a}.",
     "proxy", "origin server", "Timeouts should be set on both sides of the gateway, with the inner timeout shorter."),
    ("reassign tickets from support to engineering",
     "To reassign a ticket from {a} to {b}, use Assign team; the ticket keeps its history and {b} is notified.",
     "support", "engineering", "Tickets that are reassigned more than twice are flagged for review."),
    ("copy files from the laptop to the server",
     "To copy files from the {a} to the {b}, use the sync tool: choose the {a} folder as the source and the {b} as the target.",
     "laptop", "server", "Files are encrypted while they are copied and checked afterwards with a checksum."),
    ("refer patients from the clinic to the hospital",
     "To refer a patient from the {a} to the {b}, complete the referral form; the {b} confirms the appointment with the {a}.",
     "clinic", "hospital", "Urgent referrals are phoned through as well as sent in writing."),
    ("sublet from the tenant to a friend",
     "A tenant may sublet only with the landlord's written consent; the rights pass from the {a} to the {b} for the agreed period.",
     "tenant", "friend", "The original tenant stays responsible for the rent while the property is sublet."),
]
for q, tpl, a, b, general in ORDER:
    right = tpl.format(a=a, b=b)
    wrong = tpl.format(a=b, b=a)
    add_case("order", q, [(3, right), (0, wrong), (1, general)])

# -----------------------------------------------------------------------------
# kind "plain": ordinary overlap, some with a long keyword-stuffed distractor
# -----------------------------------------------------------------------------
PLAIN = [
    ("how long does standard delivery take",
     "Standard delivery takes three to five working days. Express delivery arrives the next day if you order before noon.",
     "Delivery times are shown at checkout and depend on the delivery address.",
     "Delivery drivers must carry identification and wear the company uniform at all times."),
    ("what is the refund policy for gift cards",
     "Gift cards are not refundable and cannot be exchanged for cash. A lost card can be replaced if you have the receipt.",
     "Gift cards are valid for two years from the date of purchase.",
     "Refund policy: refunds, refunds, refunds. Our refund policy covers refund requests, refund times and refund amounts for every refund."),
    ("when must the landlord return the deposit",
     "The landlord must return the deposit within fourteen days after the tenancy ends, minus lawful deductions.",
     "Disputes about deductions from the deposit are decided by the deposit protection scheme.",
     "A landlord must give a tenant twenty-four hours notice before entering the property."),
    ("how many days of annual leave do full-time staff get",
     "Full-time staff receive twenty-five days of annual leave a year. Request leave through the portal at least two weeks ahead.",
     "Part-time staff receive annual leave in proportion to their hours.",
     "Sick leave must be reported to the manager before the shift starts."),
    ("how do I enable two-factor authentication",
     "Enable two-factor authentication in Settings, then Security. You can use an authenticator app or a hardware key.",
     "Two-factor authentication is required for administrators and recommended for everyone.",
     "Authentication failures are logged and reviewed by the security team every week."),
    ("what are the daily transfer limits",
     "Daily transfer limits are 5,000 for standard accounts and 25,000 for premium accounts.",
     "Transfers above the limit need approval from a second signatory.",
     "Transfer of ownership of an account requires a signed form and identification."),
    ("how do I book a blood test",
     "You can book a blood test online or by phone. Fasting is required for some tests, and the booking confirmation says which.",
     "Results are usually ready within three working days and are shared through the patient portal.",
     "Blood donation sessions run every Tuesday at the health centre."),
    ("how long are api keys valid",
     "API keys do not expire, but you should rotate them every ninety days. Revoked keys stop working immediately.",
     "API keys are shown once, at creation, so store them in a secrets manager.",
     "API documentation is versioned; old versions are supported for eighteen months."),
    ("what documents do I need to apply for a parking permit",
     "Apply for a parking permit with proof of address and your vehicle registration document.",
     "A permit is valid for one year and is tied to a single vehicle.",
     "Parking fines can be challenged within twenty-eight days of the notice."),
    ("how do I dispute an invoice",
     "To dispute an invoice, contact billing within thirty days and include the invoice number.",
     "Disputed amounts are put on hold while the dispute is reviewed.",
     "Invoice, invoice, invoice: this page lists every invoice format, invoice template and invoice number rule for each invoice."),
    ("when are council tax bills sent",
     "Council tax bills are sent in March. Late payment may lead to a reminder and then to court costs.",
     "You can pay council tax monthly by direct debit over ten months.",
     "Council meetings are open to the public and are held on the first Monday of the month."),
    ("how do I report a security incident",
     "Report a security incident by emailing the security team with the time, your account and what you observed.",
     "Do not delete anything on the affected machine until the security team has looked at it.",
     "Security badges must be worn visibly in the office and returned when you leave."),
    ("how long do I have to claim expenses",
     "Expense claims must be submitted within thirty days with receipts attached.",
     "Claims above five hundred need approval from your director.",
     "Travel must be booked through the company portal to get the negotiated fares."),
    ("how do I track my parcel",
     "Track your parcel with the tracking number in your dispatch email.",
     "If the tracking page has not changed for three days, contact support with the number.",
     "Parcel lockers are available in every store and are open all day."),
    ("what happens if a payment is declined",
     "If a payment is declined, check the card details and the billing address, then try again or use another card.",
     "Banks may decline a payment they think is unusual; contact your bank to approve it.",
     "A declined appeal can be taken to the tribunal within twenty-eight days."),
    ("can I change my delivery address after ordering",
     "You can change the delivery address until the order is dispatched; open the order and choose Edit address.",
     "After dispatch, a parcel can be redirected only by the carrier, and a fee may apply.",
     "The billing address must match the address held by the card issuer."),
]
for q, rel, part, dist in PLAIN:
    add_case("plain", q, [(3, rel), (1, part), (0, dist)])

# -----------------------------------------------------------------------------
# filler passages: plausible text on the same topics, unjudged for every query
# -----------------------------------------------------------------------------
SUBJ = ["Customers", "Members", "Staff", "Tenants", "Patients", "Applicants", "Account holders", "Suppliers", "Visitors", "Administrators"]
ACT = ["can update", "must confirm", "should review", "may request", "are asked to check", "need to renew", "can download", "are reminded to keep"]
OBJ = ["their contact details", "the direct debit mandate", "the signed agreement", "the delivery preferences", "their booking", "the privacy settings",
       "the monthly statement", "the training record", "the insurance certificate", "the access badge", "the shared folder", "the support history",
       "the opening hours", "the price list", "the service level", "the warranty terms", "the order history", "the meeting notes"]
WHEN = ["at any time in the portal.", "once a year.", "before the end of the month.", "within five working days.", "after the first sixty days.",
        "when something changes.", "during the quarterly review.", "by phone or in writing.", "from the Help menu.", "at the front desk."]
EXTRA = ["Ask the team if you are unsure.", "A copy is kept for audit.", "There is no charge for this.", "Large files may take longer.",
         "Changes take effect the next day.", "Older versions are archived.", "Support is available on weekdays.", "The form is on the intranet."]
for i in range(1, 171):
    DOCS[f"f{i:03d}"] = f"{rng.choice(SUBJ)} {rng.choice(ACT)} {rng.choice(OBJ)} {rng.choice(WHEN)} {rng.choice(EXTRA)}"

# -----------------------------------------------------------------------------
# opaque ids: shuffle so an id never hints at which passage is the answer (ties are broken by id)
old_ids = sorted(DOCS)
rng.shuffle(old_ids)
RENAME = {old: f"d{i:04d}" for i, old in enumerate(old_ids, 1)}
DOCS = {RENAME[d]: t for d, t in DOCS.items()}
QRELS = {q: {RENAME[d]: g for d, g in v.items()} for q, v in QRELS.items()}

if __name__ == "__main__":
    ids = sorted(DOCS)
    with open(os.path.join(HERE, "corpus.json"), "w", encoding="utf-8") as fh:
        json.dump({d: DOCS[d] for d in ids}, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    with open(os.path.join(HERE, "queries.json"), "w", encoding="utf-8") as fh:
        json.dump([{"qid": q, "text": t, "kind": k} for q, t, k in QUERIES], fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    with open(os.path.join(HERE, "qrels.txt"), "w", encoding="utf-8") as fh:
        fh.write("# qid iteration docid grade   (3 answers it, 2 good, 1 partly useful, 0 judged not relevant)\n")
        for q, _, _ in QUERIES:
            for d in sorted(QRELS[q]):
                fh.write(f"{q} 0 {d} {QRELS[q][d]}\n")
    kinds = {}
    for _, _, k in QUERIES:
        kinds[k] = kinds.get(k, 0) + 1
    print(f"{len(DOCS)} passages, {len(QUERIES)} queries {kinds}, "
          f"{sum(len(v) for v in QRELS.values())} judgements")
