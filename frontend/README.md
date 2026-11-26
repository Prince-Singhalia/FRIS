# FRIS frontend

The React/TypeScript client consumes the FRIS versioned API. Local Vite development proxies `/api` to `http://localhost:8000`; set `FRONTEND_API_PROXY_TARGET` to use another backend address.

Use Node.js 24.15.0 or newer. This minimum satisfies the engine requirements of the locked frontend dependencies.

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
