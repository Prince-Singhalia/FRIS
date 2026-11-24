# FRIS — Project Rules for AI Coding Agents

## Non-Negotiable Invariants

1. **Inspect first.** Examine existing workspace, source files, Git state, runtimes before changes. Preserve user work.
2. **Do not fake integrations.** No hard-coded publication lists, fabricated API responses, simulated success statuses in production paths. Mocks allowed only in tests and must be labelled.
3. **Do not invent provider API behaviour.** Verify endpoint paths, parameters, auth, pagination against official docs before implementing. Record docs URL and date checked.
4. **Do not claim a test passed unless actually run.** Show command, result, skipped tests. If provider unreachable, mark `not_configured`/`unavailable`.
5. **No paid dependencies in MVP.** Use free/open-source components.
6. **Respect source terms.** Official APIs and feeds only. No Google Scholar scraping. No bypassing publisher access controls.
7. **Protect secrets and personal data.** No secrets in source control. Never send institutional email to providers by default. Hash passwords.
8. **Keep raw evidence and normalized data separate.** Preserve provider-specific values, retrieval timestamps, source URLs.
9. **Make processing idempotent.** Re-running discovery must not create duplicates.
10. **Do not overengineer.** Modular monolith, PostgreSQL, Docker Compose, bounded concurrency. No Kafka/K8s/Redis unless measured need.
11. **Keep two pipelines distinct:** Research Data Pipeline (discovers/stores publications) vs Software CI/CD Pipeline (tests/builds/deploys the app AND Prefect worker/flow).
12. **Demo researcher is external.** Never represent pilot researcher as faculty of the customer university. Label as "DEMO — external researcher."
13. **Tenant isolation.** All tenant-owned entities include tenant_id. Enforce in API queries and test cross-tenant denial.
14. **Confidence scores are not probabilities.** Call them scores, not percentages or probabilities. Display evidence, not just numbers.
15. **DOI-first deduplication.** Same normalized DOI = same work. No-DOI dedup requires strong multi-signal corroboration or manual review.
