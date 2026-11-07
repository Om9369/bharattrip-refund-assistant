# BharatTrip Refund Operations Assistant & Reconciler

> **AI Operations Associate Take-Home Submission**  
> An automated reconciliation engine and AI-powered operational assistant designed to eliminate handoff gaps, resolve refund exceptions, and prevent agent escalations without adding headcount.

---

## 📌 Overview

BharatTrip's refund operations suffered an escalation surge from **23 in March to 75 in June 2026**, despite refund volume remaining flat (~145–150/month).

This system diagnoses and fixes the root cause: **a disconnected handoff between Support and Finance**.
- **Support** marks tickets "Closed" without confirmation of payout (**69 ghost closures**, ₹10.8L at risk).
- **Finance** disburses funds or places payouts on hold without communicating back (**58 stuck payouts**, 50 unexplained deductions).
- **Messy Channels**: Informal requests over WhatsApp and email arrive unlogged and lack reference tracking.

---

## 🚀 Key Features & Architecture

The solution strictly adheres to core operational design: **deterministic code for exact financial matching, and Generative AI strictly for unstructured human communication.**

```
                               ┌─────────────────────────────────┐
                               │  BharatTrip Refund Data (.xlsx) │
                               └────────────────┬────────────────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. Deterministic Core (recon.py)                                                                │
│    • Normalizes erratic ticket IDs ("RF 1750", "(revised)" ➔ "RF-1750")                        │
│    • Standardizes 5 hand-typed date formats to timestamps                                       │
│    • Deduplicates rows (preserves latest operational state)                                     │
│    • Audits & flags 6 exception types (Ghost Closures, Stuck Payouts, Status Conflicts)         │
│    • Constructs the Unified Master Ledger (Single Source of Truth)                              │
└───────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 2. Interactive Operational Dashboard (app.py - Streamlit)                                       │
│    • Tab 1: Morning Report — Priority daily action lists for Support and Finance                │
│    • Tab 2: Reconcile & Exceptions — Deep audit metrics, risk analysis & ledger download        │
│    • Tab 3: Informal Request Intake — Automated message logging & draft replies                 │
└───────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 3. AI Language Layer (ai.py - Google Gemini)                                                    │
│    • Parses unstructured WhatsApp/Email messages (English, Hindi, Hinglish)                     │
│    • Extracts agent name, route, urgency, and missing information                               │
│    • Generates instant reference acknowledgments (RF-NEW-XXX)                                   │
│    • Drafts concise, fact-checked agent updates strictly from ledger data                       │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```text
BharatTrip_AI_Assistant/
├── app.py                                  # Streamlit web dashboard (3 tabs)
├── recon.py                                # Core cleaning, reconciliation & ledger engine
├── ai.py                                   # Gemini API integration (with canned demo fallback)
├── requirements.txt                        # Python dependencies
├── BharatTrip_Refund_Data_final (5).xlsx   # Sample dataset (Feb - Jun 2026)
└── README.md                               # Project documentation
```

---

## 🛠️ Quickstart: How to Run Locally

### 1. Prerequisites
- Python 3.9 to 3.12 installed.

### 2. Setup Environment & Install Dependencies
Clone or navigate to the repository folder:
```bash
cd BharatTrip_AI_Assistant
python -m venv venv
```

Activate the virtual environment:
- **Windows (PowerShell):**
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
- **Mac/Linux:**
  ```bash
  source venv/bin/activate
  ```

Install requirements:
```bash
pip install -r requirements.txt
```

### 3. Set Gemini API Key *(Optional)*
If you want live AI parsing and reply generation, set your API key:
- **Windows (PowerShell):**
  ```powershell
  $env:GEMINI_API_KEY="your-gemini-api-key"
  ```
- **Mac/Linux:**
  ```bash
  export GEMINI_API_KEY="your-gemini-api-key"
  ```
*(Note: If no API key is provided, the app will run seamlessly using built-in demo fallback responses).*

### 4. Launch App
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`, upload `BharatTrip_Refund_Data_final (5).xlsx` in the sidebar, and explore the 3 operational tabs.

---

## ☁️ Deploying to Streamlit Cloud

To share a live public link with reviewers:
1. Push this folder to a public **GitHub** repository (exclude `venv/`).
2. Go to [share.streamlit.io](https://share.streamlit.io/) and log in with GitHub.
3. Click **"New App"**, select your repository, set the main file path to `app.py`.
4. Under **Advanced Settings > Secrets**, add:
   ```toml
   GEMINI_API_KEY = "your-actual-api-key"
   ```
5. Click **Deploy**.

---

## 📊 Summary of Operational Findings

When auditing the provided 5-month dataset:
* **Total Support Tickets:** 733 | **Finance Payouts:** 680
* **Matched in Both:** 664
* **Support-Only ("Ghost Closures"):** 69 tickets (₹10.8L) closed by Support with no record in Finance.
* **Finance-Only:** 16 refunds processed by Finance that Support never logged.
* **Payment Accuracy:** 582 of 583 paid refunds reconcile mathematically; the failure is **information handoff**, not calculation.

---

## 🎯 Target Success Metrics (30-Day SLA)

| Metric | Baseline | 30-Day Target |
| :--- | :--- | :--- |
| **Escalations per 100 requests** | 53 / 100 (June peak) | $\le$ 20 / 100 |
| **Ghost Closures (>4 days without Finance)** | 10% (66 cases) | **0%** (via enforced Closure Rule) |
| **Stuck Finance Payouts (>5 days)** | 20 cases | $<$ 3 cases |
| **Median Payout Turnaround (Guardrail)** | 3 days | $\le$ 3 days (no operational degradation) |
