package com.example.riskui.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.util.Map;

// Thin HTTP client for calling risk-engine directly (synchronous short-running jobs).
// risk-engine handles HDFS reads and Hive writes internally.
@Service
public class RiskEngineClient {

    private static final Logger log = LoggerFactory.getLogger(RiskEngineClient.class);

    private final RestClient client;

    public RiskEngineClient(RestClient riskEngineRestClient) {
        this.client = riskEngineRestClient;
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> calculateRisk(String portfolioId, String modelVersion) {
        log.info("Calling risk-engine: portfolio={} model={}", portfolioId, modelVersion);
        return (Map<String, Object>) client.post()
                .uri("/api/calculate")
                .contentType(MediaType.APPLICATION_JSON)
                .body(Map.of("portfolioId", portfolioId, "modelVersion", modelVersion))
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> healthCheck() {
        return (Map<String, Object>) client.get()
                .uri("/healthz")
                .retrieve()
                .body(Map.class);
    }
}
