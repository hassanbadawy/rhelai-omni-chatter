# (Experimental) LLama Stack UI

## Docker Setup

1. Build the container:

```bash
docker build -f Containerfile -t llama-stack-playground .
```

2. Run the UI only (connecting to an external Llama Stack API server):

```bash
./start-dev-container.sh
```

3. Run both API server + UI (two containers from the same image):

```bash
TOGETHER_API_KEY=<your-key> ./start-dev-container.sh --with-api
```

This starts the API server container (`llama-stack-api`) on port 8321 and the UI container (`llama-stack-ui`) on port 8501. The UI is available at `http://localhost:8501`.

To stop both containers:

```bash
docker stop llama-stack-ui llama-stack-api
```

## Developer Setup

1. Start up Llama Stack API server. More details [here](https://llama-stack.readthedocs.io/en/latest/getting_started/index.html).

```
llama stack build --template together --image-type conda

llama stack run together
```

2. (Optional) Register datasets and eval tasks as resources. If you want to run pre-configured evaluation flows (e.g. Evaluations (Generation + Scoring) Page).

```bash
llama-stack-client datasets register \
--dataset-id "mmlu" \
--provider-id "huggingface" \
--url "https://huggingface.co/datasets/llamastack/evals" \
--metadata '{"path": "llamastack/evals", "name": "evals__mmlu__details", "split": "train"}' \
--schema '{"input_query": {"type": "string"}, "expected_answer": {"type": "string", "chat_completion_input": {"type": "string"}}}'
```

```bash
llama-stack-client benchmarks register \
--eval-task-id meta-reference-mmlu \
--provider-id meta-reference \
--dataset-id mmlu \
--scoring-functions basic::regex_parser_multiple_choice_answer
```

3. Start Streamlit UI

```bash
uv run --with ".[ui]" streamlit run llama_stack/distribution/ui/app.py
```

## Environment Variables

| Environment Variable       | Description                        | Default Value             |
|----------------------------|------------------------------------|---------------------------|
| LLAMA_STACK_ENDPOINT       | The endpoint for the Llama Stack   | http://localhost:8321     |
| FIREWORKS_API_KEY          | API key for Fireworks provider     | (empty string)            |
| TOGETHER_API_KEY           | API key for Together provider      | (empty string)            |
| SAMBANOVA_API_KEY          | API key for SambaNova provider     | (empty string)            |
| OPENAI_API_KEY             | API key for OpenAI provider        | (empty string)            |
