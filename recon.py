"""Deterministic core: clean -> reconcile -> exceptions. No AI here on purpose:
money matching must be exact and auditable."""
import re
import pandas as pd

def norm_id(s):
    m = re.search(r"(\d{4})", str(s))
    return f"RF-{m.group(1)}" if m else None

def parse_date(v):
    if pd.isna(v): return pd.NaT
    if hasattr(v, "year"): return pd.Timestamp(v)
    for fmt in ("%d-%m-%Y", "%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"):
        try: return pd.to_datetime(str(v).strip(), format=fmt)
        except ValueError: pass
    return pd.NaT

def load(path):
    x = pd.read_excel(path, sheet_name=None)
    return x["Support_Tracker"], x["Finance_Tracker"], x.get("Escalations")

def clean(S, F, log):
    S, F = S.copy(), F.copy()
    S["id"] = S["Ticket ID"].map(norm_id); F["id"] = F["Ref No"].map(norm_id)
    log.append(f"IDs normalised: {(S['Ticket ID'].astype(str)!=S['id']).sum()} Support, "
               f"{(F['Ref No'].astype(str)!=F['id']).sum()} Finance (e.g. 'RF 1750', '(revised)')")
    for c in ["Request Date", "Last Updated"]: S[c] = S[c].map(parse_date)
    for c in ["Received On", "Processed On"]: F[c] = F[c].map(parse_date)
    log.append("Mixed date formats parsed to real dates")
    S["Status"] = S["Status"].astype(str).str.strip()
    S["Agent"] = S["Agent"].astype(str).str.strip().str.title()
    F["Agent Name"] = F["Agent Name"].astype(str).str.strip().str.title()
    log.append("Status/agent text trimmed; agent names case-normalised")
    n1, n2 = len(S), len(F)
    S = S.sort_values("Last Updated").drop_duplicates("id", keep="last")
    F = F.sort_values("Processed On").drop_duplicates("id", keep="last")
    log.append(f"Duplicate rows removed (keep latest): {n1-len(S)} Support, {n2-len(F)} Finance")
    return S, F

def reconcile(S, F):
    m = S.merge(F, on="id", how="outer", indicator=True)
    m["match_state"] = m["_merge"].map({"both": "both", "left_only": "support_only", "right_only": "finance_only"})
    return m.drop(columns="_merge")

def exceptions(m, asof, grace_days=5, stuck_days=5, esc=None):
    asof = pd.Timestamp(asof); rows = []
    def add(r, typ, owner, why, age):
        amt = r.get("Refund Amount (INR)")
        if pd.isna(amt): amt = r.get("Amount Paid (INR)")
        rows.append(dict(id=r["id"], type=typ, owner=owner, why=why, age_days=age,
            amount=0 if pd.isna(amt) else amt,
            agent=r["Agent"] if pd.notna(r.get("Agent")) else r.get("Agent Name"),
            support_status=r.get("Status"), finance_status=r.get("Payout Status"),
            handled_by=r.get("Handled By")))
    for _, r in m.iterrows():
        ss, fs = r.get("Status"), r.get("Payout Status")
        age = (asof - r["Request Date"]).days if pd.notna(r.get("Request Date")) else None
        if r.match_state == "support_only" and ss == "Closed" and (age or 0) > grace_days:
            add(r, "GHOST_CLOSED", "Support", "Closed in Support but Finance has no record", age)
        elif r.match_state == "finance_only":
            add(r, "FINANCE_ONLY", "Support", "Finance has it, Support never logged it", None)
        elif r.match_state == "both":
            if ss == "Closed" and fs in ("Pending Payout", "Declined"):
                add(r, "STATUS_CONFLICT", "Support", f"Support Closed but Finance says {fs}", age)
            elif ss == "Working" and fs == "Declined":
                add(r, "STATUS_CONFLICT", "Support", "Support Working but Finance Declined (agent not told)", age)
            if fs == "Refund Done":
                paid = (r["Amount Paid (INR)"] or 0); ded = 0 if pd.isna(r["Deduction (INR)"]) else r["Deduction (INR)"]
                if abs(r["Refund Amount (INR)"] - paid - ded) > 0:
                    add(r, "AMOUNT_MISMATCH", "Finance", f"Promised {r['Refund Amount (INR)']:.0f}, paid {paid:.0f}, deduction {ded:.0f}", age)
                elif ded > 0:
                    add(r, "UNEXPLAINED_DEDUCTION", "Finance", f"Deduction of {ded:.0f} paid with no reason recorded", age)
            if fs == "Pending Payout" and pd.notna(r["Received On"]):
                a = (asof - r["Received On"]).days
                if a > stuck_days:
                    add(r, "STUCK_PAYOUT", "Finance", f"Pending {a} days: {r['Remarks']}", a)
    ex = pd.DataFrame(rows).drop_duplicates(["id", "type"])
    if esc is not None and len(ex):
        e = esc.copy(); e["id"] = e["Related Ticket / Ref"].map(norm_id)
        ex["escalated"] = ex["id"].isin(set(e["id"].dropna()))
    ex["priority"] = (ex["age_days"].fillna(0) + 1) * ex["amount"].fillna(0) / 1000
    return ex.sort_values("priority", ascending=False).reset_index(drop=True)


def build_ledger(m, ex, asof):
    """One row per refund (the proposed single source of truth).
    Support-owned fields, Finance-owned fields, and a derived unified status + next owner."""
    asof = pd.Timestamp(asof)
    L = pd.DataFrame({
        "Refund ID": m["id"],
        "Agent": m["Agent"].where(m["Agent"].notna(), m["Agent Name"]),
        "Route": m["Route"].where(m["Route"].notna(), m["Sector"]),
        "Channel": m["Channel"],
        # --- Support-owned ---
        "Request Date": m["Request Date"],
        "Amount Requested (INR)": m["Refund Amount (INR)"],
        "Support Status": m["Status"],
        "Handled By": m["Handled By"],
        # --- Finance-owned ---
        "Received By Finance On": m["Received On"],
        "Payout Status": m["Payout Status"],
        "Amount Paid (INR)": m["Amount Paid (INR)"],
        "Deduction (INR)": m["Deduction (INR)"],
        "Deduction Reason (required)": "",
        "Processed On": m["Processed On"],
        "Finance Remarks": m["Remarks"],
    })
    def status(r):
        ps, ss, st = r["Payout Status"], r["Support Status"], None
        if ps == "Refund Done": return "Paid", "None"
        if ps == "Declined": return "Declined - agent must be told reason", "Support"
        if ps == "Pending Payout": return "With Finance - pending payout", "Finance"
        if pd.isna(ps) and pd.notna(ss):
            if ss == "Closed": return "NOT RECEIVED BY FINANCE (Support closed early)", "Support"
            if ss == "Not Eligible": return "Not eligible (Support)", "None"
            return "With Support", "Support"
        return "In Finance only - Support never logged", "Support"
    s = L.apply(status, axis=1, result_type="expand")
    L["Unified Status"], L["Next Action Owner"] = s[0], s[1]
    first = ex.sort_values("priority", ascending=False).drop_duplicates("id").set_index("id")
    L["Open Exception"] = L["Refund ID"].map(first["type"]).fillna("")
    L["Days Waiting"] = L["Refund ID"].map(first["age_days"])
    return L.sort_values(["Open Exception", "Refund ID"], ascending=[False, True]).reset_index(drop=True)
def build_ledger(m, ex, asof):
    """One row per refund (the proposed single source of truth)."""
    asof = pd.Timestamp(asof)
    L = pd.DataFrame({
        "Refund ID": m["id"],
        "Agent": m["Agent"].where(m["Agent"].notna(), m["Agent Name"]),
        "Route": m["Route"].where(m["Route"].notna(), m["Sector"]),
        "Channel": m["Channel"],
        # --- Support-owned ---
        "Request Date": m["Request Date"],
        "Amount Requested (INR)": m["Refund Amount (INR)"],
        "Support Status": m["Status"],
        "Handled By": m["Handled By"],
        # --- Finance-owned ---
        "Received By Finance On": m["Received On"],
        "Payout Status": m["Payout Status"],
        "Amount Paid (INR)": m["Amount Paid (INR)"],
        "Deduction (INR)": m["Deduction (INR)"],
        "Deduction Reason (required)": "",
        "Processed On": m["Processed On"],
        "Finance Remarks": m["Remarks"],
    })
    def status(r):
        ps, ss = r["Payout Status"], r["Support Status"]
        if ps == "Refund Done": return "Paid", "None"
        if ps == "Declined": return "Declined - agent must be told reason", "Support"
        if ps == "Pending Payout": return "With Finance - pending payout", "Finance"
        if pd.isna(ps) and pd.notna(ss):
            if ss == "Closed": return "NOT RECEIVED BY FINANCE (Support closed early)", "Support"
            if ss == "Not Eligible": return "Not eligible (Support)", "None"
            return "With Support", "Support"
        return "In Finance only - Support never logged", "Support"
    s = L.apply(status, axis=1, result_type="expand")
    L["Unified Status"], L["Next Action Owner"] = s[0], s[1]
    first = ex.sort_values("priority", ascending=False).drop_duplicates("id").set_index("id")
    L["Open Exception"] = L["Refund ID"].map(first["type"]).fillna("")
    L["Days Waiting"] = L["Refund ID"].map(first["age_days"])
    return L.sort_values(["Open Exception", "Refund ID"], ascending=[False, True]).reset_index(drop=True)