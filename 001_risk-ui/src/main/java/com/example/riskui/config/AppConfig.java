package com.example.riskui.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestClient;

@Configuration
public class AppConfig {

    @Value("${risk.engine.url:http://risk-engine:8081}")
    private String riskEngineUrl;

    // RestClient for calling risk-engine directly (synchronous, blocking).
    // Inject the Spring Boot auto-configured builder so Jackson message converters are included.
    // For high-throughput scenarios, replace with WebClient (reactive).
    @Bean
    public RestClient riskEngineRestClient(RestClient.Builder builder) {
        return builder
                .baseUrl(riskEngineUrl)
                .build();
    }
}
