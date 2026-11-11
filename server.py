#!/usr/bin/env python3
import os
import subprocess
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
            return f"{status}[Raw Output Requested]\n{combined_output}"
            
        return status + summarize_with_local_llm(command, combined_output)
    except subprocess.TimeoutExpired:
        error_msg = f"ERROR: Command timed out after {timeout_s:g} seconds."
        return error_msg if return_raw else summarize_with_local_llm(command, error_msg)
    except OSError as e:
        error_msg = f"ERROR: {str(e)}"
        return error_msg if return_raw else summarize_with_local_llm(command, error_msg)

if __name__ == "__main__":
    mcp.run()