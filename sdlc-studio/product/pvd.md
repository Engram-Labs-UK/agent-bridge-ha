# Product Vision Document: Engram Labs

> **Document Type:** PVD (master)
> **Version:** 0.6.0
> **Last Updated:** 2026-07-04
> **Status:** Draft
> **Owner:** Product Manager (Darren Benson)
> **Review Cadence:** per product milestone (and on any cross-repo contract change)

<!--
The PVD is the PRODUCT layer above the per-repo PRD. It COORDINATES and TRACES; it never
re-specifies what a child repo's PRD already owns. One writable master (this file) lives in
engram-labs-product; every child repo gets it read-only (see `pvd sync`). Kept lean — the
opt-in sections (topology tree, G1–G5 gates, release coordination) are omitted until the
product is large/multi-team enough to need them.
-->

## 1. Vision & Scope

**Vision:** A single engram platform — **engram-studio** — for authoring, storing, and serving AI-persona "engrams", consumed *optionally* by the agent fleet (**agent-bridge**) and the operator console (**agent-crew**). Engram is a capability the fleet can switch on, never a dependency it is built around.

**Scope:** Coordinates the go-forward repos — **bridge** (multi-agent runtime/infra), **crew** (operator dashboard/orchestrator), **studio** (the unified engram platform), and **framework** (the AGPL open-source core: canonical engram schema, the Behavioural Compiler, the per-host bootloaders, and the `engram-canonical-v1` content-hash canonicaliser). framework owns the engram *definition*; studio authors/stores/serves engrams against it; bridge+crew consume them. Scope settles the **runtime read contract** studio owns and bridge+crew consume; the **cutover** off the old `engram-library` FastAPI onto studio; the binding **no-engram optionality** invariant; and the staged **retirement** of the legacy repos (engram-library, engram-foundry, engram-foundry-cli) — each gated on parity, never assumed.

**Business context:** Engram capability accreted across five repos with no product layer and a fragmenting runtime API (bridge/crew read the old library; studio is the new platform with a different, multi-tenant shape). The identity-anchored operating model (canonical: [`operating-model.md`](operating-model.md); crew RFC-0011 is crew's consumer binding) makes engrams the *fixed identity substrate* for some agents and a *fungible costume* for chatbots — so a coherent, verifiable, optional engram contract is now load-bearing for trust (content-addressed identity, signed AI-BOM) and for the next crew features (costumes, RAG). This PVD is the coordination spine that prevents the three repos drifting apart at the engram seam.

## 2. Strategic Goals

| Goal ID | Strategic Goal | Metric | Target | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| PG1 | **One unified engram platform** — consolidate 5 repos → studio | legacy repos retired (library + foundry + foundry-cli) | 3 retired | studio | In Progress |
| PG2 | **Optional-engram guarantee** — bridge + crew run fully with zero engram link | CI "no-engram" contract test green in both repos | 2/2 green | bridge + crew | Proposed |
| PG3 | **Content-addressed engram identity** — every engram-backed agent has a verifiable `sourceHash` | engram agents with a resolved (non-`none`) `engramRef`; AI-BOM `complete` not `partial` | 100% of engram agents | studio + bridge | Proposed |
| PG4 | **Curated knowledge live** — chatbot costumes + per-crew RAG | crew CR-0220 + CR-0224 unblocked + shipped | both Done | crew + bridge + studio | Blocked (on PG2/PG3 + studio read-contract) |

## 3. Master Feature Inventory

Each product feature maps to its **owning repo** and that repo's **PRD/CR feature** — the traceability `product reconcile` checks. Specs live in the child repos; this only traces.

| PF ID | Feature | Owning repo | Child PRD/CR feature | Priority | Status | Target |
| --- | --- | --- | --- | --- | --- | --- |
| PF0001 | Engram authoring + storage platform (orgs, pipeline, chat, costs) | studio | studio:prd §features | P1 | Done (core) | shipped |
| PF0002 | **Fleet runtime read contract** (engram-by-slug · `sourceHash` · zones · fleet read-auth) — the cutover keystone | studio | studio:CR-(new, 0.4) | P1 | Proposed | Phase 1 |
| PF0003 | Bridge engram consumption (genome `engramRef`, content-addressing, signed AI-BOM completeness) | bridge | bridge:RFC-0014 · CR-0461 · CR-0454 | P2 | Proposed | Phase 2–3 |
| PF0004 | Crew engram consumption (EngramClient, librarian/zones, identity-binding view) | crew | crew:CR-0157 (Done) · CR-0126 (Done) | P2 | In Progress | Phase 2 |
| PF0005 | Chatbot persona/engram **costumes** (per-conversation overlay, audited) | bridge + crew | bridge:CR-0435 · crew:CR-0220 | P2 | Blocked | Phase 3 |
| PF0006 | Per-crew **RAG knowledgebase** + archivist/librarian roles | bridge + crew | bridge:CR-0436 · crew:CR-0224 | P3 | Blocked | Phase 3 |
| PF0007 | **No-engram optionality invariant** (binding, CI-tested) | bridge + crew | bridge:CR-(new, 0.5) · crew:CR-(new, 0.5) | P1 | Proposed | Phase 0/2 |
| PF0008 | Foundry pipeline absorption (parity-audit → migrate → retire) | studio | studio:CR-(new, 0.6) | P2 | Proposed | Phase 4 |
| PF0009 | engram-library content migration + standalone-API retirement | studio | studio:US0047 (ETL, Done) + retire | P2 | In Progress | Phase 4 |
| PF0010 | **Canonical engram schema + content-addressed canonicaliser** (`engram-canonical-v1`) — the engram definition + the one hash algorithm `sourceHash` derives from | framework | framework:CR-0005 (schema 3.1.0) · `framework/bootloaders/shared/content-hash.js` | P1 | In Progress | underpins PG3 / PR3 |
| PF0011 | **Canonical operating model** (I·C·K four-class taxonomy, identity-as-unit-of-trust, no-on-demand-mint, fixed/accreting doctrine, deployment/trust tiers) - the product-owned doctrine consumers reference, never restate | product | [`operating-model.md`](operating-model.md) (canonical) · framework RFC-0001/firmware (identity physics) · bridge (enforcement) · crew RFC-0011 (crew's binding) | P1 | Canonical (v4.0.0) | live |

## 4. Cross-Repo Dependencies

| Dep ID | From repo | To repo | Dependency | Type | Required by | Status |
| --- | --- | --- | --- | --- | --- | --- |
| PD1 | bridge | studio | the runtime read contract (PF0002) | api | Phase 2 cutover | Proposed |
| PD2 | crew | studio | the runtime read contract (PF0002) | api | Phase 2 cutover (EngramClient repoint) | Proposed |
| PD3 | studio | library | engram content migration / ongoing sync until retirement | data | Phase 4 | In Progress (ETL once) |
| PD4 | bridge | crew | librarian access config (capability tag + zones) — crew authors, bridge consumes | data | already live | Done (CR-0157) |
| PD5 | crew | bridge | agent taxonomy on discovery (`identitySubstrate`, `engramRef`) | api | already live | Done (CR-0256) |
| PD6 | studio + bridge | framework | the shared `engram-canonical-v1` canonicaliser + schema (PF0010) — the "ONE shared canonicaliser" PR3 mandates | spec/lib | PG3 / `sourceHash` parity | Proposed |

### Two lenses on the same constellation — do not conflate them

The five repos order differently depending on the question asked. Both orderings are correct; they answer different questions, and mistaking one for the other is a common source of design error.

- **Derivation lens (where a concept is defined; what must be designed first):**
  `framework → studio → crew → bridge → bridge-ha`. Everything springs from the **framework** (the identity substrate: the engram schema, firmware, fixity, the content hash). **studio** authors and stores engrams built on it; **crew** is the operator's control plane over the fleet; **bridge** is the runtime that gives an identity capability; **bridge-ha** embodies it in the physical world. This is the operator's mental model and the order the operating model itself derives in (identity physics → operating model → consumers).
- **Runtime-dependency lens (who calls whom while running; the DAG in the PD table above):** **studio** owns the read contract that **bridge** and **crew** both consume (PD1/PD2); **framework** owns the canonicaliser that **studio** and **bridge** both consume (PD6); **crew ↔ bridge** is a live two-way seam (PD4/PD5). This is a DAG, not a line, and it does **not** follow the derivation order — at runtime nothing "depends on" crew in the way the derivation lens places bridge after it, and bridge-ha is a leaf, not the terminus of a chain.

Rule of thumb: use the **derivation lens** to decide *where a definition belongs* (it is why the operating model sits above the framework and the framework owns the class definition — CR-0022); use the **runtime lens** to decide *what must be deployed and versioned together* (it is why §5 API contracts, not the derivation order, gate the cutover).

## 5. API Contract Commitments

The inter-repo seam where multi-repo products break. Versioned; breaking changes + migration deadline declared.

| Contract | Owner repo | Consumers | Current version | Planned | Breaking change | Migration deadline | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Engram fleet read API** — `GET /engrams/{slug}?version=` → content + `sourceHash`; `GET /engrams` list/search; zones (real/fictional/audit) + tier (free/licensed); fleet read-auth | studio | bridge, crew | — (today: old engram-library `/api/v1`) | studio `v1` | YES — cutover off the engram-library FastAPI; consumers repoint | at Phase-2 cutover (library API retires after) | Proposed |
| Bridge agent taxonomy on `/v1/discovery` (`identitySubstrate`, `engramRef{slug,version}`) | bridge | crew | live | unchanged | no | — | Stable |
| Crew librarian access config (`capabilities.tags:['librarian']` + `capabilities.library.zones`) | crew | bridge | live | unchanged | no | — | Stable (CR-0157) |

**Contract principle (consult-frozen 2026-06-22):** the read API exposes a content-addressed `sourceHash` (`engram-canonical-v1`, publish-time + immutable) and is read via a **per-fleet read-only service token** (NOT a public endpoint — studio is multi-tenant), scoped **`tier{free|owned}` × `crew-namespace`** server-side. Additive + versioned; the old library API stays live (frozen read-only) until parity is proven, then retires.

### Tenancy & crew topology (current — operator decision 2026-06-22)

- **One studio org today: `deskpoint`.** `org:crew = 1:N` — all crews live under the single `deskpoint` org. Org-split + cross-org transfer machinery **does not exist and is NOT built now** (deferred to a future point).
- **Crews (current, growing from the library):** `System` (agentcrew), `deskpoint` (the operator's personal crew — shares the org name), `Engram Labs`, `Julian`, `Netscape Nation`, + more as library engrams are onboarded. Membership notes: Spanners belongs in **System/agentcrew** (not deskpoint); the **Engram Labs** crew mixes Engram-Labs + Agent-Crew personnel. The agents' identity engrams live in the engram-studio library.
- **Live isolation axis = crew-namespace; the org axis is present-but-dormant** (single value). So within the single operator-owned `deskpoint` org, **cross-crew engram reads are governance/relevance, NOT a confidentiality wall** (RFC-0014 C5) — crew-scope decides *which crew's engrams surface* (and the per-crew RAG substrate, PF0006), not a hard barrier. The **hard confidentiality wall is the ORG boundary**, which is dormant until the org-split. Spanners' A1 crew-scope stays in the schema (server-enforced, future-proof); its hard-wall reading is deferred with the org-split.
- **Build consequence:** Phase-1 can assume the single `deskpoint` org (keep the org column, single-valued); the service token scopes on `crew-namespace` + `tier`. No cross-org logic required now.

## 6. Risk & Conflict Register

| ID | Risk / conflict | Severity | Impact | Mitigation | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- |
| PR1 | **Studio multi-tenant auth vs bridge "no-key / free-tier" assumption** — the fleet read-auth reconciliation | High | blocks the cutover (PF0002) | **RESOLVED-w-conditions (consult 2026-06-22):** per-fleet read-only service token (NOT public); scope = `tier{free\|owned}` × `crew-namespace`, server-side; revocable/TTL≤90d/audited (Knox C1–C6) | studio + bridge | Resolved-w-conditions |
| PR2 | **Foundry parity gaps unknown** until audited — premature retirement loses features | Med | feature regression on retirement | PF0008 parity-audit gates retirement (no retire until gap-list empty) | studio | Open (EP0016) |
| PR3 | **Canonicalisation mismatch** → `sourceHash` drift between studio (Postgres) and bridge expectation | Med | false drift signals; AI-BOM churn | **RESOLVED-w-conditions (consult 2026-06-22):** `engram-canonical-v1`, publish-time + immutable, ONE shared canonicaliser (bridge ↔ studio) whose reference implementation is owned by **framework** (PF0010, `content-hash.js`), `hashAlgo` recorded (Eve E1 / Spanners A4) | studio + bridge + framework | Resolved-w-conditions |
| PR4 | **Dual-running period** (library + studio) content drift | Low–Med | stale reads, divergent engrams | **MITIGATED (consult 2026-06-22):** freeze library read-only (NOT a live sync) + zero-mismatch `sourceHash` reconciliation gate (Queeg R1); frozen library retained as cold last-known-good (R3c) | studio | Mitigated |
| PR5 | **No-engram invariant regresses silently** as engram features land | Med | breaks the operator's ground rule unnoticed | PF0007 binding CI contract test in both bridge + crew | bridge + crew | Mitigated-by-PF0007 |

## 7. Decisions Log

| Date | Decision | Owner | Rationale | Related |
| --- | --- | --- | --- | --- |
| 2026-06-22 | **Studio serves the runtime API** (cutover off engram-library) | operator | one platform, one API; the old standalone library API is a fork-in-the-road | PF0002, PD1/PD2, §5 |
| 2026-06-22 | **No-engram = binding + CI-tested** in bridge AND crew | operator | the fleet must never depend on engram; a doc principle isn't regression-proof | PF0007, PR5 |
| 2026-06-22 | **New `engram-labs-product` repo anchors the PVD**; manifest = bridge, crew, studio | operator | neutral product layer above the per-repo PRDs (PVD doctrine) | this file, manifest.yaml |
| 2026-06-22 | **engram-framework added to the product manifest** (4th go-forward repo) — it owns the canonical schema + the `engram-canonical-v1` canonicaliser the content-addressed-identity story rests on; previously the canonicaliser had no named owner | operator | the AGPL open-source core is load-bearing for PG3/PR3, not incidental; name the owner so `sourceHash` parity traces | PF0010, PD6, PR3, manifest.yaml |
| 2026-06-22 | **engram-foundry + engram-foundry-cli retire into studio — only after a parity audit + migrate + verify** | operator | they carry pipeline features (9-stage flow, adversarial protocols, auditor team, headshot/ComfyUI, CLI/MCP authoring) that must be checked across, not assumed | PF0008, PR2 |
| 2026-06-22 | "engram-forge" = engram-foundry (operator misremember); no separate forge repo | operator | filesystem confirms engram-foundry / -cli | PF0008 |
| 2026-06-22 | **EP0015 read-contract design FROZEN** — Phase-1 consult unanimous SIGN-OFF-WITH-CONDITIONS (Knox/Queeg/Spanners/Eve + Three-Amigos). Resolves all 4 open points: service-token auth (scope = tier × crew), org:crew = 1:N, `engram-canonical-v1` publish-time hashing, freeze+reconciliation+replay-diff parity gate. | Claude Code (Opus 4.8) | studio:`reviews/consult-ep0015-readcontract-2026-06-22.md`; PR1/PR3 resolved-w-conditions, PR4 mitigated |
| 2026-06-22 | **Single studio org (`deskpoint`); org-split deferred** — resolves the EP0015 residual "does engram-labs get its own org?". `org:crew = 1:N` with ALL crews under the one `deskpoint` org; cross-org transfer not built now. The live isolation axis is crew-namespace; the org wall is dormant (so within-org crew-scope is governance/relevance, not confidentiality — RFC-0014 C5). Phase-1 assumes the single org. | operator | §5 Tenancy & crew topology; EP0015 A1 |
| 2026-07-04 | **Canonical operating model authored in the product layer** (`operating-model.md`, v4.0.0) - the I·C·K taxonomy, identity-as-unit-of-trust, and the fixed/accreting doctrine now have one product-owned home. Resolves the dangling-pointer drift (agent-crew cited a non-existent `docs/operating-model.md` 13 times); the framework owns the identity *physics*, this doc owns the operating *model*, and crew RFC-0011 becomes crew's consumer binding. The "living/frozen" descriptor is retired from the classifier (kept for the relationship) per the fleet-Entity consult (Julian, Cora, 2026-07-04). | operator | PF0011, `operating-model.md`, crew RFC-0011 §10.8 |
| 2026-07-04 | **agent-bridge-ha added as the 5th go-forward repo** (the embodiment / home-control layer) and the standing seam-check wired: the master PVD is projected read-only into all five repos via `pvd sync` (`pvd drift` fails loud, exit 1, on any child divergence; projections are written read-only). The two chain lenses (derivation vs runtime-dependency) are documented in §4 so they are not conflated. `product_reconcile`'s feature-map half is filed inert against this CR/RFC-cited PVD (sdlc-studio CR-0141); it stays advisory until fixed - `pvd drift` is the live check. | operator | manifest.yaml, §4 chain-lenses, sdlc-studio:CR-0141 |

## Revision History

| Date | Version | Change | Author |
| --- | --- | --- | --- |
| 2026-06-22 | 0.1.0 | Initial PVD — Engram Labs product layer over bridge/crew/studio; locks the studio-cutover, the no-engram invariant, the new-product-repo anchor, and the foundry parity-gated retirement. Drafted from the deep cross-repo dive; opt-in sections (topology/gates/release-coordination) omitted until needed. | Claude Code (Opus 4.8) |
| 2026-06-22 | 0.2.0 | Phase-1 consult outcome folded in — EP0015 read-contract design frozen (Knox/Queeg/Spanners/Eve unanimous SIGN-OFF-WITH-CONDITIONS). PR1/PR3 → resolved-w-conditions, PR4 → mitigated; decisions log + EP0015 (engram-studio) updated with the binding C/R/A/E condition set. | Claude Code (Opus 4.8) |
| 2026-06-22 | 0.3.0 | Operator org decision — single `deskpoint` studio org, org-split deferred; added §5 Tenancy & crew topology (org:crew 1:N, crew-namespace = the live isolation axis, org wall dormant ⇒ within-org crew-scope is governance per RFC-0014 C5). Phase-1 assumes the single org. | Claude Code (Opus 4.8) |
| 2026-06-22 | 0.4.0 | Added **engram-framework** as the 4th go-forward repo (manifest + §1 scope) — the AGPL open-source core owning the canonical schema + `engram-canonical-v1` canonicaliser. New PF0010 (schema + canonicaliser), PD6 (studio+bridge → framework), PR3 owner named, decisions-log entry. | Claude Code (Opus 4.8) |
| 2026-07-04 | 0.5.0 | Canonical **operating model** authored in the product layer (`operating-model.md` v4.0.0) - one home for the I·C·K taxonomy, identity-as-trust, and the fixed/accreting doctrine; kills the dangling-pointer drift (13 dead refs in crew), demotes crew RFC-0011 to a consumer binding, retires "living/frozen" from the classifier per the fleet-Entity consult. New PF0011; §1 business-context reference repointed; decisions-log entry. | Claude (Opus 4.8) |
| 2026-07-04 | 0.6.0 | **Standing coordination (Phase 3).** Added **agent-bridge-ha** as the 5th go-forward repo (embodiment/home-control). Wired the read-only PVD projection across all five repos (`pvd sync`); `pvd drift` is now the live seam-check (exit 1 on divergence, mutation-verified; projections are read-only). Documented the two chain lenses (derivation vs runtime-dependency) in §4. Filed sdlc-studio CR-0141 - `product_reconcile`'s feature-map parser is inert against this CR/RFC-cited PVD, so it stays advisory until fixed. | Claude (Opus 4.8) |
