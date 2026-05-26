# frontend/

SPA на vanilla HTML5 + CSS3 + JavaScript ES2022+.

**Никакого** Tailwind, никаких фреймворков. BEM-методология для CSS.

Phase 6 содержит рабочую SPA-основу: cookie-auth bootstrap, hash-router,
chat, quote-only source modal и компактные admin screens.

## Структура

```
frontend/
├── index.html
├── js/
│   ├── api/                         # feature wrappers over core/api-client.js
│   ├── components/
│   ├── core/                        # session-state, api-client, router, routes
│   ├── generated/                   # contract-derived frontend constants
│   └── pages/
├── styles/
│   ├── base.css
│   ├── app.css
│   ├── chat.css
│   └── admin.css
└── nginx.conf
```

## Запуск

Через compose:

```bash
docker compose -f ../infra/docker-compose.yml up -d --build frontend java-backend
```

Открой http://localhost. По умолчанию frontend обращается к Java по
`http://localhost:8080/api/v1`; Python напрямую из браузера не вызывается.
Если нужен другой Java origin, задай `window.CORP_RAG_API_BASE` перед
`/js/app.js`.

Локальная статическая проверка:

```bash
node --check js/app.js
```
