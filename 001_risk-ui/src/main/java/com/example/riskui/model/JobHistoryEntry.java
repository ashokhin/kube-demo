package com.example.riskui.model;

import java.time.Instant;

public record JobHistoryEntry(
        String id,
        String type,
        String portfolioId,
        String modelVersion,
        String scenario,
        boolean success,
        int httpStatus,
        long durationMs,
        Instant timestamp
) {}
