# reading-results: Measured when it was measured, and missing is not zero

## Priority: MEDIUM

## What goes wrong

A follower count is quoted as if it were live, or an account that has never been
measured is rendered as "0 followers" — which reads as failure rather than as
absence.

## Two honesty constraints

- **Numbers are as of the last sweep, not live.** Every account and post carries
  the time it was measured. Quote that time rather than implying the number is
  current.
- **An unmeasured account has no metrics at all** — not zeroes. Say it has not
  been measured yet.

## Per destination, not aggregate

`posts_performance` reports each destination separately, because the same post
does not do the same numbers everywhere. Summing them into one figure throws away
the finding the user actually wants: which destination worked.

`accounts_performance` gives followers, posts, total likes and following per
account, each with how far it moved over the period, ordered by followers.

## Context

- Not every platform reports every metric. A metric a platform does not return
  is absent, not zero — the same rule as an unmeasured account.
