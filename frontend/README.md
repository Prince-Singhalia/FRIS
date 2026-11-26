# FRIS frontend

The React/TypeScript client consumes the FRIS versioned API. Local Vite development proxies `/api` to `http://localhost:8000`; set `FRONTEND_API_PROXY_TARGET` to use another backend address.

```sh
npm ci
npm run dev
```

Quality checks:

```sh
npm run lint
npm run typecheck
npm test
npm run build
```

The production Docker image serves the static build with unprivileged Nginx and proxies `/api/` requests to the Compose `api` service.
