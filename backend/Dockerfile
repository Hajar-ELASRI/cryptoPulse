FROM maven:3.9.11-eclipse-temurin-17 AS build
WORKDIR /app
COPY pom.xml .
COPY src ./src
RUN mvn -B package -DskipTests

FROM eclipse-temurin:17-jre-jammy
WORKDIR /app
RUN groupadd --system cryptopulse && useradd --system --gid cryptopulse cryptopulse
COPY --from=build /app/target/cryptopulse-api-0.1.0.jar app.jar
USER cryptopulse
EXPOSE 8081
ENTRYPOINT ["java", "-jar", "app.jar"]
