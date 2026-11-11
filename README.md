# Smart Bash MCP

<p align="center">
  <img src="assets/smart-bash-logo.svg" alt="Smart Bash — cut tokens, lower costs" width="640">
</p>

[![Tests](https://github.com/yasirmturk/smart-bash/actions/workflows/tests.yml/badge.svg)](https://github.com/yasirmturk/smart-bash/actions/workflows/tests.yml)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20me%20a-coffee-FFDD00?logo=buymeacoffee&logoColor=000000)](https://www.buymeacoffee.com/yturk)

An MCP server that runs shell commands and optionally summarizes long output with an OpenAI-compatible chat-completions endpoint. Short output and raw-mode requests bypass the model.

The dashboard reports rough estimates of tokens removed from tool output and their equivalent share of a context window over 1-, 7-, and 30-day periods; these are not actual session or context-window usage. More stats are planned, and users are welcome to share findings and ideas through GitHub issues or pull requests.

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

For local Docker or Podman setup, telemetry details, report interpretation, and troubleshooting, see **[Monitoring setup](MONITORING.md)**.

## Troubleshooting

- **MCP connection fails:** run the configured Python executable with `server.py` directly and check stderr; verify the environment and installed requirements.
- **Summary unavailable:** check the endpoint, model name and authentication. The fallback includes the exception type. Raw mode does not require the model.
- **Command fails:** check its reported exit status and output, working directory and timeout.

## License

MIT; see [LICENSE](LICENSE).
