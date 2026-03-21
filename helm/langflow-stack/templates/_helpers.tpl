{{/*
Expand the name of the chart.
*/}}
{{- define "langflow-stack.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "langflow-stack.labels" -}}
app.kubernetes.io/part-of: langflow-stack
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{/*
Route host for a given service name
*/}}
{{- define "langflow-stack.routeHost" -}}
{{ . }}-{{ $.Release.Namespace }}.apps.{{ $.Values.clusterDomain }}
{{- end }}

{{/*
Security context for non-root containers
*/}}
{{- define "langflow-stack.securityContext" -}}
allowPrivilegeEscalation: false
runAsNonRoot: true
seccompProfile:
  type: RuntimeDefault
capabilities:
  drop:
    - ALL
{{- end }}
