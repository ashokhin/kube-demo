# syntax=docker/dockerfile:1

# Stage 1 — build the fat JAR with Maven
FROM maven:3.9-eclipse-temurin-21 AS builder

WORKDIR /app

# Copy pom.xml first — Docker caches the dependency layer unless pom.xml changes.
# This avoids re-downloading all dependencies on every source change.
COPY pom.xml .
RUN mvn dependency:go-offline -q

COPY src/ ./src/
RUN mvn package -DskipTests -q

# Stage 2 — minimal runtime image
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

# Non-root user for the principle of least privilege
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

COPY --from=builder /app/target/risk-ui-*.jar app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
