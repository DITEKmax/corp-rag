# backend/

Java Spring Boot multi-module проект.

Эта папка пустая — здесь появится содержимое в **EPIC 2** (Contracts) и **EPIC 3** (Java Auth).

## Целевая структура (после EPIC 2)

```
backend/
├── pom.xml                          # parent POM
├── corp-rag-contracts/              # Java DTO/constants generation module; consumes ../contracts
│   ├── pom.xml
│   └── src/main/java/               # сгенерированные DTO и constants
└── corp-rag-app/                    # основное приложение
    ├── pom.xml
    └── src/main/java/com/corprag/
```

Исходные OpenAPI/AsyncAPI YAML и `constants.yaml` живут в корневом `contracts/`, а не внутри `backend/`.

Полная структура пакетов — см. `docs/ARCHITECTURE.md` раздел 4.4.

## Команды (появятся когда будет POM)

```bash
# cd backend
# ./mvnw clean package
# ./mvnw spring-boot:run -pl corp-rag-app
```
