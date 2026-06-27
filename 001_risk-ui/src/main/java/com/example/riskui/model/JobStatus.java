package com.example.riskui.model;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Status of a launched Kubernetes Job")
public record JobStatus(

        @Schema(description = "Kubernetes Job name", example = "spark-calculator-v2-1-abc123")
        String jobName,

        @Schema(description = "Job launch status", example = "SUBMITTED")
        String status,

        @Schema(description = "Human-readable message")
        String message
) {
    public static JobStatus submitted(String jobName) {
        return new JobStatus(jobName, "SUBMITTED",
                "Job submitted to Kubernetes. Check status with kubectl get job " + jobName);
    }

    public static JobStatus disabled(String reason) {
        return new JobStatus("n/a", "DISABLED", reason);
    }
}
