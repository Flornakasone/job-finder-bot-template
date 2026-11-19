# Historial de desarrollo

Pull Requests del repo privado de desarrollo (no es público porque contiene mi configuración personal).

Los números salteados son issues: en GitHub comparten numeración con los PRs.

| PR | Fecha | Cambio |
|---|---|---|
| #1 | 2026-10-22 | feat: Job model with uid for dedup + CI with pytest |
| #2 | 2026-10-22 | feat: add Remotive source with HTML cleanup and error handling |
| #3 | 2026-10-22 | feat: add Jobicy source (TDD) and shared HTTP helper |
| #4 | 2026-10-27 | feat: add hard filters (role, excluded, location, English) |
| #5 | 2026-10-29 | feat: add dedup store (seen hashes + sent history) |
| #6 | 2026-10-29 | feat: daily pipeline with Telegram summary and cron |
| #7 | 2026-10-30 | feat: add Himalayas source (TDD) filtered to Argentina |
| #8 | 2026-10-30 | ci: move daily cron to an off-peak minute |
| #9 | 2026-10-30 | feat: add Get on Board source (TDD) with location by remote_modality |
| #10 | 2026-11-02 | feat: idempotent daily send with 3 nightly attempts |
| #11 | 2026-11-02 | feat: language gate with 5 English levels and written-only exception |
| #12 | 2026-11-02 | feat: match % with local embeddings, skills and role priority |
| #13 | 2026-11-02 | fix: duplicated title in message and less saturated match % |
| #39 | 2026-11-02 | feat: gap penalty for missing requirements |
| #43 | 2026-11-03 | feat: integrity gate against prompt injection |
| #46 | 2026-11-03 | feat: less noise in daily summary (title region filter + min score) |
| #48 | 2026-11-03 | feat(llm): Groq client and job evaluator (part A of #16) |
| #49 | 2026-11-03 | feat(llm): AI evaluation in daily summary (part B of #16) |
| #50 | 2026-11-03 | ci: add force input to manual workflow run |
| #51 | 2026-11-05 | feat: add Remote OK source and AI/data QA roles |
| #53 | 2026-11-05 | feat: add company ATS readers |
| #54 | 2026-11-05 | feat: filter titles requiring other languages and tidy AI gaps line |
| #55 | 2026-11-05 | feat: weekly report of most requested missing skills |
| #56 | 2026-11-05 | feat: add verified company portals and real ATS fixtures |
| #57 | 2026-11-06 | chore: exclude paid training/placement funnels disguised as job offers |
| #58 | 2026-11-06 | feat: user config folder (me/) + templates + CLI tests |
| #59 | 2026-11-06 | docs: setup guide + clearer AI evaluation labels |
| #60 | 2026-11-06 | chore: prepare public template (README, license, export script) |
| #61 | 2026-11-06 | test: run personal keyword checks only when me/ exists |
| #62 | 2026-11-06 | test: trim WWR fixture to 5 jobs (no need to redistribute the full feed) |
| #63 | 2026-11-18 | fix(llm): grounding for AI requirements checklist |
| #64 | 2026-11-18 | chore: template v1.1 (data guard + grounding in README) |
