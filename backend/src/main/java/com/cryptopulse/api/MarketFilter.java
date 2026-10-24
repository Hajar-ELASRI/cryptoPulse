package com.cryptopulse.api;
import java.time.Instant;
import java.util.Locale;
import java.util.Set;
record MarketFilter(String symbol, Instant from, Instant to, int page, int limit,
    String type, String severity, String label, String runId, boolean ascending) {
    static MarketFilter parse(String symbol, String from, String to, int page, int limit,
        String type, String severity, String label, String runId, boolean ascending) {
        if (page < 0 || page > 10000) throw new IllegalArgumentException("page must be between 0 and 10000");
        if (limit < 1 || limit > 500) throw new IllegalArgumentException("limit must be between 1 and 500");
        if (symbol != null) {
            symbol = symbol.toUpperCase(Locale.ROOT);
            if (!Set.of("BTCUSDT", "ETHUSDT").contains(symbol)) throw new IllegalArgumentException("Unknown symbol: " + symbol);
        }
        Instant start = timestamp(from), end = timestamp(to);
        if (start != null && end != null && !start.isBefore(end)) throw new IllegalArgumentException("from must be before to");
        if (type != null && !Set.of("VOLUME_SPIKE", "PRICE_MOVE", "LARGE_TRADE").contains(type))
            throw new IllegalArgumentException("type must be VOLUME_SPIKE, PRICE_MOVE or LARGE_TRADE");
        if (severity != null && !Set.of("warning", "critical").contains(severity))
            throw new IllegalArgumentException("severity must be warning or critical");
        if (label != null && !Set.of("positive", "neutral", "negative").contains(label))
            throw new IllegalArgumentException("label must be positive, neutral or negative");
        if (runId == null) runId = "live";
        if (!runId.matches("[A-Za-z0-9_-]{1,80}")) throw new IllegalArgumentException("run_id must contain 1 to 80 letters, digits, underscores or hyphens");
        return new MarketFilter(symbol, start, end, page, limit, type, severity, label, runId, ascending);
    }
    private static Instant timestamp(String value) {
        if (value == null) return null;
        try { return Instant.parse(value); }
        catch (java.time.format.DateTimeParseException e) {
            throw new IllegalArgumentException("from and to must be ISO-8601 timestamps with a UTC offset");
        }
    }
}

