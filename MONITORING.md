# Local monitoring

Smart Bash can send anonymous numeric usage measurements to a local Grafana/Loki stack. The event contains output byte counts, rough token estimates, and the mode (`raw`, `short`, `summary`, or `fallback`); it does not contain commands or their output.

Token estimates use UTF-8 bytes divided by four. They are not tokenizer counts or actual agent context usage. Context-window panels compare estimated output reduction against a configurable context size; they do not measure context occupancy, full sessions, or model-request tokens.

## Start with Docker Compose

From the repository root, start Docker Desktop or another Docker Engine with Compose:

```sh
docker compose -f monitoring/compose.yaml up -d
```

The stack exposes Loki on `127.0.0.1:3100` and Grafana on `127.0.0.1:3300`. The dashboard is at <http://127.0.0.1:3300/d/smart-bash-savings>. Docker Compose creates named volumes for Loki and Grafana data; these survive container restarts and `docker compose down`.

The same Compose file can be used with Podman if a Compose provider is installed:

```sh
podman compose -f monitoring/compose.yaml up -d
```

On macOS, make sure the Podman machine is running first.

Both services are unauthenticated and bound to loopback for local use only. Do not change the port bindings to expose them to a network without adding appropriate access controls.

## Enable telemetry

Create a local opt-in file; this does not require changing either MCP client's configuration:

```sh
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/smart-bash"
printf '%s\n' 'http://127.0.0.1:3100' > "${XDG_CONFIG_HOME:-$HOME/.config}/smart-bash/loki-url"
```

Alternatively, set `SMART_BASH_LOKI_URL` in the MCP server environment. This variable overrides the file; setting it to an empty string disables telemetry. Restart or reconnect the MCP server after changing the setting.

Check service health:

```sh
curl -fsS http://127.0.0.1:3100/ready
curl -fsS http://127.0.0.1:3300/api/health
```

If Loki is unavailable, command execution continues and a warning is written to stderr; missed measurements are not retried.

## Read the report

The dashboard offers 1-day, 7-day, and 30-day ranges. It starts at 7 days. Metrics begin only after telemetry is enabled and the MCP server reconnects; prior command history cannot be reconstructed. Loki data is retained in its named volume unless that volume is deleted.

Total and per-interval savings percentages use `100 × total saved / total original`, weighted by output size. Percentages are undefined when original output is zero. The main chart shows estimated saved tokens per client and interval on a logarithmic scale, so large outputs do not flatten smaller values. Zero values cannot be shown on a log scale; gaps are connected for readability. It is not a cumulative token count or continuous observation. The percentage chart leaves idle buckets empty.

Set the **Context window size (tokens)** textbox to the model's context limit. The panels show average estimated output reduction per call as a percentage of that configured size, and cumulative reductions as context-window equivalents over the selected period. These are comparisons, not counts of sessions or context windows actually saved.

## Client attribution

Add `SMART_BASH_CLIENT` to each MCP server's environment: use `claude` for Claude Code and `copilot` for Copilot. Restart the MCP servers to load it. The dashboard's **Client** filter selects these labels. New events without a label use `unknown`; older events without a client field are shown as **Unknown** in dashboard queries without changing the stored logs. Labels are explicit, not inferred. Copilot CLI and desktop share their label; session-level attribution is not implemented.

## Edit charts

Anonymous access is read-only. Sign in at <http://127.0.0.1:3300/login> with your Grafana account (Editor or Admin) to edit and save charts. A fresh Grafana installation initially uses `admin` / `admin` and prompts for a new password; existing installations retain their credentials.

Provisioned dashboards allow UI saves, but changes are stored in Grafana's database, not the repository JSON. Updating the provisioned JSON can overwrite those edits. For a personal dashboard, use **Save as copy**; export its JSON if you want to contribute it back. The default dashboard and your copies persist in the Grafana volume.

## Stop and remove

Stop containers while retaining monitoring data:

```sh
docker compose -f monitoring/compose.yaml down
```

Start them again with `docker compose -f monitoring/compose.yaml up -d`. To permanently delete the stored Grafana and Loki data as well, run `docker compose -f monitoring/compose.yaml down --volumes`; this removes the history.
