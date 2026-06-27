package com.example.riskui.service;

import com.example.riskui.model.JobHistoryEntry;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.ConcurrentLinkedDeque;

@Service
public class JobHistoryService {

    private static final int MAX_ENTRIES = 50;

    private final ConcurrentLinkedDeque<JobHistoryEntry> deque = new ConcurrentLinkedDeque<>();

    public void record(String type, String portfolioId, String modelVersion,
                       String scenario, boolean success, int httpStatus, long durationMs) {
        deque.addFirst(new JobHistoryEntry(
                UUID.randomUUID().toString(),
                type,
                portfolioId,
                modelVersion,
                scenario,
                success,
                httpStatus,
                durationMs,
                Instant.now()
        ));
        if (deque.size() > MAX_ENTRIES) {
            deque.pollLast();
        }
    }

    public List<JobHistoryEntry> getAll() {
        return new ArrayList<>(deque);
    }
}
