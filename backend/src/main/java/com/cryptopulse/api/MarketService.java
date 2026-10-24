package com.cryptopulse.api;
import org.bson.Document;
import org.bson.types.Decimal128;
import org.springframework.stereotype.Service;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.Date;
import java.util.List;
import java.util.function.Function;
import static com.cryptopulse.api.ApiModels.*;
@Service
class MarketService {
    private final MarketRepository repository;
    MarketService(MarketRepository repository) { this.repository = repository; }
    List<Indicator> indicators(MarketFilter f) {
        return read("indicators", "window_start", f, d -> new Indicator(d.getString("symbol"),
            d.getString("run_id"), d.getString("mode"), time(d, "window_start"), time(d, "window_end"),
            ((Number) d.get("trade_count")).longValue(), decimal(d, "base_volume"), decimal(d, "quote_volume"),
            decimal(d, "min_price"), decimal(d, "max_price"), decimal(d, "avg_price"), decimal(d, "open_price"),
            decimal(d, "close_price"), decimal(d, "change_pct"), time(d, "prev_window_start"), time(d, "updated_at")));
    }
    List<Alert> alerts(MarketFilter f) {
        return read("alerts", "event_time", f, d -> new Alert(d.getString("symbol"), d.getString("run_id"),
            d.getString("mode"), d.getString("type"), d.getString("severity"), time(d, "event_time"),
            time(d, "window_start"), decimal(d, "observed_value"), decimal(d, "threshold"), decimal(d, "baseline"),
            d.getString("unit"), d.getString("reason"), d.getString("ref_event_id"), time(d, "created_at")));
    }
    List<Sentiment> sentiment(MarketFilter f) {
        return read("sentiment", "event_time", f, d -> new Sentiment(d.getString("event_id"),
            d.getString("source_event_id"), d.getString("source_topic"), d.getString("source"),
            d.getList("symbols", String.class), d.getList("trade_symbols", String.class), d.getString("label"),
            decimal(d, "score"), d.getString("model"), time(d, "event_time"), time(d, "processed_at"), time(d, "stored_at")));
    }
    List<Run> runs(int page, int limit) {
        return repository.runs(page, limit).stream().map(d -> new Run(d.getString("_id"),
            d.getList("symbols", String.class).stream().sorted().toList(), time(d, "start"), time(d, "end"),
            ((Number) d.get("indicator_count")).longValue(), ((Number) d.get("alert_count")).longValue())).toList();
    }
    private <T> List<T> read(String collection, String timeField, MarketFilter f, Function<Document,T> mapper) {
        List<Document> docs = repository.find(collection, timeField, f);
        try { return docs.stream().map(mapper).toList(); }
        catch (RuntimeException e) { throw new IllegalStateException("Stored document does not match the market contract", e); }
    }
    private static Instant time(Document d, String field) {
        Object value = d.get(field);
        if (value == null) return null;
        if (value instanceof Date date) return date.toInstant();
        if (value instanceof Instant instant) return instant;
        return Instant.parse(value.toString());
    }
    private static String decimal(Document d, String field) {
        Object value = d.get(field);
        if (value == null) return null;
        BigDecimal decimal = value instanceof Decimal128 bson ? bson.bigDecimalValue() : new BigDecimal(value.toString());
        return decimal.toPlainString();
    }
}

