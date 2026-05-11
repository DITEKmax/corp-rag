# frontend/

SPA на vanilla HTML5 + CSS3 + JavaScript ES2022+.

**Никакого** Tailwind, никаких фреймворков. BEM-методология для CSS.

Эта папка пустая — здесь появится содержимое в **EPIC 16** (Frontend Foundation).

## Целевая структура

```
frontend/
├── index.html
├── public/
│   └── favicon.ico
├── src/
│   ├── styles/                      # CSS по BEM
│   │   ├── base/
│   │   ├── layouts/
│   │   ├── components/
│   │   └── pages/
│   ├── scripts/
│   │   ├── main.js
│   │   ├── api/                     # client, auth, documents, chat
│   │   ├── auth/                    # session, guard
│   │   ├── router/
│   │   ├── pages/
│   │   ├── components/
│   │   └── utils/
│   └── assets/
└── nginx.conf
```

Полная структура — см. `docs/ARCHITECTURE.md` раздел 6.

## Запуск (появится когда будет содержимое)

```bash
# cd frontend
# python -m http.server 8081
# или через nginx в docker-compose
```
