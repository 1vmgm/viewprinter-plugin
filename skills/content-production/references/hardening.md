# Improve through use without accumulating brittle rules

After a meaningful round, capture what happened and whether the lesson belongs to the item, format, project, tool adapter or universal workflow. Don't rewrite the public skill after every preference change.

## Small improvement loop

1. Record the raw incident/correction, affected versions, evidence and context in private project history.
2. Separate the production change (what we did) from the finding (what we concluded). Mark confidence and plausible alternative explanations.
3. Keep project-specific taste in project.md or the format revision. Add a due condition to carry-forward for unresolved questions, not a fabricated answer.
4. For a repeatable cross-project failure, propose a narrowly scoped instruction or helper fix. A single deterministic bug can warrant a fix; creative correlations usually need more evidence.
5. Add a realistic regression case that would have exposed the failure. Run the relevant helper tests and at least one different-format/project case before broadening the rule.
6. Review the diff for conflicts, duplication, unnecessary gates, credentials and private assets. Validate package contents/links and record checks actually run. Public push, release and deployment require their own authorization.
7. Link the finding to the changed rule/test and record what would invalidate it. Supersede old findings explicitly; don't erase history.

Do not claim automatic self-improvement or that memory changed the installed skill. A project finding is evidence for a candidate patch, not permission for unrelated publishing or a production deployment. Preserve existing user authorization and avoid repeated confirmation for routine authorized local changes.

## Evaluation cases worth keeping

- Unchosen concepts: user asks for alternatives and review before spending. Agent produces representative plans/previews and waits at that actual boundary.
- Approved format: user asks for a batch. Agent varies allowed dimensions and keeps typography/pacing/structure rather than replacing the format.
- Bulk feedback: approvals mixed with global and item-specific edits. Agent maps IDs/versions correctly and doesn't silently carry approval onto changed output.
- Restart after an update: agent finds external memory from cwd, reads carry-forward and resumes the current round without deleting earlier findings.
- New product/static asset: workflow transfers without a mandatory phone frame, avatar, soundtrack, brand motif or storyline carried over from another project.
- Audio reuse: existing track isn't uploaded twice; an unlicensed track is never downloaded or uploaded; a review-only audition isn't silently exposed to automatic campaigns; a fake seamless-loop claim fails.

Use Claude skill-creator's with-skill/baseline comparisons where available. The shipped `evals/evals.json` holds generic prompts and expectations with no project data; keep run outputs, transcripts and project-specific cases outside the skill. Objective checks cover state/IDs/paths/approval and export facts. Human review covers creative quality. Model-based planning checks are not rendered-media validation, download attribution or live client installation tests. Don't spend generation credits or publish content just to evaluate wording.
