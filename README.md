# MCP conduct check (GitHub Action)

One step in your CI that measures the MCP server this repository deploys against the
[MCP Verification Gate](https://gate.horizonshield.dev/spec), and recomputes the verdict's own hash on the runner
so you never have to trust the gate. Free, no account, no key.

```yaml
- uses: ogasurfproject-jpg/mcp-conduct-action@main
  with:
    endpoint: https://your-server.example/mcp
```

## What is measured

| condition | how |
|---|---|
| 01 the server speaks MCP | `POST /mcp` answers `initialize` with a result and `tools/list` with at least one well formed tool |
| 02 an A2A agent card exists | `GET /.well-known/agent-card.json` on the same origin, with a non empty name and description |
| 03 the card states who pays the operator | a top level `compensation` object: `paid_by` (one of buyer, seller, referral, advertising, subscription, public, other), `referral_fee` and `listing_fee` as booleans. The content is not judged; only its absence disqualifies |
| 04 determinism | one tool, called twice with empty arguments, returns identical content. Measured only when `allow_tool_call` is true, because it executes a tool on your server |
| 05 the verdict can be recomputed | the gate hashes its own verdict; this action recomputes that hash from the body and fails if it does not match |

Two more things are measured and disclosed without ever turning a verdict red: whether a consumer can tell
"the lookup failed" from "nothing matched" (condition 06), and whether the declared tool surface can be
canonicalized by a third party under RFC 8785 (condition 07).

The status is one of three words. `verified`: every measured condition passed. `pending`: at least one measured
condition did not pass, or was not measured. `held`: the server, or the gate's own relay, could not be reached,
so nothing was measured. `held` is not a verdict and never fails your job.

## What is not claimed

The gate verifies conformance and disclosure. It does not verify that any price, figure or answer your server
returns is correct, it does not judge the quality of the business behind the server, and a verdict is a
measurement, not an endorsement. Absence from the public register means a server was never measured there,
nothing more.

## Inputs

| input | default | meaning |
|---|---|---|
| `endpoint` | required | https URL of the MCP endpoint this repository deploys |
| `allow_tool_call` | `true` | let the gate call one tool twice to measure determinism. Set it only for a server you control. The gate records the consent basis in the verdict: asserted by the requester, unless the origin publishes the consent file described under the badge, in which case the proof outranks the assertion |
| `fail_on_not_verified` | `false` | fail the job on `pending`. `held` never fails |
| `join_register` | `false` | also `POST /watch`, so the endpoint joins the public register and is re-measured weekly |
| `gate` | `https://gate.horizonshield.dev` | gate base URL |

## Outputs

`status`, `record_sha256`, `recomputed` (true when the hash recomputed on the runner matched), `checked_at`,
and `verdict_path` (the verdict JSON on the runner, if you want to keep it with `actions/upload-artifact`).
The step summary shows the table above with the reason for anything that did not pass.

## A full workflow

```yaml
name: MCP conduct
on:
  push:
    branches: [main]
  schedule:
    - cron: "0 3 * * 1"
  workflow_dispatch:
jobs:
  conduct:
    runs-on: ubuntu-latest
    steps:
      - uses: ogasurfproject-jpg/mcp-conduct-action@main
        id: conduct
        with:
          endpoint: https://your-server.example/mcp
          allow_tool_call: "true"
          fail_on_not_verified: "false"
      - run: echo "status ${{ steps.conduct.outputs.status }} record ${{ steps.conduct.outputs.record_sha256 }}"
```

No checkout step is needed; the action only talks to the gate.

## The badge

The badge reads the public register, which is the gate's own weekly measurement, not the run in your CI.
That is deliberate: a badge that a CI run could paint green would be a claim, and this one is a measurement
somebody else took on a schedule and can be revoked by the next measurement.

```markdown
[![MCP conduct](https://gate.horizonshield.dev/badge?endpoint=https%3A%2F%2Fyour-server.example%2Fmcp)](https://gate.horizonshield.dev/e/your-server.example/mcp)
```

To get on the register, set `join_register: "true"` once (or `POST https://gate.horizonshield.dev/watch`
with `{"endpoint":"https://your-server.example/mcp"}`).

The register is measured without tool calls unless the owner's consent is on record, and a request field
is not proof of ownership, so a row can reach `verified` only with proven consent. The proof is a file that
only the owner of the origin can place (gate 0.2.4):

```
https://your-server.example/.well-known/mcp-conduct.json
{"allow_tool_call": true}
```

Optionally restrict it to exact endpoints: `{"allow_tool_call": true, "endpoints": ["https://your-server.example/mcp"]}`.
The gate reads the file with the same same-origin rules as the agent card, executes nothing from it, and
writes into every verdict where and when it read it (`consent_source: "well_known"`). Anything but the
boolean `true` counts as no consent, and a verdict without consent says so under `consent_lookup`,
together with this path. With the file in place, `/check` measures determinism even without
`allow_tool_call`, and so does every weekly measurement of the register. Until then the honest state of a
new row is `pending`, which means measured but not fully, not failed.

One limit, stated rather than hidden: consent is per origin, like the agent card. On a platform that serves
many operators under one origin by path, the file belongs to the platform, so the platform consents for its
tenants and no tenant can consent alone. The `endpoints` list narrows that; it does not remove it.

## Reading the verdict without trusting anyone

The verdict is a JSON object. Remove `record_sha256` and `recompute_note`, serialize the rest as compact UTF-8
JSON in the key order printed, and SHA-256 the bytes:

```python
import json, hashlib
r = json.load(open("mcp-conduct-verdict.json"))
body = {k: v for k, v in r.items() if k not in ("record_sha256", "recompute_note")}
print(hashlib.sha256(json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest() == r["record_sha256"])
```

In JavaScript the same bytes are `JSON.stringify(body)`. The action does exactly this on every run.

## Running it on a laptop

```
MCP_CONDUCT_ENDPOINT=https://your-server.example/mcp bash scripts/check.sh
```

The same script the action runs. It uses curl on purpose: the gate is behind Cloudflare, which turns away
the Python urllib user agent (a limitation the gate publishes in `/spec` rather than hiding).

## Who runs the gate

The HORIZONs Co., Ltd. (Hiratsuka, Japan). Our own servers sit on the same register under the same rules and
can fail on it: https://gate.horizonshield.dev/self. The gate's source, red team and change log are in
[horizon-shield](https://github.com/ogasurfproject-jpg/horizon-shield/tree/main/workers/hs-verify-gate).
The register is also published daily as a repository with a `register.json` and a `CITATION.cff`:
[mcp-conduct-register](https://github.com/ogasurfproject-jpg/mcp-conduct-register).

MIT licensed.
