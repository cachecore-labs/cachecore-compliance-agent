"""8 compliance questions with 4 phrasing variants each.

Variants are semantically equivalent but lexically distinct, designed to
demonstrate L2 semantic cache matching across different sub-agents.

Each question maps to a list of 4 variants [A, B, C, D].
"""

QUESTIONS: dict[str, list[str]] = {
    # Q1 — Termination rights
    "Q1": [
        "Does this contract include a termination-for-convenience clause?",
        "Can either party terminate this agreement without specific grounds?",
        "Is there a provision allowing termination without cause?",
        "Does this contract permit early exit without fault by either party?",
    ],
    # Q2 — Payment terms
    "Q2": [
        "What are the payment terms and when are invoices due?",
        "How quickly must the buyer remit payment after receiving an invoice?",
        "What is the net payment period specified in this agreement?",
        "When does payment become due under this contract's terms?",
    ],
    # Q3 — Liability cap
    "Q3": [
        "Is there a cap on total liability under this contract?",
        "What is the maximum aggregate liability either party can face?",
        "Does this agreement limit the total financial exposure of each party?",
        "Is total liability capped at a specific dollar amount or formula?",
    ],
    # Q4 — Governing law
    "Q4": [
        "Which jurisdiction's laws govern this agreement?",
        "What is the governing law and venue specified in this contract?",
        "Under which state or country's legal framework is this contract enforced?",
        "What jurisdiction has been chosen to govern disputes under this agreement?",
    ],
    # Q5 — Confidentiality obligations
    "Q5": [
        "What confidentiality obligations does this contract impose?",
        "Are there non-disclosure requirements binding both parties?",
        "Does this agreement require the parties to keep information confidential?",
        "What restrictions exist on sharing proprietary information under this contract?",
    ],
    # Q6 — IP ownership
    "Q6": [
        "Who owns the intellectual property created under this contract?",
        "Does this agreement assign IP rights for work product to the buyer?",
        "How is ownership of deliverables and inventions allocated?",
        "Which party retains intellectual property rights over created works?",
    ],
    # Q7 — Dispute resolution
    "Q7": [
        "How are disputes resolved under this contract?",
        "Does the agreement require arbitration or mediation before litigation?",
        "What dispute resolution mechanism is specified in this contract?",
        "Is there a mandatory process for resolving disagreements between the parties?",
    ],
    # Q8 — Force majeure
    "Q8": [
        "Does this contract contain a force majeure clause?",
        "Are the parties excused from performance during extraordinary events?",
        "Is there a provision covering unforeseeable circumstances beyond either party's control?",
        "Does this agreement address liability relief for events like natural disasters or pandemics?",
    ],
}

# Variant labels for display
VARIANT_LABELS = ["A", "B", "C", "D"]
