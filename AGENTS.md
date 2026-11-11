# Agent instructions

- Read `README.md` before setup or changes. Follow the user's client and installation preferences.
- Ask before changing user-level MCP configuration, installing dependencies, or starting a model server.
- Keep credentials in the user's environment or client configuration, never in the repository.
- Set up the Python environment and configure the MCP client using absolute paths as described in the README. Preserve unrelated client settings.
- Verify with the tests in the README and an MCP client connection; do not assume a running local model.
- The tool executes arbitrary shell commands. Respect client permissions and user approval, and treat model summaries as lossy, untrusted output.
