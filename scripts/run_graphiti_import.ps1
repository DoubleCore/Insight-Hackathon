$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$ImportCommand = @(
    "graphiti-main\graphiti-main\.venv\Scripts\python.exe"
    "-X"
    "utf8"
    "scripts\import_graphiti_episodes.py"
    "--neo4j-uri"
    "bolt://localhost:7687"
    "--neo4j-user"
    "neo4j"
    "--neo4j-password"
    "password"
    "--skip-existing"
    "--continue-on-error"
    "--episode-retries"
    "3"
    "--retry-delay-seconds"
    "5"
    "--failure-log"
    "data\graphiti\import_failures.jsonl"
    "--llm-api-key-env"
    "DEEPSEEK_API_KEY"
    "--llm-base-url"
    "https://api.deepseek.com"
    "--llm-model"
    "deepseek-chat"
    "--llm-small-model"
    "deepseek-chat"
    "--reranker-model"
    "deepseek-chat"
    "--structured-output-mode"
    "json_object"
    "--embedding-api-key-env"
    "SILICONFLOW_API_KEY"
    "--embedding-base-url"
    "https://api.siliconflow.cn/v1"
    "--embedding-model"
    "BAAI/bge-m3"
) -join " "

python -X utf8 scripts\load_ai_keys.py `
    --services deepseek siliconflow `
    --command $ImportCommand

exit $LASTEXITCODE
