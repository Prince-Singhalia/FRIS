# Security Policy

## Reporting a vulnerability

Do not open a public issue for a security vulnerability. Contact the project owner privately with a description, reproduction steps, affected files or endpoints, and impact. Do not include live credentials or confidential faculty data in the report.

## Security expectations

- Keep `.env`, credentials, private keys, dumps, and logs out of Git.
- Rotate any credential that may have been exposed; removing a file does not remove it from Git history.
- Use strong deployment secrets and disable development/demo defaults in production.
- Keep tenant isolation, password hashing, provider terms, and source provenance tests in scope for changes.
