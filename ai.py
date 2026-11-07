"""AI layer (Gemini): only for messy language. Falls back to canned output with no key."""
import json, os
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

def _client():
    key = os.environ.get("GEMINI_API_KEY")
    if not key: return None
    from google import genai
    return genai.Client(api_key=key)

INTAKE_PROMPT = """You are a refund-intake assistant for BharatTrip, a B2B travel company.
Read the raw message from a travel agent (may be English, Hindi or Hinglish) and return ONLY JSON:
{"agent_name": str|null, "route": str|null, "issue_type": "status_chase"|"new_request"|"dispute"|"other",
 "days_waiting": int|null, "urgency": "low"|"medium"|"high", "missing_info": [str],
 "reply": str}
Rules: reply must be short, polite, in the sender's language style, say a ticket has been created
with reference {ref}, and ask only for missing_info. Never promise an amount or a date."""

REPLY_PROMPT = """Draft a short, polite status message to a travel agent about their refund.
Use ONLY the facts below. Do not invent dates, reasons or amounts. If something is unknown, say
we are checking with Finance and will update within 1 working day. Facts: {facts}
Return plain text, max 70 words."""

def _gen(prompt, as_json=False):
    c = _client()
    if c is None:
        return None
    cfg = {"response_mime_type": "application/json"} if as_json else None
    try:
        return c.models.generate_content(model=MODEL, contents=prompt, config=cfg).text
    except Exception as e:
        print("Gemini error:", e)   # visible in the terminal
        return None

def parse_intake(message, ref="RF-NEW"):
    out = _gen(INTAKE_PROMPT.replace("{ref}", ref) + "\n\nMESSAGE:\n" + message, as_json=True)
    if out is None:
        return {"note": "No GEMINI_API_KEY set - demo fallback", "issue_type": "status_chase",
                "urgency": "medium", "missing_info": ["booking reference"],
                "reply": f"Thanks, we've logged your request as {ref}. Please share the booking reference."}
    return json.loads(out)

def draft_reply(row):
    facts = {k: row[k] for k in ["id", "agent", "type", "why", "amount", "age_days"] if k in row and str(row[k]) != "nan"}
    out = _gen(REPLY_PROMPT.format(facts=json.dumps(facts, default=str)))
    return out or f"[fallback] Hi {facts.get('agent')}, we're checking refund {facts['id']} with Finance and will update you within 1 working day."
