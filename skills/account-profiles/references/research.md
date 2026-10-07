# Maintaining platform knowledge

`research.json` is a dated fact register, not a list of eternal defaults. Read only
the matching platform module; open the relevant fact rows when updating evidence.
The shipped register is read-only in an installed plugin, which an update replaces: keep
refreshed facts, in the same shape, in the project beside the brief, and tell the user
which shipped facts look out of date.

Each fact has a stable `id`, `platform`, `topic`, `claim`, `scope`, `status`, `sources`
(URL/title/publisher/sourceUpdatedAt), `checkedAt`, `checkMethod`, `recheckAfter`,
`limitations`, and optional `supersedes`/`conflictsWith`. Use null for an unknown source
date. The date researched is never a substitute for a source's own update date.

Statuses: `verified-source`, `tool-observation`, `design-recommendation`,
`needs-confirmation`, `conflicting`, `superseded`. Account-specific enabled state
belongs in the group's feature rows, with `enabled`, `disabled`, `eligible-unverified`,
`unknown`, or `not-applicable` and its own evidence/time.

Prefer official help, current native UI and ViewPrinter's live platform schema.
Record consumer-app and API limits separately. Official pages can disagree across
date, country, placement and account tier: retain both scopes and mark unresolved
conflicts. Do not replace a missing fact with a remembered follower threshold.
An inaccessible official page is a failed research attempt, not fresh verification.
Third-party discovery can locate an official source; label any unresolved fallback.

Refresh when a feature is being relied on and the fact is stale, contradicted, or
account/region dependent. Thirty days for eligibility/link rules and ninety days for
asset specifications are review reminders chosen by this workflow, not platform
validity guarantees. A visible mismatch triggers immediate research. Recheck dates
do not create an automatic task or promise monitoring.

For unlocks capture: feature and placement; account subtype/tier; country and age
conditions when documented; follower/activity/verification prerequisites; exact
native setting path; who must act; side effects; what evidence confirms success.
Do not infer native unlocks from API scopes, active OAuth or a business connection.

Append source changes to the history in the project's copy of the register, with
old/new claim and reason. Keep
last-known evidence when a source becomes unavailable; change verification state
instead of resetting its date. Record product/tool defects with reproducible output
and a next step, apart from platform eligibility and project strategy.
