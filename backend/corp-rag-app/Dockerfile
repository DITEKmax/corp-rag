# Build with the repository root as the Docker context:
# docker build -f backend/corp-rag-app/Dockerfile .
FROM maven:3.9.9-eclipse-temurin-21 AS build

WORKDIR /workspace

COPY contracts contracts
COPY scripts scripts
COPY backend/pom.xml backend/pom.xml
COPY backend/corp-rag-contracts/pom.xml backend/corp-rag-contracts/pom.xml
COPY backend/corp-rag-app/pom.xml backend/corp-rag-app/pom.xml
COPY backend/corp-rag-app/src backend/corp-rag-app/src

RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-yaml && \
    rm -rf /var/lib/apt/lists/*

RUN mvn -q -f backend/pom.xml -pl corp-rag-app -am -DskipTests package

FROM eclipse-temurin:21-jre

WORKDIR /app
COPY --from=build /workspace/backend/corp-rag-app/target/corp-rag-app-0.1.0-SNAPSHOT.jar /app/app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
