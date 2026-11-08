{{- define "myapp.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "myapp.labels" -}}
app: {{ .Chart.Name }}
release: {{ .Release.Name }}
{{- end -}}
