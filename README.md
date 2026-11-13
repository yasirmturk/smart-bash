# Smart Bash MCP

<p align="center">
  <img src="assets/smart-bash-logo.svg" alt="Smart Bash — cut tokens, lower costs" width="640">
</p>

[![Tests](https://github.com/yasirmturk/smart-bash/actions/workflows/tests.yml/badge.svg)](https://github.com/yasirmturk/smart-bash/actions/workflows/tests.yml)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20me%20a-coffee-FFDD00?logo=buymeacoffee&logoColor=000000)](https://www.buymeacoffee.com/yturk)

Smart Bash is a small MCP server that runs shell commands and summarizes long output, so less text is sent back to your AI assistant. It works with Claude Code, GitHub Copilot CLI and desktop app, and other stdio-compatible MCP clients.

## Prerequisites

- Python 3.10 or later and pip
- Claude Code, GitHub Copilot CLI or desktop app, or another MCP client
- Optionally, [llama.cpp](https://github.com/ggml-org/llama.cpp) for local summaries

Short output and `return_raw=True` work without a language model.

## Install

From the project directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

### Optional: run a local model

On macOS with Homebrew:

```sh
brew install llama.cpp
llama-server -hf Qwen/Qwen2.5-Coder-7B-Instruct-GGUF:Q4_K_M \
  --host 127.0.0.1 --port 9931 -c 8192
```

On first run, llama.cpp downloads the quantized Qwen2.5-Coder 7B model. Keep the server running while using Smart Bash. Other llama.cpp installation options are in its [README](https://github.com/ggml-org/llama.cpp).

## Connect your MCP client

Use absolute paths to the Python executable and `server.py`.

**Claude Code** — run this from the project directory:

```sh
claude mcp add smart-bash --scope user \
  -e LOCAL_LLM_URL=http://127.0.0.1:9931/v1/chat/completions \
  -e LOCAL_LLM_MODEL=qwen-local \
  -- "$(pwd)/.venv/bin/python" "$(pwd)/server.py"
```

**GitHub Copilot CLI and desktop app** — both use the same MCP configuration. Add this entry to `~/.copilot/mcp-config.json`, replacing `/absolute/path/to/smart-bash` with the project directory:

```json
{
  "mcpServers": {
    "smart-bash": {
      "type": "local",
      "tools": ["*"],
      "command": "/absolute/path/to/smart-bash/.venv/bin/python",
      "args": ["/absolute/path/to/smart-bash/server.py"],
      "env": {
        "LOCAL_LLM_URL": "http://127.0.0.1:9931/v1/chat/completions",
        "LOCAL_LLM_MODEL": "qwen-local"
      }
    }
  }
}
```

Reconnect the server in your MCP client. You can omit the model settings if you only need short output or raw mode.

## Use it

Ask your assistant to run a shell command with `execute_local_bash`. By default, output shorter than 300 characters is returned as-is; longer output is summarized. If the model is unavailable, Smart Bash returns a labeled fallback with up to 1,000 characters of the original output.

Use `return_raw=True` when you need the original command output rather than a summary—for example, for diffs, JSON, or tables. It skips the model, but still combines stdout and stderr, trims surrounding whitespace, and adds a marker, so it is not byte-for-byte output.

The tool also accepts `cwd` to choose a working directory and `timeout` in milliseconds (default 120,000; maximum 600,000).

## Safety and privacy

Smart Bash runs commands with your user permissions; it is **not a sandbox**. Review commands and use your MCP client's approval controls. For long-output summaries, the command and up to 8,000 characters of output are sent to the configured model endpoint. Use a local model if you don't want that data sent to a remote service.

## Monitoring

The optional dashboard shows rough token and context-window savings estimates, not actual model token counts or agent context usage. See **[MONITORING.md](MONITORING.md)** for local Docker or Podman setup.

## Contributing

More stats and improvements are planned. Share your findings or suggestions in [GitHub issues](https://github.com/yasirmturk/smart-bash/issues) or pull requests.

## License

[MIT](LICENSE)
