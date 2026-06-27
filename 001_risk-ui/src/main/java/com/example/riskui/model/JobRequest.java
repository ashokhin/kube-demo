package com.example.riskui.model;

import io.swagger.v3.oas.annotations.media.Schema;

// Parameters passed by the user when launching a spark-calculator Job.
// risk-ui injects these as environment variables into the Kubernetes Job spec.
@Schema(description = "Parameters for a spark-calculator risk model run")
public record JobRequest(

        @Schema(description = "Risk model version to use", example = "v2.1")
        String modelVersion,

        @Schema(description = "Portfolio identifier to calculate risk for", example = "PORTFOLIO_A")
        String portfolioId,

        @Schema(description = "Scenario name (base, stress, adverse)", example = "base")
        String scenario
) {}
