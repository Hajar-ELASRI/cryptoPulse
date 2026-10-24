package com.cryptopulse.api;
import com.mongodb.MongoTimeoutException;
import org.bson.Document;
import org.bson.types.Decimal128;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.Date;
import java.util.List;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
@WebMvcTest(MarketController.class)
@Import({MarketService.class, WebConfiguration.class})
class MarketApiTest {
    @Autowired MockMvc mvc;
    @MockitoBean MarketRepository repository;
    static final String PERIOD = "symbol=BTCUSDT&from=2026-10-16T09:00:00Z&to=2026-10-16T10:00:00Z";
    @ParameterizedTest
    @ValueSource(strings={"/api/live","/api/alerts","/api/sentiment","/api/replay/runs"})
    void emptyLists(String route) throws Exception {
        when(repository.find(anyString(),anyString(),any())).thenReturn(List.of());
        when(repository.runs(anyInt(),anyInt())).thenReturn(List.of());
        mvc.perform(get(route)).andExpect(status().isOk()).andExpect(content().json("[]"));
    }
    @Test void mapsAliIndicatorsWithExactDecimalsAndDefaults() throws Exception {
        when(repository.find(eq("indicators"),anyString(),any())).thenReturn(List.of(indicator()));
        mvc.perform(get("/api/live")).andExpect(status().isOk())
            .andExpect(jsonPath("$[0].avg_price").value("67000.123456789123456789"))
            .andExpect(jsonPath("$[0].close_price").value("67010.25"))
            .andExpect(jsonPath("$[0].open_price").value("66900.00"))
            .andExpect(jsonPath("$[0].run_id").value("live"))
            .andExpect(jsonPath("$[0].mode").value("live"))
            .andExpect(jsonPath("$[0].window_start").value("2026-10-16T09:00:00Z"))
            .andExpect(jsonPath("$[0]._id").doesNotExist());
        verify(repository).find(eq("indicators"),eq("window_start"),argThat(f ->
            f.symbol().equals("BTCUSDT") && f.limit()==60 && !f.ascending() && f.runId().equals("live")));
    }
    @Test void analyticsUsesReplayAndAscendingPages() throws Exception {
        when(repository.find(anyString(),anyString(),any())).thenReturn(List.of(indicator()));
        mvc.perform(get("/api/analytics?"+PERIOD+"&run_id=replay-demo&page=2&limit=10"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.indicators.length()").value(1))
            .andExpect(jsonPath("$.run_id").value("replay-demo")).andExpect(jsonPath("$.summary").doesNotExist());
        verify(repository).find(eq("indicators"),anyString(),argThat(f ->
            f.ascending() && f.page()==2 && f.limit()==10 && f.runId().equals("replay-demo")));
    }
    @ParameterizedTest @ValueSource(strings={"VOLUME_SPIKE","PRICE_MOVE","LARGE_TRADE"})
    void allAlertTypesAndSeverity(String type) throws Exception {
        when(repository.find(anyString(),anyString(),any())).thenReturn(List.of(alert()));
        mvc.perform(get("/api/alerts?type="+type+"&severity=critical&run_id=replay-demo"))
            .andExpect(status().isOk()).andExpect(jsonPath("$[0].baseline").value("50820.0"))
            .andExpect(jsonPath("$[0].unit").value("ratio")).andExpect(jsonPath("$[0].reason").value("Explained alert"));
        verify(repository).find(eq("alerts"),eq("event_time"),argThat(f ->
            type.equals(f.type()) && "critical".equals(f.severity()) && "replay-demo".equals(f.runId())));
    }
    @Test void sentimentIncludesAssetAndTradeSymbols() throws Exception {
        when(repository.find(anyString(),anyString(),any())).thenReturn(List.of(new Document("event_id","sentiment:1")
            .append("source_event_id","rss:1").append("source_topic","crypto-news").append("symbols",List.of("BTC"))
            .append("trade_symbols",List.of("BTCUSDT")).append("label","positive").append("score",0.64)));
        mvc.perform(get("/api/sentiment?symbol=BTCUSDT&label=positive")).andExpect(status().isOk())
            .andExpect(jsonPath("$[0].symbols[0]").value("BTC"))
            .andExpect(jsonPath("$[0].trade_symbols[0]").value("BTCUSDT"))
            .andExpect(jsonPath("$[0].source_topic").value("crypto-news"))
            .andExpect(jsonPath("$[0].source_event_id").value("rss:1"));
        verify(repository).find(eq("sentiment"),anyString(),argThat(f -> "positive".equals(f.label()) && f.limit()==50));
    }
    @Test void sentimentCarriesSourceTitleAndUrl() throws Exception {
        when(repository.find(anyString(),anyString(),any())).thenReturn(List.of(
            new Document("event_id","sentiment:rss:1").append("source_event_id","rss:1").append("source_topic","crypto-news")
                .append("label","negative").append("score",-0.3),
            new Document("event_id","sentiment:rss:2").append("source_event_id","rss:2").append("source_topic","crypto-news")
                .append("label","neutral").append("score",0)));
        when(repository.titles(eq("news"),argThat(ids -> ids.containsAll(List.of("rss:1","rss:2"))))).thenReturn(List.of(
            new Document("_id","rss:1").append("title","Bitcoin slides below 80,000").append("url","https://example.org/a")));
        mvc.perform(get("/api/sentiment")).andExpect(status().isOk())
            .andExpect(jsonPath("$[0].title").value("Bitcoin slides below 80,000"))
            .andExpect(jsonPath("$[0].url").value("https://example.org/a"))
            .andExpect(jsonPath("$[1].title").doesNotExist())
            .andExpect(jsonPath("$[1].source_event_id").value("rss:2"));
        verify(repository, never()).titles(eq("social_posts"), any());
    }
    @Test void replayRunsAndDetails() throws Exception {
        when(repository.runs(0,100)).thenReturn(List.of(new Document("_id","replay-demo")
            .append("symbols",List.of("ETHUSDT","BTCUSDT")).append("indicator_count",360).append("alert_count",12)
            .append("start",Date.from(Instant.parse("2026-10-16T09:00:00Z")))));
        mvc.perform(get("/api/replay/runs")).andExpect(status().isOk())
            .andExpect(jsonPath("$[0].run_id").value("replay-demo")).andExpect(jsonPath("$[0].indicator_count").value(360))
            .andExpect(jsonPath("$[0].alert_count").value(12));
        when(repository.find(anyString(),anyString(),any())).thenReturn(List.of());
        mvc.perform(get("/api/replay/replay-demo?symbol=BTCUSDT")).andExpect(status().isOk())
            .andExpect(jsonPath("$.run_id").value("replay-demo")).andExpect(jsonPath("$.indicators").isEmpty())
            .andExpect(jsonPath("$.alerts").isEmpty());
        verify(repository).find(eq("indicators"),anyString(),argThat(f -> f.ascending() && f.runId().equals("replay-demo")));
        verify(repository).find(eq("alerts"),anyString(),argThat(f -> f.ascending() && f.runId().equals("replay-demo")));
    }
    @ParameterizedTest
    @ValueSource(strings={"/api/live?limit=0","/api/live?limit=501","/api/live?page=-1","/api/live?page=10001",
        "/api/live?limit=abc","/api/live?symbol=XYZ","/api/alerts?from=yesterday",
        "/api/alerts?from=2026-10-16T00:00:00","/api/alerts?from=2026-10-17T00:00:00Z&to=2026-10-16T00:00:00Z",
        "/api/alerts?type=volume_spike","/api/alerts?severity=unknown","/api/sentiment?label=unknown",
        "/api/alerts?run_id=$ne","/api/analytics","/api/analytics?symbol=BTCUSDT",
        "/api/replay/live"})
    void invalidInputsNeverQueryMongo(String route) throws Exception {
        mvc.perform(get(route)).andExpect(status().isBadRequest()).andExpect(jsonPath("$.code").value("INVALID_ARGUMENT"));
        verifyNoInteractions(repository);
    }
    @Test void databaseErrorsAreSafe() throws Exception {
        when(repository.find(anyString(),anyString(),any())).thenThrow(new MongoTimeoutException("mongodb://secret:password@host"));
        mvc.perform(get("/api/live")).andExpect(status().isServiceUnavailable())
            .andExpect(jsonPath("$.code").value("DATA_UNAVAILABLE"))
            .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("password"))));
    }
    @Test void malformedDataIsServerError() throws Exception {
        when(repository.find(anyString(),anyString(),any())).thenReturn(List.of(indicator().append("avg_price","bad")));
        mvc.perform(get("/api/live")).andExpect(status().isInternalServerError());
    }
    @Test void cors() throws Exception {
        mvc.perform(options("/api/live").header("Origin","http://localhost:5173").header("Access-Control-Request-Method","GET"))
            .andExpect(status().isOk()).andExpect(header().string("Access-Control-Allow-Origin","http://localhost:5173"));
        mvc.perform(options("/api/live").header("Origin","https://unknown.example").header("Access-Control-Request-Method","GET"))
            .andExpect(status().isForbidden());
    }
    static Document indicator() {
        return new Document("_id","live:BTCUSDT:2026-10-16T09:00:00Z").append("symbol","BTCUSDT")
            .append("mode","live").append("run_id","live").append("trade_count",10)
            .append("window_start",Date.from(Instant.parse("2026-10-16T09:00:00Z")))
            .append("window_end",Date.from(Instant.parse("2026-10-16T09:01:00Z")))
            .append("avg_price",new Decimal128(new BigDecimal("67000.123456789123456789")))
            .append("min_price","66900.00").append("max_price","67100.00").append("open_price","66900.00")
            .append("close_price","67010.25").append("base_volume","1.25").append("quote_volume","83762.8125");
    }
    static Document alert() {
        return new Document("symbol","BTCUSDT").append("mode","live").append("run_id","live")
            .append("type","VOLUME_SPIKE").append("severity","critical").append("observed_value",4.2)
            .append("threshold",2.0).append("baseline",50820.0).append("unit","ratio").append("reason","Explained alert");
    }
}

