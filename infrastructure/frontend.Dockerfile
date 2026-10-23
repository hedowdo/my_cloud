FROM node:24.19.0-bookworm-slim AS build
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@11.25.0 --activate
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml .npmrc ./
COPY frontend/package.json frontend/package.json
RUN --mount=type=cache,target=/pnpm/store pnpm install --frozen-lockfile \
    --store-dir=/pnpm/store --fetch-timeout=180000 --fetch-retries=5 --network-concurrency=4
COPY frontend ./frontend
RUN pnpm build

FROM caddy:2.11.7-alpine
RUN mkdir -p /srv/frontend /config /data \
    && chown -R 10001:10001 /srv /config /data \
    && setcap -r /usr/bin/caddy
COPY --from=build /app/frontend/dist /srv/frontend
COPY infrastructure/Caddyfile.dev /etc/caddy/Caddyfile
USER 10001:10001
EXPOSE 8080
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
