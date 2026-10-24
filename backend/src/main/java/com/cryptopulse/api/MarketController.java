package com.cryptopulse.api;
import io.swagger.v3.oas.annotations.Operation;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import static com.cryptopulse.api.ApiModels.*;
@RestController
@RequestMapping("/api")
class MarketController {
    private final MarketService service;
    MarketController(MarketService service) { this.service = service; }

    @GetMapping("/live")
    @Operation(summary = "Latest live Spark windows, newest first; decimals are strings")
    List<Indicator> live(@RequestParam(defaultValue = "BTCUSDT") String symbol,
        @RequestParam(defaultValue = "60") int limit, @RequestParam(defaultValue = "0") int page) {
        return service.indicators(filter(symbol, null, null, page, limit, null, false));
    }

    @GetMapping("/analytics")
    @Operation(summary = "Spark indicators in chronological order; no computed summary")
    Analytics analytics(@RequestParam String symbol, @RequestParam String from, @RequestParam String to,
        @RequestParam(name = "run_id", defaultValue = "live") String runId,
        @RequestParam(defaultValue = "500") int limit, @RequestParam(defaultValue = "0") int page) {
        var f = filter(symbol, from, to, page, limit, runId, true);
        return new Analytics(f.symbol(), f.from(), f.to(), f.runId(), service.indicators(f));
    }

    @GetMapping("/alerts")
    List<Alert> alerts(@RequestParam(required = false) String symbol,
        @RequestParam(required = false) String from, @RequestParam(required = false) String to,
        @RequestParam(defaultValue = "0") int page, @RequestParam(defaultValue = "100") int limit,
        @RequestParam(required = false) String type, @RequestParam(required = false) String severity,
        @RequestParam(name = "run_id", defaultValue = "live") String runId) {
        return service.alerts(MarketFilter.parse(symbol, from, to, page, limit, type, severity, null, runId, false));
    }

    @GetMapping("/sentiment")
    @Operation(summary = "Filter by trade_symbols; source_event_id is the source fallback")
    List<Sentiment> sentiment(@RequestParam(required = false) String symbol,
        @RequestParam(required = false) String from, @RequestParam(required = false) String to,
        @RequestParam(defaultValue = "0") int page, @RequestParam(defaultValue = "50") int limit,
        @RequestParam(required = false) String label) {
        return service.sentiment(MarketFilter.parse(symbol, from, to, page, limit, null, null, label, null, false));
    }

    @GetMapping("/replay/runs")
    @Operation(summary = "Runs with replay results, including alert-only runs; counts do not imply completion")
    List<Run> runs(@RequestParam(defaultValue = "0") int page, @RequestParam(defaultValue = "100") int limit) {
        filter(null, null, null, page, limit, null, true);
        return service.runs(page, limit);
    }

    @GetMapping("/replay/{runId}")
    @Operation(summary = "Replay indicators and alerts, oldest first; does not launch Spark")
    Replay replay(@PathVariable String runId, @RequestParam(required = false) String symbol,
        @RequestParam(required = false) String from, @RequestParam(required = false) String to,
        @RequestParam(defaultValue = "0") int page, @RequestParam(defaultValue = "500") int limit) {
        var f = filter(symbol, from, to, page, limit, runId, true);
        if ("live".equals(f.runId())) throw new IllegalArgumentException("A replay run_id is required");
        return new Replay(f.runId(), service.indicators(f), service.alerts(f));
    }
    private MarketFilter filter(String symbol, String from, String to, int page, int limit, String runId, boolean ascending) {
        return MarketFilter.parse(symbol, from, to, page, limit, null, null, null, runId, ascending);
    }
}

