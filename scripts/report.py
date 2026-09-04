#!/usr/bin/env python3
"""Read the gate's verdict, recompute its hash, and report it in plain words.

No HTTP in here on purpose (the gate refuses the Python urllib user agent); check.sh does the request.

Exit codes: 0 verified or held, 10 pending, 20 the record does not hash to its own record_sha256.
"""
import hashlib
import json
import os
import sys
from urllib.parse import quote

VERDICT = os.environ["VERDICT"]
GATE = os.environ.get("GATE", "https://gate.horizonshield.dev").rstrip("/")
EP = os.environ.get("EP", "")
GH_OUT = os.environ.get("GITHUB_OUTPUT") or os.devnull
GH_SUM = os.environ.get("GITHUB_STEP_SUMMARY") or os.devnull

CONDITIONS = [
    ("mcp_endpoint", "01 MCP endpoint answers initialize and tools/list"),
    ("agent_card", "02 A2A agent card at /.well-known/agent-card.json"),
    ("compensation_disclosure", "03 the card states who compensates the operator"),
    ("determinism", "04 the same tool call returns the same content twice"),
]


def recompute(record):
    body = {k: v for k, v in record.items() if k not in ("record_sha256", "recompute_note")}
    raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main():
    with open(VERDICT, "r", encoding="utf-8") as f:
        record = json.load(f)
    if "error" in record and "status" not in record:
        print("::error::the gate answered with an error instead of a verdict: " + json.dumps(record)[:400])
        return 1

    status = str(record.get("status", "")).strip()
    sha = record.get("record_sha256") or ""
    checked_at = record.get("checked_at") or ""
    endpoint = record.get("endpoint") or EP
    got = recompute(record) if sha else ""
    recomputed = bool(sha) and got == sha

    checks = record.get("checks") or {}
    rows = []
    for key, label in CONDITIONS:
        c = checks.get(key) or {}
        if c.get("measured") is False:
            mark = "not measured"
        elif c.get("pass") is True:
            mark = "pass"
        else:
            mark = "did not pass"
        reason = str(c.get("reason") or "").replace("\n", " ").strip()
        rows.append((label, mark, reason))
    canon = record.get("canonicalization") or {}
    if canon.get("measured"):
        rows.append(("07 declared surface can be canonicalized by a third party (RFC 8785)",
                     "yes" if canon.get("canonicalizable") else "no (fingerprint withheld)",
                     "disclosure only, never turns a verdict red"))
    rows.append(("05 the verdict hashes to its own record_sha256",
                 "recomputed, matches" if recomputed else ("MISMATCH" if sha else "no record_sha256 in the verdict"),
                 "computed on this runner from the verdict body, not taken from the gate"))

    host_path = endpoint[len("https://"):] if endpoint.startswith("https://") else endpoint
    row_url = GATE + "/e/" + host_path
    badge_url = GATE + "/badge?endpoint=" + quote(endpoint, safe="")
    history_url = GATE + "/history?endpoint=" + quote(endpoint, safe="")

    print()
    print("  status:        " + status)
    print("  checked_at:    " + checked_at)
    print("  gate:          " + str(record.get("gate_version", "")) + " " + str(record.get("gate_commit", "")))
    print("  record_sha256: " + sha)
    print("  recomputed:    " + ("matches" if recomputed else "MISMATCH"))
    print("  consent basis: " + str(record.get("consent_basis", "")))
    if record.get("consent_source"):
        print("  consent source: " + str(record.get("consent_source")))
    lookup = record.get("consent_lookup") or {}
    if lookup.get("how_to_consent") and record.get("consent_source") in (None, "none", "requester"):
        print("  consent file:  " + str(lookup.get("result", "")))
        print("      " + str(lookup.get("how_to_consent", ""))[:400])
    print()
    for label, mark, reason in rows:
        print("  [" + mark + "] " + label)
        if reason and mark not in ("pass", "recomputed, matches"):
            print("      " + reason[:300])
    print()
    print("  row on the public register (weekly, not this run): " + row_url)
    print("  badge (reads the register, not this run):           " + badge_url)

    with open(GH_OUT, "a", encoding="utf-8") as o:
        o.write("status=" + status + "\n")
        o.write("record_sha256=" + sha + "\n")
        o.write("recomputed=" + ("true" if recomputed else "false") + "\n")
        o.write("checked_at=" + checked_at + "\n")
        o.write("verdict_path=" + VERDICT + "\n")

    with open(GH_SUM, "a", encoding="utf-8") as s:
        s.write("## MCP conduct: " + status + "\n\n")
        s.write("`" + endpoint + "` measured at " + checked_at + " by gate " + str(record.get("gate_version", "")) + "\n\n")
        s.write("| condition | result | note |\n|---|---|---|\n")
        for label, mark, reason in rows:
            note = "" if mark in ("pass", "recomputed, matches") else reason[:220].replace("|", "\\|")
            s.write("| " + label + " | " + mark + " | " + note + " |\n")
        s.write("\n`record_sha256` " + sha + "\n\n")
        if lookup.get("how_to_consent") and record.get("consent_source") in (None, "none", "requester"):
            s.write("Consent on record: " + str(lookup.get("result", "")) + ". " + str(lookup.get("how_to_consent", "")) + "\n\n")
        s.write("Recompute it yourself: remove `record_sha256` and `recompute_note`, serialize the rest as compact UTF-8 JSON in the printed key order "
                "(`json.dumps(r, separators=(',',':'), ensure_ascii=False)` in Python, `JSON.stringify(r)` in JavaScript), SHA-256 the bytes.\n\n")
        s.write("This gate verifies conformance and disclosure only. It does not verify that any figure the server returns is correct, "
                "and a verdict is a measurement, not an endorsement.\n\n")
        s.write("Register row (weekly measurement): " + row_url + "  \nHistory: " + history_url + "\n")

    if sha and not recomputed:
        print("::error::record_sha256 " + sha + " does not match the recompute " + got)
        return 20
    if status == "verified":
        print("::notice::MCP conduct: verified. record_sha256 " + sha)
        return 0
    if status == "held":
        print("::warning::MCP conduct: held. The server or the gate's relay could not be reached, so nothing was measured. This is not a verdict about the server.")
        return 0
    failed = [label for label, mark, _ in rows if mark in ("did not pass", "not measured")]
    print("::warning::MCP conduct: pending. Not passed or not measured: " + "; ".join(failed))
    return 10


if __name__ == "__main__":
    sys.exit(main())
