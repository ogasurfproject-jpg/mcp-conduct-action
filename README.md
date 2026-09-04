# mcp-conduct-action is now wedjat-check-action

This action was published on 2026-09-04 without noticing that the same job already had a repository,
built the day before and better at it. Rather than keep two, the work moved to the older one:

**https://github.com/ogasurfproject-jpg/wedjat-check-action**

```yaml
- uses: ogasurfproject-jpg/wedjat-check-action@v1
  with:
    endpoint: https://your-server.example/mcp
```

It does everything this one did (measure the endpoint at the MCP Verification Gate, recompute
`record_sha256` inside your own job, fail the build on a measured failure) and three things this one
did not: a `require` policy with three settings instead of one flag, `must_pass` to name the exact
conditions that have to be measured and pass, and `unmeasured_conditions` reported as its own output
so that "not measured" can never be read as "passed".

This repository is left in place, not deleted, because its URL was already sent to other operators in
public issues on 2026-09-04 and a dead link helps nobody. The code that was here is unchanged in git
history; only this README was replaced.

## The other pieces

- The gate itself, free and keyless: https://gate.horizonshield.dev/spec
- Before an agent connects, in your own code: `npm i mcp-conduct` (https://www.npmjs.com/package/mcp-conduct)
- Consent to be measured fully, from your own origin: publish `/.well-known/mcp-conduct.json` with `{"allow_tool_call": true}`
- What the register is and is not: https://shield.the-horizons-innovation.com/verify-directory/

MIT. The HORIZONs Co., Ltd.
