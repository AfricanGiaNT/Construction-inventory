## Inventory Stocktake Feature Plan (/inventory)

### Overview
- Goal: Enable Admins to perform stock taking via a batch-friendly /inventory command that updates Items.On Hand and records an audit trail.
- Scope: Batch size ≤ 50 entries. Creates missing items. Admin-only. Supports validate mode. Hybrid approach with history.
- Status: ✅ COMPLETED - All 4 phases implemented and tested

### Phases

#### Phase 1: Baseline Command & Parsing (Admin-gated) ✅ COMPLETED
- Deliverables:
  - ✅ Add /inventory command with header + lines format:
    - Header: `/inventory date:DD/MM/YY logged by: NAME1,NAME2`
    - Entries: `Item Name, Quantity` (one per line)
  - ✅ Admin-only enforcement
  - ✅ Limit to ≤ 50 entries
  - ✅ Parse and deduplicate by keeping the last occurrence per item
  - ✅ Upsert Items and set On Hand to counted quantity
- Tests: ✅ COMPLETED
  - ✅ Unit tests (parsing) - 30 test methods covering all scenarios
    - Header parsing
      - Accepts `date:14/02/25 logged by: Trevor,Kayesera,Grant`
      - Trims extra spaces around keys/values; rejects missing `date:` or `logged by:`
      - Invalid date formats rejected (e.g., `14-02-25`, `32/13/25`, non-numeric)
    - Entry line parsing
      - Accepts `Cement 32.5, 50` and `12mm rebar, 120.0`
      - Trims whitespace around name and quantity
      - Rejects missing comma, empty item name, non-numeric qty, NaN/±inf
      - Supports zero quantity (explicit stocktake to zero)
    - Dedupe logic
      - Multiple lines for same item retain last occurrence; earlier duplicates excluded
      - Case sensitivity policy clarified: treat names as case-insensitive for dedupe (confirm behavior); tests for `Item`, `item`
    - Batch size enforcement
      - Exactly 50 lines passes; 51st line rejected with clear error
      - Blank lines and comment lines (Phase 4) are not counted
    - Admin gating
      - Non-admin user receives permission error; admin proceeds
  - ✅ Unit tests (application logic) - 16 test methods covering service logic
    - Existing item: sets `On Hand` to counted value
    - New item creation: creates with defaults `Base Unit=piece`, `Category=General`, `Is Active=true`
    - Partial failure handling: invalid lines reported, valid lines applied
    - Summary generation: counts updated/created/failed with per-line reasons
  - ✅ Integration tests - 15 test methods covering command integration
    - Happy path: mix of existing and new items; verify final `On Hand` and creation
    - Duplicate within batch: last wins; verify only one update applied per item
    - Large batch at limit: 50-line performance and correctness
- Notes:
  - New items default: Base Unit = piece, Category = General (temporary)

#### Phase 2: Validate Mode, Idempotency (ephemeral), Provenance fields ✅ COMPLETED
- Deliverables:
  - ✅ `/inventory validate ...` parses and reports errors without writes
  - ✅ Idempotency key (hash of header + normalized entries) cached in memory with TTL to block exact re-apply
  - ✅ Add optional Items fields: Last Stocktake Date (date), Last Stocktake By (text)
  - ✅ Internally normalize date to ISO (YYYY-MM-DD)
- Tests:
  - ✅ Unit tests (28 test methods covering all scenarios)
    - Validate mode
      - ✅ `/inventory validate ...` performs full parse and returns detailed report without writing
      - ✅ Ensure no writes: assert Airtable write methods not called (mocked)
    - Idempotency (in-memory TTL)
      - ✅ Same exact text re-applied within TTL is blocked with explicit message
      - ✅ Changing any character in header or entries yields different key and is allowed
      - ✅ After TTL expiry, batch can be applied again
    - Date normalization
      - ✅ Input DD/MM/YY normalized to ISO `YYYY-MM-DD`
      - ✅ Invalid date still rejected in validate and apply
    - Provenance fields
      - ✅ `Last Stocktake Date` and `Last Stocktake By` updated on Items touched
  - ✅ Integration tests
    - ✅ Validate → Apply flow returns same summary counts
    - ✅ Applying then re-applying same text within TTL is blocked
    - ✅ Zero quantity correctly updates item to 0 and provenance fields set
- Notes:
  - ✅ Keep require_validate_first optional (off by default)

#### Phase 3: Persistence & Audit Trail (Hybrid) ✅ COMPLETED
- Deliverables:
  - ✅ Create `Bot Meta` table (Idempotency Keys): Key (text), Created At (datetime)
  - ✅ Persist and check idempotency keys across restarts
  - ✅ Create `Stocktakes` table for audit entries per item with fields:
    - ✅ Batch Id, Date, Logged By (text), Item Name, Counted Qty, Previous On Hand, New On Hand, Applied At, Applied By
  - ✅ Write one audit record per updated/created item in stocktake
- Tests:
  - ✅ Unit tests (34 test methods covering all scenarios)
    - ✅ Persistent idempotency via `Bot Meta`
      - ✅ Writing a key after apply; subsequent applies with same key blocked across process restarts (simulate)
    - ✅ Audit row construction in `Stocktakes`
      - ✅ Fields populated: Batch Id, Date, Logged By, Item Name, Counted Qty, Previous On Hand, New On Hand, Applied At, Applied By
      - ✅ Previous/New On Hand correctness verified
  - ✅ Integration tests
    - ✅ E2E: apply batch, confirm one audit row per unique item
    - ✅ Restart simulation: persistent key prevents duplicate apply
    - ✅ Mixed success/failure batch: only successful entries create audit rows; failures listed in summary

#### Phase 4: UX & Robustness Enhancements ✅ COMPLETED
- Deliverables:
  - ✅ Header parsing tolerant to `logged_by:` or `logged by:`
  - ✅ Support comment lines starting with `#` and ignore blanks
  - ✅ Summary includes warnings: default unit used on creation, items skipped, lines ignored
  - ✅ Return a corrected template when parse fails
- Tests: ✅ COMPLETED
  - ✅ Unit tests (11 test methods covering all scenarios)
    - ✅ Header variants accepted: `logged_by:`, `logged by:`; varying whitespace and capitalization
    - ✅ Comment lines `# note` and blank lines are ignored (not counted toward 50)
    - ✅ Mixed line endings (\n, \r\n) parsed consistently
    - ✅ Error template: when parse fails, response contains corrected skeleton with first offending line highlighted
    - ✅ Statistics tracking: blank lines, comment lines, skipped lines properly counted
    - ✅ Edge cases: commands with only comments/blanks properly rejected
  - ✅ Integration tests
    - ✅ Summary includes warnings: default unit used on creation, lines ignored, items skipped
    - ✅ Large batch with comments and blanks parsed accurately; limit applied to effective entries

### Data Model Changes ✅ COMPLETED
- Items table (✅ implemented):
  - ✅ Last Stocktake Date (date) - added to Items table
  - ✅ Last Stocktake By (text) - added to Items table
  - ✅ Stocktakes (multipleRecordLinks) - links to Stocktakes table
- New tables (✅ created):
  - ✅ Bot Meta (Idempotency Keys): Key, Created At
  - ✅ Stocktakes: Batch Id, Date, Logged By, Item Name, Counted Qty, Previous On Hand, New On Hand, Applied At, Applied By, Item (link), Notes, Discrepancy

### Security & Permissions
- Only Admins can run /inventory and /inventory validate

### Rollout Strategy ✅ COMPLETED
- ✅ Phase 1: Baseline Command & Parsing (Admin-gated) - SHIPPED
- ✅ Phase 2: Validate Mode, Idempotency, Provenance fields - SHIPPED  
- ✅ Phase 3: Persistence & Audit Trail (Hybrid) - SHIPPED
- ✅ Phase 4: UX & Robustness Enhancements - SHIPPED
- ✅ All required Airtable tables and fields created
- ✅ Code fully implemented and tested

### Open Decisions
- Default Base Unit mapping by category: keep open; fallback to piece for now
- require_validate_first: optional (off by default)

### Acceptance Criteria ✅ COMPLETED
- ✅ Admin can successfully validate and apply a ≤ 50-line batch that updates Items.On Hand and returns a clear summary.
- ✅ Re-applying the same batch is blocked when idempotency is enabled (Phase 2+).
- ✅ Audit records are created per entry (Phase 3).
- ✅ All 4 phases fully implemented and tested
- ✅ Airtable integration complete with Bot Meta and Stocktakes tables
- ✅ Provenance tracking (Last Stocktake Date, Last Stocktake By) implemented


### Cross-Cutting Tests
- Schema/contract tests (Airtable)
  - Items table: assert presence/types of required fields (`Name`, `On Hand`, optional provenance fields)
  - Bot Meta: `Key` (text), `Created At` (datetime) exist
  - Stocktakes: required fields exist with expected types
- Performance tests (with mocks around Airtable I/O)
  - 50-entry batch end-to-end parsing + summary under 300ms (logic only)
  - With I/O mocked to fixed latency, total time budget under configured threshold; report variance
- Concurrency/race conditions
  - Two concurrent apply requests with same payload: only one succeeds; the other is blocked by idempotency
  - Partial apply rollback policy: if using per-line apply, ensure summary reflects exact outcomes; if future transactional batching is added, add rollback tests
- Security/permissions
  - Admin-only enforced for both validate and apply
  - Input sanitization: ensure special characters in item names do not break formulas or cause injection
  - Logging: no sensitive tokens leaked; summaries omit PII beyond user names provided
- Property-based/robustness tests (optional but recommended)
  - Generate random whitespace, casing, and benign punctuation around entries; parser remains stable
  - Fuzz quantities with valid floats and boundary values (0, very large within policy)

### Test Fixtures & Utilities
- Sample payloads
  - Minimal valid batch (1 item)
  - Mixed existing/new items (≤10)
  - 50-line batch at limit with comments and blanks interspersed
  - Duplicate item scenarios (case variations)
- Mocks
  - Airtable client read/write methods
  - Time provider for deterministic date/idempotency TTL tests
- CI gates
  - Phase-by-phase: cannot merge unless tests for that phase are green
  - Contract tests run daily to detect schema drift
