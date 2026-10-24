package com.cryptopulse.api;

import org.bson.Document;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import java.util.UUID;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/** Optional real-Mongo verification; always uses a unique disposable database. */
@SpringBootTest
@AutoConfigureMockMvc
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@EnabledIfEnvironmentVariable(named = "API_TEST_MONGO_URI", matches = ".+")
class MongoIntegrationTest {
    private static final String DATABASE = "cryptopulse_api_test_" + UUID.randomUUID().toString().replace("-", "");
    @Autowired MongoTemplate mongo;
    @Autowired MockMvc mvc;

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) {
        registry.add("spring.data.mongodb.uri", () -> System.getenv("API_TEST_MONGO_URI"));
        registry.add("spring.data.mongodb.database", () -> DATABASE);
    }

    @BeforeEach
    void fixtures() {
        mongo.getDb().drop();
        mongo.insert(MarketApiTest.indicator().append("_id", "live"), "indicators");
        mongo.insert(MarketApiTest.indicator().append("_id", "replay").append("mode", "replay").append("run_id", "replay-demo"), "indicators");
    }

    @AfterAll
    void cleanup() { mongo.getDb().drop(); }

    @Test
    void actualMongoSeparatesLiveAndReplayAndAppliesTimeBounds() throws Exception {
        mvc.perform(get("/api/live?symbol=BTCUSDT"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].avg_price").value("67000.123456789123456789"));
        mvc.perform(get("/api/replay/replay-demo")).andExpect(status().isOk())
                .andExpect(jsonPath("$.indicators.length()").value(1)).andExpect(jsonPath("$.indicators[0].run_id").value("replay-demo"));
        mvc.perform(get("/api/analytics?symbol=BTCUSDT&from=2026-10-16T08:00:00Z&to=2026-10-16T09:00:00Z")).andExpect(status().isOk())
                .andExpect(jsonPath("$.indicators").isEmpty());
    }

    @Test
    void actualMongoSupportsSentimentArrayFilter() throws Exception {
        mongo.insert(new Document("event_id", "sentiment:demo").append("symbols", java.util.List.of("BTC"))
                .append("trade_symbols", java.util.List.of("BTCUSDT"))
                .append("score", "0.5").append("event_time", java.util.Date.from(java.time.Instant.now())), "sentiment");
        mvc.perform(get("/api/sentiment?symbol=BTCUSDT")).andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1));
        mvc.perform(get("/api/sentiment?symbol=ETHUSDT")).andExpect(status().isOk())
                .andExpect(jsonPath("$").isEmpty());
    }

    @Test
    void runsIncludeAlertOnlyRunsAndExcludeLive() throws Exception {
        mongo.insert(MarketApiTest.alert().append("run_id", "replay-alert-only").append("mode", "replay")
                .append("event_time", java.util.Date.from(java.time.Instant.parse("2026-10-17T09:00:00Z"))), "alerts");
        mongo.insert(MarketApiTest.alert().append("run_id", "replay-demo").append("mode", "replay")
                .append("event_time", java.util.Date.from(java.time.Instant.parse("2026-10-16T09:01:00Z"))), "alerts");
        mvc.perform(get("/api/replay/runs")).andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0].run_id").value("replay-alert-only"))
                .andExpect(jsonPath("$[0].indicator_count").value(0))
                .andExpect(jsonPath("$[0].alert_count").value(1))
                .andExpect(jsonPath("$[1].run_id").value("replay-demo"))
                .andExpect(jsonPath("$[1].indicator_count").value(1))
                .andExpect(jsonPath("$[1].alert_count").value(1));
    }
}
