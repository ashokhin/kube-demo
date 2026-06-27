package com.example.riskui.service;

import com.example.riskui.model.JobRequest;
import com.example.riskui.model.JobStatus;
import io.kubernetes.client.openapi.ApiClient;
import io.kubernetes.client.openapi.ApiException;
import io.kubernetes.client.openapi.Configuration;
import io.kubernetes.client.openapi.apis.BatchV1Api;
import io.kubernetes.client.openapi.models.*;
import io.kubernetes.client.util.Config;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.util.List;
import java.util.Map;

/**
 * Launches spark-calculator as a Kubernetes Job using the official Java client.
 *
 * The service account bound to this pod must have RBAC permissions:
 *   - verbs: [create, get, list]
 *   - resources: [jobs]
 *   - apiGroups: [batch]
 *
 * See: 006_gitops/manifests/rbac/risk-ui-role.yaml
 *
 * When KUBERNETES_ENABLED=false (local docker-compose mode), all methods
 * return a DISABLED status so the app still starts without a cluster.
 */
@Service
public class KubernetesJobService {

    private static final Logger log = LoggerFactory.getLogger(KubernetesJobService.class);

    @Value("${kubernetes.enabled:true}")
    private boolean kubernetesEnabled;

    @Value("${kubernetes.namespace:hadoop-demo-dev}")
    private String namespace;

    @Value("${spark.calculator.image:nexus.company.internal/hadoop-demo/spark-calculator:latest}")
    private String sparkImage;

    @Value("${spark.calculator.mock-mode:true}")
    private boolean sparkMockMode;

    private BatchV1Api batchApi;

    // Initialize the Kubernetes client using the in-cluster config (mounted ServiceAccount token).
    // Falls back gracefully when kubernetesEnabled=false (local development).
    @EventListener(ApplicationReadyEvent.class)
    public void initKubernetesClient() {
        if (!kubernetesEnabled) {
            log.info("Kubernetes integration disabled (KUBERNETES_ENABLED=false)");
            return;
        }
        try {
            ApiClient client = Config.fromCluster();
            Configuration.setDefaultApiClient(client);
            batchApi = new BatchV1Api();
            log.info("Kubernetes client initialized, namespace={}", namespace);
        } catch (IOException e) {
            log.error("Failed to initialize Kubernetes client — is this running inside a pod?", e);
        }
    }

    /**
     * Creates a Kubernetes Job that runs spark-calculator with the given parameters.
     *
     * The Job name is derived from the model version and a timestamp to ensure uniqueness.
     * Kubernetes garbage-collects completed Jobs after ttlSecondsAfterFinished (set in the spec).
     */
    public JobStatus launchSparkJob(JobRequest request) {
        if (!kubernetesEnabled) {
            return JobStatus.disabled("Kubernetes is disabled in local mode (KUBERNETES_ENABLED=false)");
        }

        String jobName = buildJobName(request.modelVersion());
        V1Job job = buildJobSpec(jobName, request);

        try {
            batchApi.createNamespacedJob(namespace, job).execute();
            log.info("Launched Kubernetes Job name={} model={} portfolio={} scenario={}",
                    jobName, request.modelVersion(), request.portfolioId(), request.scenario());
            return JobStatus.submitted(jobName);
        } catch (ApiException e) {
            log.error("Failed to create Kubernetes Job: status={} body={}", e.getCode(), e.getResponseBody());
            throw new RuntimeException("Kubernetes API error: " + e.getCode(), e);
        }
    }

    private String buildJobName(String modelVersion) {
        // Job names must be valid DNS labels: lowercase alphanumeric and hyphens.
        String sanitized = modelVersion.toLowerCase().replaceAll("[^a-z0-9]", "-");
        long ts = System.currentTimeMillis() / 1000;
        return "spark-calc-" + sanitized + "-" + ts;
    }

    private V1Job buildJobSpec(String jobName, JobRequest request) {
        // Environment variables are the primary interface for parameterizing the Job.
        // This mirrors how ArgoCD/Helm would inject values in a real GitOps workflow,
        // but here we set them dynamically at job-creation time.
        List<V1EnvVar> env = List.of(
                envVar("MODEL_VERSION", request.modelVersion()),
                envVar("PORTFOLIO_ID", request.portfolioId()),
                envVar("SCENARIO", request.scenario()),
                envVar("MOCK_MODE", String.valueOf(sparkMockMode))
        );

        return new V1Job()
                .apiVersion("batch/v1")
                .kind("Job")
                .metadata(new V1ObjectMeta()
                        .name(jobName)
                        .namespace(namespace)
                        .labels(Map.of(
                                "app", "spark-calculator",
                                "app.kubernetes.io/name", "spark-calculator",
                                "launched-by", "risk-ui",
                                "model-version", request.modelVersion().replaceAll("[^a-zA-Z0-9-]", "-")
                        )))
                .spec(new V1JobSpec()
                        // Automatically delete the Job 1 hour after completion.
                        .ttlSecondsAfterFinished(3600)
                        .backoffLimit(2)
                        .template(new V1PodTemplateSpec()
                                .metadata(new V1ObjectMeta()
                                        .labels(Map.of("app.kubernetes.io/name", "spark-calculator")))
                                .spec(new V1PodSpec()
                                        .restartPolicy("Never")
                                        .serviceAccountName("spark-calculator")
                                        .containers(List.of(
                                                new V1Container()
                                                        .name("spark-calculator")
                                                        .image(sparkImage)
                                                        .env(env)
                                        )))));
    }

    private V1EnvVar envVar(String name, String value) {
        return new V1EnvVar().name(name).value(value);
    }
}
