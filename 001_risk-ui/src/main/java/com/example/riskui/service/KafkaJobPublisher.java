package com.example.riskui.service;

import com.example.riskui.model.JobRequest;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Service;

import java.util.concurrent.CompletableFuture;

@Service
public class KafkaJobPublisher {

    private static final Logger log = LoggerFactory.getLogger(KafkaJobPublisher.class);

    private final KafkaTemplate<String, JobRequest> kafkaTemplate;
    private final String topic;
    private final Counter publishedCounter;
    private final Counter failedCounter;

    public KafkaJobPublisher(
            KafkaTemplate<String, JobRequest> kafkaTemplate,
            @Value("${kafka.topics.risk-jobs:risk-jobs}") String topic,
            MeterRegistry registry) {
        this.kafkaTemplate = kafkaTemplate;
        this.topic = topic;
        this.publishedCounter = Counter.builder("riskui_kafka_published_total")
                .description("Total job requests published to Kafka")
                .register(registry);
        this.failedCounter = Counter.builder("riskui_kafka_publish_failed_total")
                .description("Total Kafka publish failures")
                .register(registry);
    }

    public void publish(String key, JobRequest request) {
        CompletableFuture<SendResult<String, JobRequest>> future =
                kafkaTemplate.send(topic, key, request);
        future.whenComplete((result, ex) -> {
            if (ex != null) {
                failedCounter.increment();
                log.error("Failed to publish job request key={} to {}: {}", key, topic, ex.getMessage());
            } else {
                publishedCounter.increment();
                log.info("Published job request key={} to {} offset={}",
                        key, topic, result.getRecordMetadata().offset());
            }
        });
    }
}
