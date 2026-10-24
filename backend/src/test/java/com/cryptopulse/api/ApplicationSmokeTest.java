package com.cryptopulse.api;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = "spring.data.mongodb.uri=mongodb://localhost:1/?serverSelectionTimeoutMS=100&connectTimeoutMS=100")
@AutoConfigureMockMvc
class ApplicationSmokeTest {
    @Autowired MockMvc mvc;

    @Test
    void startsAndDocumentsAllFiveRoutesWithoutMongo() throws Exception {
        mvc.perform(get("/v3/api-docs")).andExpect(status().isOk())
                .andExpect(jsonPath("$.paths['/api/live'].get").exists())
                .andExpect(jsonPath("$.paths['/api/analytics'].get").exists())
                .andExpect(jsonPath("$.paths['/api/alerts'].get").exists())
                .andExpect(jsonPath("$.paths['/api/sentiment'].get").exists())
                .andExpect(jsonPath("$.paths['/api/replay/runs'].get").exists())
                .andExpect(jsonPath("$.paths['/api/replay/{runId}'].get").exists());
        mvc.perform(get("/actuator/health/liveness")).andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("UP"));
    }

    @Test
    void realDriverFailureReturnsSafeUnavailableAndReadinessDown() throws Exception {
        mvc.perform(get("/api/live")).andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.code").value("DATA_UNAVAILABLE"));
        mvc.perform(get("/actuator/health/readiness")).andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.status").value("DOWN"))
                .andExpect(jsonPath("$.components").doesNotExist());
    }
}
