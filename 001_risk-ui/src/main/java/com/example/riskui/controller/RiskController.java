package com.example.riskui.controller;

import com.example.riskui.model.JobHistoryEntry;
import com.example.riskui.model.JobRequest;
import com.example.riskui.model.JobStatus;
import com.example.riskui.service.JobHistoryService;
import com.example.riskui.service.KafkaJobPublisher;
import com.example.riskui.service.KubernetesJobService;
import com.example.riskui.service.RiskEngineClient;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
@Tag(name = "Risk", description = "Endpoints for launching risk model computations")
public class RiskController {

    private final KubernetesJobService k8sJobService;
    private final RiskEngineClient riskEngineClient;
    private final KafkaJobPublisher kafkaJobPublisher;
    private final JobHistoryService jobHistory;
    private final Counter calculateCounter;
    private final Counter sparkJobCounter;
    private final Counter kafkaJobCounter;

    public RiskController(
            KubernetesJobService k8sJobService,
            RiskEngineClient riskEngineClient,
            KafkaJobPublisher kafkaJobPublisher,
            JobHistoryService jobHistory,
            MeterRegistry registry) {
        this.k8sJobService = k8sJobService;
        this.riskEngineClient = riskEngineClient;
        this.kafkaJobPublisher = kafkaJobPublisher;
        this.jobHistory = jobHistory;
        this.calculateCounter = Counter.builder("riskui_calculate_requests_total")
                .description("Synchronous risk-engine calculations triggered")
                .register(registry);
        this.sparkJobCounter = Counter.builder("riskui_spark_jobs_total")
                .description("Spark jobs launched via Kubernetes API")
                .register(registry);
        this.kafkaJobCounter = Counter.builder("riskui_kafka_jobs_total")
                .description("Risk jobs dispatched via Kafka")
                .register(registry);
    }

    @PostMapping("/calculate")
    @Operation(summary = "Run risk calculation via risk-engine (synchronous REST)")
    public ResponseEntity<Map<String, Object>> calculate(
            @RequestParam String portfolioId,
            @RequestParam String modelVersion) {
        calculateCounter.increment();
        long t0 = System.currentTimeMillis();
        Map<String, Object> result = riskEngineClient.calculateRisk(portfolioId, modelVersion);
        jobHistory.record("calculate", portfolioId, modelVersion, null, true, 200,
                System.currentTimeMillis() - t0);
        return ResponseEntity.ok(result);
    }

    @PostMapping("/jobs/spark")
    @Operation(summary = "Launch spark-calculator Job via Kubernetes API (asynchronous)")
    public ResponseEntity<JobStatus> launchSparkJob(@RequestBody JobRequest request) {
        sparkJobCounter.increment();
        long t0 = System.currentTimeMillis();
        JobStatus status = k8sJobService.launchSparkJob(request);
        jobHistory.record("spark", request.portfolioId(), request.modelVersion(),
                request.scenario(), true, 202, System.currentTimeMillis() - t0);
        return ResponseEntity.accepted().body(status);
    }

    @PostMapping("/jobs/async")
    @Operation(summary = "Dispatch risk job via Kafka (async, event-driven)")
    public ResponseEntity<Map<String, String>> dispatchAsyncJob(@RequestBody JobRequest request) {
        kafkaJobCounter.increment();
        long t0 = System.currentTimeMillis();
        String key = request.portfolioId() + ":" + request.modelVersion();
        kafkaJobPublisher.publish(key, request);
        jobHistory.record("async", request.portfolioId(), request.modelVersion(),
                request.scenario(), true, 202, System.currentTimeMillis() - t0);
        return ResponseEntity.accepted().body(Map.of(
                "status", "QUEUED",
                "topic", "risk-jobs",
                "key", key,
                "message", "Job request published to Kafka. risk-engine will process asynchronously."
        ));
    }

    @GetMapping("/jobs/history")
    @Operation(summary = "Last 50 dispatched jobs (in-memory, resets on restart)")
    public ResponseEntity<List<JobHistoryEntry>> getHistory() {
        return ResponseEntity.ok(jobHistory.getAll());
    }

    @GetMapping("/jobs/{jobName}/status")
    @Operation(summary = "Get Kubernetes Job status by name")
    public ResponseEntity<Map<String, String>> getJobStatus(@PathVariable String jobName) {
        return ResponseEntity.ok(Map.of(
                "jobName", jobName,
                "status", "RUNNING",
                "message", "Query `kubectl get job " + jobName + "` for real-time status"
        ));
    }
}
