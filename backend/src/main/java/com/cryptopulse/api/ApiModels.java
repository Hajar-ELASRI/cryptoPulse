package com.cryptopulse.api;
import java.time.Instant;
import java.util.List;
public final class ApiModels {
    private ApiModels() {}
    public record Indicator(String symbol, String runId, String mode, Instant windowStart, Instant windowEnd,
        long tradeCount, String baseVolume, String quoteVolume, String minPrice, String maxPrice,
        String avgPrice, String openPrice, String closePrice, String changePct, Instant prevWindowStart, Instant updatedAt) {}
    public record Alert(String symbol, String runId, String mode, String type, String severity, Instant eventTime,
        Instant windowStart, String observedValue, String threshold, String baseline, String unit, String reason,
        String refEventId, Instant createdAt) {}
    public record Sentiment(String eventId, String sourceEventId, String sourceTopic, String source,
        List<String> symbols, List<String> tradeSymbols, String label, String score, String model,
        Instant eventTime, Instant processedAt, Instant storedAt) {}
    public record Analytics(String symbol, Instant from, Instant to, String runId, List<Indicator> indicators) {}
    public record Replay(String runId, List<Indicator> indicators, List<Alert> alerts) {}
    public record Run(String runId, List<String> symbols, Instant start, Instant end, long indicatorCount, long alertCount) {}
    public record Error(String code, String message, Instant timestamp) {}
}

