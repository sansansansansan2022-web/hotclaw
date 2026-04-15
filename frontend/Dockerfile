FROM mcr.microsoft.com/devcontainers/javascript-node:dev-20-bookworm

ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json /app/frontend/

RUN npm ci

COPY frontend /app/frontend

ARG HOTCLAW_API_ORIGIN=http://backend:8140
ENV HOTCLAW_API_ORIGIN=${HOTCLAW_API_ORIGIN}

RUN npm run build

EXPOSE 3460

CMD ["npm", "run", "start", "--", "-H", "0.0.0.0", "-p", "3460"]
