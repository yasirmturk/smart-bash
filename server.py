#!/usr/bin/env python3
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import json
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("smart-bash")

LOCAL_LLM_URL = os.environ.get("LOCAL_LLM_URL", "http://127.0.0.1:9931/v1/chat/completions")
LOCAL_API_KEY = os.environ.get("LOCAL_API_KEY", "")
LOCAL_LLM_MODEL = os.environ.get("LOCAL_LLM_MODEL", "qwen-local")
LOCAL_LLM_TIMEOUT = float(os.environ.get("LOCAL_LLM_TIMEOUT", "30"))
BASH_DEFAULT_TIMEOUT_MS = int(os.environ.get("BASH_DEFAULT_TIMEOUT_MS", "120000"))
BASH_MAX_TIMEOUT_MS = max(int(os.environ.get("BASH_MAX_TIMEOUT_MS", "600000")), BASH_DEFAULT_TIMEOUT_MS)

def loki_url() -> str:
    if "SMART_BASH_LOKI_URL" in os.environ:
        return os.environ["SMART_BASH_LOKI_URL"]
    config_dir = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    try:
        return (config_dir / "smart-bash" / "loki-url").read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""
    except OSError as error:
        print(f"Smart Bash telemetry configuration unavailable: {type(error).__name__}", file=sys.stderr)
        return ""

SMART_BASH_LOKI_URL = loki_url()

def record_usage(original: str, returned: str, mode: str) -> None:
    if not SMART_BASH_LOKI_URL:
        return
    original_bytes = len(original.encode("utf-8"))
    returned_bytes = len(returned.encode("utf-8"))
    event = {
        "mode": mode,
        "original_bytes": original_bytes,
        "returned_bytes": returned_bytes,
        "original_tokens_estimate": original_bytes / 4,
        "returned_tokens_estimate": returned_bytes / 4,
        "saved_tokens_estimate": (original_bytes - returned_bytes) / 4,
    }
    payload = json.dumps({
        "streams": [{
            "stream": {"app": "smart-bash"},
            "values": [[str(time.time_ns()), json.dumps(event)]],
        }]
    }).encode("utf-8")
    try:
        request = urllib.request.Request(
            SMART_BASH_LOKI_URL.rstrip("/") + "/loki/api/v1/push",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=1):
            pass
    except (OSError, ValueError) as error:
        print(f"Smart Bash telemetry unavailable: {type(error).__name__}", file=sys.stderr)

def summarize_with_local_llm(command: str, raw_output: str) -> str:
    if len(raw_output) < 300:
        return raw_output
    
    payload = json.dumps({
        "model": LOCAL_LLM_MODEL,
        "messages": [
            {"role": "system", "content": "You are a local token-optimization agent. Summarize the terminal output concisely. Highlight key results, errors, file paths, or metrics. Keep it under 200 words."},
            {"role": "user", "content": f"Command executed: `{command}`\n\nRaw Output:\n{raw_output[:8000]}"}
        ],
        "temperature": 0.1,
        "max_tokens": 300
    }).encode('utf-8')
    
    headers = {"Content-Type": "application/json"}
    if LOCAL_API_KEY:
        headers["Authorization"] = f"Bearer {LOCAL_API_KEY}"
    req = urllib.request.Request(LOCAL_LLM_URL, data=payload, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=LOCAL_LLM_TIMEOUT) as response:
            result = json.loads(response.read().decode('utf-8'))
            summary = result["choices"][0]["message"]["content"]
            if not isinstance(summary, str) or not summary.strip():
                raise ValueError("empty summary")
            
            reduction = int((1 - (len(summary) / len(raw_output))) * 100)
            return f"{summary}\n\n[⚡ Local MCP: Reduced output from {len(raw_output)} to {len(summary)} chars ({reduction}% saved)]"
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        return f"[Output Truncated - Local LLM Summary Unavailable: {type(error).__name__}]\n{raw_output[:1000]}"

@mcp.tool()
def execute_local_bash(command: str, cwd: str = ".", return_raw: bool = False, timeout: int = BASH_DEFAULT_TIMEOUT_MS) -> str:
    """
    Executes a shell command on the local machine.
    By default, it returns a token-optimized summary.
    Set return_raw=True ONLY when you need exact, unedited output (e.g., exact timestamps, file sizes, or tabular data).
    timeout is in milliseconds (default 120000, capped at 600000); raise it for long-running commands such as builds or installs.
    """
    timeout_s = min(max(timeout, 1), BASH_MAX_TIMEOUT_MS) / 1000
    try:
        result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout_s)
        combined_output = (result.stdout + "\n" + result.stderr).strip()
        status = f"ERROR: Command exited with status {result.returncode}.\n" if result.returncode else ""
        
        if return_raw:
            output = f"{status}[Raw Output Requested]\n{combined_output}"
            record_usage(output, output, "raw")
            return output
            
        output = status + summarize_with_local_llm(command, combined_output)
        mode = "short" if len(combined_output) < 300 else (
            "fallback" if output.startswith(status + "[Output Truncated - Local LLM Summary Unavailable:") else "summary"
        )
        record_usage(status + combined_output, output, mode)
        return output
    except subprocess.TimeoutExpired:
        error_msg = f"ERROR: Command timed out after {timeout_s:g} seconds."
        return error_msg if return_raw else summarize_with_local_llm(command, error_msg)
    except OSError as e:
        error_msg = f"ERROR: {str(e)}"
        return error_msg if return_raw else summarize_with_local_llm(command, error_msg)

if __name__ == "__main__":
    mcp.run()