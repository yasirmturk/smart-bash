# Smart Bash MCP

An MCP server that runs shell commands and optionally summarizes long output with an OpenAI-compatible chat-completions endpoint. Short output and raw-mode requests bypass the model.

## Safety and privacy

This server can execute arbitrary shell commands with the permissions of its user. Use it only with trusted MCP clients and their approval controls; it is not a sandbox. Commands and up to 8,000 characters of their output are sent to the configured model endpoint when summarization is triggered. A remote endpoint receives that data. Model summaries are lossy and may contain errors or instructions from untrusted command output.

## Install

Requirements: Python 3.10+ and pip. A model endpoint is optional for raw mode and short output.

From the downloaded or cloned project directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

The commands above use a POSIX shell; on Windows, use `.venv\Scripts\python.exe` instead.

For summarized output, start an OpenAI-compatible chat-completions server separately. For example, with `llama-server` installed:

```sh
llama-server -hf Qwen/Qwen2.5-Coder-7B-Instruct-GGUF:Q4_K_M \
  --host 127.0.0.1 --port 9931 -c 8192
```

If the endpoint requires a key, set `LOCAL_API_KEY` in your MCP client configuration or environment. Keep real keys out of the repository. Set `LOCAL_LLM_MODEL` if the endpoint requires a different model name.

## Register with an MCP client

Use the **absolute path** to this checkout and its virtual environment. For clients that start servers with a restricted `PATH`, use the absolute Python executable path, not `python`.

**Claude Code**, from the project directory:

```sh
claude mcp add smart-bash --scope user \
  -- "$(pwd)/.venv/bin/python" "$(pwd)/server.py"
```

Add client environment settings with `claude mcp add` options as needed; see `claude mcp add --help`. Check the connection with `claude mcp list`.

**Copilot CLI**: add this entry under `mcpServers` in `~/.copilot/mcp-config.json`, replacing `<checkout>` with the absolute checkout path:

```json
"smart-bash": {
  "type": "local",
  "tools": ["*"],
  "command": "<checkout>/.venv/bin/python",
  "args": ["<checkout>/server.py"],
  "env": {
    "LOCAL_LLM_URL": "http://127.0.0.1:9931/v1/chat/completions",
    "LOCAL_LLM_MODEL": "qwen-local"
  }
}
```

Add `LOCAL_API_KEY` to the client environment only if the endpoint requires it. Restart or reconnect the client, then check that it exposes `execute_local_bash`. Other stdio MCP clients can use the same Python executable, script and environment variables.

## Tool

`execute_local_bash(command, cwd=".", return_raw=False, timeout=120000)`

- `command`: shell command to execute; `cwd`: working directory.
- `return_raw`: skip summarization. Output includes a marker; stdout and stderr are combined and surrounding whitespace is trimmed, so it is not byte-exact.
- `timeout`: milliseconds, limited by `BASH_MAX_TIMEOUT_MS`.

Output of 300 or more characters is summarized by default; only the first 8,000 characters are sent to the model. If the endpoint fails or returns an invalid response, a labeled fallback includes the first 1,000 characters. Nonzero command exits are reported explicitly. Use raw mode for diffs, JSON, tabular data and other output where a summary would be unreliable.

## Configuration

| Environment variable | Default | Purpose |
|---|---|---|
| `LOCAL_LLM_URL` | `http://127.0.0.1:9931/v1/chat/completions` | Chat-completions endpoint |
| `LOCAL_LLM_MODEL` | `qwen-local` | Model name sent in requests |
| `LOCAL_API_KEY` | unset | Optional bearer token |
| `LOCAL_LLM_TIMEOUT` | `30` | Model request timeout in seconds |
| `BASH_DEFAULT_TIMEOUT_MS` | `120000` | Default command timeout |
| `BASH_MAX_TIMEOUT_MS` | `600000` | Maximum command timeout; at least the default |
| `SMART_BASH_LOKI_URL` | unset | Optional Loki base URL for usage metrics; overrides the opt-in file |

## Local savings report

The optional Grafana and Loki stack records only mode and numeric byte and token estimates, not command text or output. The dashboard compares the bytes in the original combined output with the response returned to the agent; raw-mode responses are compared with themselves. Tokens are **rough estimates** using four UTF-8 bytes per token, not actual tokenizer counts or complete agent context usage. Savings can be negative when a response grows. Timeout and startup errors are not recorded. Model request tokens and previous tool calls are not measured.

The dashboard defaults to the last 7 days; change the time picker to view another range. Loki data is stored in the `smart-bash-loki-data` Podman volume and survives container restarts, but metrics only exist from when telemetry was enabled and the MCP server reconnected. No earlier command history can be reconstructed.

The **Context window size (tokens)** dashboard textbox defaults to `200000`; set it to the model's context limit. The dashboard uses it to show the average estimated per-call output reduction as a percentage of one context window, and cumulative estimated reductions as context-window equivalents for the selected time range. These are comparison estimates only: they are not actual agent context occupancy, model tokenizer counts, or a count of conversations/windows saved. Adjust the textbox when comparing models with different limits.

With Podman running, execute the following from the project directory:

```sh
podman network create smart-bash-monitoring
podman volume create smart-bash-loki-data
podman volume create smart-bash-grafana-data
podman run -d --name smart-bash-loki --network smart-bash-monitoring \
  --restart unless-stopped -p 127.0.0.1:3100:3100 \
  -v smart-bash-loki-data:/loki \
  -v "$(pwd)/monitoring/loki.yaml:/etc/loki/config.yaml:ro" \
  docker.io/grafana/loki:3.5.7 -config.file=/etc/loki/config.yaml
podman run -d --name smart-bash-grafana --network smart-bash-monitoring \
  --restart unless-stopped -p 127.0.0.1:3300:3000 \
  -e GF_AUTH_ANONYMOUS_ENABLED=true -e GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer \
  -e GF_AUTH_BASIC_ENABLED=false -e GF_AUTH_DISABLE_LOGIN_FORM=true \
  -e GF_ANALYTICS_REPORTING_ENABLED=false -e GF_ANALYTICS_CHECK_FOR_UPDATES=false \
  -v smart-bash-grafana-data:/var/lib/grafana \
  -v "$(pwd)/monitoring/grafana:/etc/grafana/provisioning:ro" \
  docker.io/grafana/grafana:12.2.0
```

To enable metrics without changing client settings, create a file containing the local Loki URL:

```sh
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/smart-bash"
printf '%s\n' 'http://127.0.0.1:3100' > "${XDG_CONFIG_HOME:-$HOME/.config}/smart-bash/loki-url"
```

Alternatively, set `SMART_BASH_LOKI_URL` in the MCP client's server environment. An empty environment value disables telemetry even if the file exists. Reconnect the MCP server to load changes. Open [the report](http://127.0.0.1:3300/d/smart-bash-savings) after a command runs; choose a time range to generate a report for that period. Only local users should be able to access these unauthenticated services. Keep the loopback bindings and do not point telemetry at an untrusted endpoint. If Loki is unavailable, commands still run and a warning is sent to stderr; missed events are not retried.

The containers and named volumes persist independently of this checkout. Restart stopped containers with `podman start smart-bash-loki smart-bash-grafana`; on macOS, the Podman machine must also be running. Setup commands create resources once; don't rerun them when the containers already exist.

## Troubleshooting

- **MCP connection fails:** run the configured Python executable with `server.py` directly and check stderr; verify the environment and installed requirements.
- **Summary unavailable:** check the endpoint, model name and authentication. The fallback includes the exception type. Raw mode does not require the model.
- **Command fails:** check its reported exit status and output, working directory and timeout.

## License

MIT; see [LICENSE](LICENSE).
