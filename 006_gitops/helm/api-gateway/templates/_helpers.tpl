{{/*
Expand the name of the chart.
*/}}
{{- define "api-gateway.name" -}}
{{- .Chart.Name }}
{{- end }}

{{/*
Create a fully qualified app name.
Truncated to 63 chars: Kubernetes DNS label limit.
*/}}
{{- define "api-gateway.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to every resource in this chart.
helm.sh/chart        – used by Helm to track the release
app.kubernetes.io/*  – standard K8s recommended labels
*/}}
{{- define "api-gateway.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/name: {{ include "api-gateway.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels — used by Service and Deployment to match pods.
Must be stable (never change after first deploy) because
changing selectors on a Deployment requires delete+recreate.
*/}}
{{- define "api-gateway.selectorLabels" -}}
app.kubernetes.io/name: {{ include "api-gateway.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
