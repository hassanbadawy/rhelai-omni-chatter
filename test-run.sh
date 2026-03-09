API_KEY="sk-GR5wzJ7jN5YrZYJ711Dfbrco8Z0vQR1K7hHJOX9F0WU"
SESSION_ID="my-chat-session-1"

INPUT="${1:-Hello, how are you?}"

curl --request POST \
     --url 'http://localhost:7860/api/v1/run/4d417b7d-f05b-4a12-af90-0cc5e9ee21a0?stream=false' \
     --header 'Content-Type: application/json' \
     --header "x-api-key: ${API_KEY}" \
     --data @- <<EOF
{
  "output_type": "chat",
  "input_type": "chat",
  "input_value": "${INPUT}",
  "session_id": "${SESSION_ID}"
}
EOF