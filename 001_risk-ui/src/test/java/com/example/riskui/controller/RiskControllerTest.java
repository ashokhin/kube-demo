package com.example.riskui.controller;

import com.example.riskui.model.JobRequest;
import com.example.riskui.model.JobStatus;
import com.example.riskui.service.JobHistoryService;
import com.example.riskui.service.KafkaJobPublisher;
import com.example.riskui.service.KubernetesJobService;
import com.example.riskui.service.RiskEngineClient;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(RiskController.class)
@Import(SimpleMeterRegistry.class)
class RiskControllerTest {

    @Autowired
    MockMvc mvc;

    @Autowired
    ObjectMapper mapper;

    @MockBean
    JobHistoryService jobHistoryService;

    @MockBean
    KafkaJobPublisher kafkaJobPublisher;

    @MockBean
    KubernetesJobService k8sJobService;

    @MockBean
    RiskEngineClient riskEngineClient;

    @Test
    void calculate_returns_result_from_risk_engine() throws Exception {
        when(riskEngineClient.calculateRisk("PORTFOLIO_A", "v1.0"))
                .thenReturn(Map.of("riskScore", 0.42, "portfolioId", "PORTFOLIO_A"));

        mvc.perform(post("/api/calculate")
                        .param("portfolioId", "PORTFOLIO_A")
                        .param("modelVersion", "v1.0"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.riskScore").value(0.42));
    }

    @Test
    void launch_spark_job_returns_accepted_with_job_name() throws Exception {
        when(k8sJobService.launchSparkJob(any()))
                .thenReturn(JobStatus.submitted("spark-calc-v1-0-1234567"));

        JobRequest request = new JobRequest("v1.0", "PORTFOLIO_A", "base");

        mvc.perform(post("/api/jobs/spark")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(mapper.writeValueAsString(request)))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.jobName").value("spark-calc-v1-0-1234567"))
                .andExpect(jsonPath("$.status").value("SUBMITTED"));
    }

    @Test
    void get_job_status_returns_stub_response() throws Exception {
        mvc.perform(get("/api/jobs/spark-calc-v1-0-1234567/status"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.jobName").value("spark-calc-v1-0-1234567"));
    }
}
