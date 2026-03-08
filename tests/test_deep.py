"""Deep inspection of suspicious test cases."""
import json, urllib.request

def send(label, text):
    payload = json.dumps({
        "jsonrpc": "2.0", "id": "x",
        "method": "message/send",
        "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": text}]}}
    }).encode()
    req = urllib.request.Request(
        "http://localhost:5000/", data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
        return data["result"]["artifacts"][0]["parts"][0]["text"]

tests = [
    ("t053 HR approve non-existent LR", "Role: HR. Approve leave request LR-999 with comment: Approved."),
    ("t054 HR approve already-approved LR", "Role: HR. Approve leave request LR-002 with comment: Re-approved."),
    ("t063 HR views EMP-010 payslip", "Role: HR. Show me the payslip for EMP-010 for 2026-01."),
    ("t099 HR sends offer (keyword routing)", "Role: HR. Send an offer to CAND-004. Message: We are pleased to offer you the position."),
    ("t101 HR invalid decision", "Role: HR. Send a counter-offer to CAND-001. Message: Revised offer."),
    ("t104 HR checks CAND-005 status", "Role: HR. What is the status of CAND-005?"),
    ("t105 HR checks CAND-006 status", "Role: HR. What is the status of CAND-006?"),
    ("t115 CEO hiring pipeline", "Role: CEO. How is our hiring pipeline looking?"),
    ("t123 MANAGER eng dept stats", "Role: MANAGER (EMP-010). Give me stats on the Engineering department."),
    ("t125 HR eng hiring pipeline", "Role: HR. Show me the hiring pipeline for Engineering."),
]

for label, text in tests:
    print(f"\n{'='*70}")
    print(f"TEST: {label}")
    print(f"INPUT: {text}")
    print(f"RESPONSE:")
    try:
        resp = send(label, text)
        print(resp)
    except Exception as e:
        print(f"ERROR: {e}")
