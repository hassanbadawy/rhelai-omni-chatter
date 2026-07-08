{{- define "locate-anything.fullname" -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "locate-anything.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/name: locate-anything
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.image.tag | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "locate-anything.selectorLabels" -}}
app.kubernetes.io/name: locate-anything
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
