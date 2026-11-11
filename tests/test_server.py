import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402


def fake_response(content):
    body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
    resp = mock.MagicMock()
    resp.read.return_value = body
    resp.__enter__.return_value = resp
    return resp


class SummarizeTests(unittest.TestCase):
    def test_short_output_skips_llm(self):
        with mock.patch("server.urllib.request.urlopen") as urlopen:
            self.assertEqual(server.summarize_with_local_llm("ls", "a" * 299), "a" * 299)
            urlopen.assert_not_called()

    def test_long_output_is_summarized_with_savings_footer(self):
        with mock.patch("server.urllib.request.urlopen", return_value=fake_response("short summary")):
            out = server.summarize_with_local_llm("ls", "a" * 1000)
        self.assertTrue(out.startswith("short summary"))
        self.assertIn("Reduced output from 1000 to 13 chars", out)

    def test_request_shape_auth_and_timeout(self):
        with mock.patch("server.LOCAL_API_KEY", "test-token"):
            with mock.patch("server.urllib.request.urlopen", return_value=fake_response("s")) as urlopen:
                server.summarize_with_local_llm("cmd", "a" * 10000)
        req = urlopen.call_args.args[0]
        self.assertEqual(urlopen.call_args.kwargs["timeout"], server.LOCAL_LLM_TIMEOUT)
        self.assertEqual(req.get_header("Authorization"), "Bearer test-token")
        payload = json.loads(req.data)
        self.assertIn("cmd", payload["messages"][1]["content"])
        self.assertNotIn("a" * 8001, payload["messages"][1]["content"])

    def test_llm_failure_falls_back_to_truncated_raw(self):
        with mock.patch("server.urllib.request.urlopen", side_effect=TimeoutError()):
            out = server.summarize_with_local_llm("ls", "#" * 5000)
        self.assertTrue(out.startswith("[Output Truncated - Local LLM Summary Unavailable: TimeoutError]"))
        self.assertEqual(out.count("#"), 1000)

    def test_no_key_omits_authorization(self):
        with mock.patch("server.LOCAL_API_KEY", ""):
            with mock.patch("server.urllib.request.urlopen", return_value=fake_response("s")) as urlopen:
                server.summarize_with_local_llm("cmd", "a" * 300)
        self.assertIsNone(urlopen.call_args.args[0].get_header("Authorization"))

    def test_invalid_summary_is_reported_as_unavailable(self):
        with mock.patch("server.urllib.request.urlopen", return_value=fake_response(None)):
            out = server.summarize_with_local_llm("cmd", "a" * 300)
        self.assertIn("Summary Unavailable: ValueError", out)


class ExecuteTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("server.summarize_with_local_llm", side_effect=lambda cmd, out: f"SUMMARY:{out}")
        self.summarize = patcher.start()
        self.addCleanup(patcher.stop)

    def test_default_summarizes(self):
        self.assertEqual(server.execute_local_bash("echo hi"), "SUMMARY:hi")

    def test_return_raw_bypasses_llm(self):
        out = server.execute_local_bash("echo hi", return_raw=True)
        self.assertEqual(out, "[Raw Output Requested]\nhi")
        self.summarize.assert_not_called()

    def test_stdout_and_stderr_combined(self):
        out = server.execute_local_bash("echo out; echo err >&2", return_raw=True)
        self.assertIn("out", out)
        self.assertIn("err", out)

    def test_nonzero_exit_is_reported_in_both_modes(self):
        for raw in (False, True):
            with self.subTest(raw=raw):
                out = server.execute_local_bash("echo failed >&2; exit 7", return_raw=raw)
                self.assertTrue(out.startswith("ERROR: Command exited with status 7.\n"))
                self.assertIn("failed", out)

    def test_cwd_is_respected(self):
        with tempfile.TemporaryDirectory() as d:
            out = server.execute_local_bash("pwd", cwd=d, return_raw=True)
            self.assertIn(os.path.realpath(d), os.path.realpath(out.split("\n", 1)[1]))

    def test_command_timeout_default_message(self):
        with mock.patch("server.subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("x", 120)) as run:
            out = server.execute_local_bash("sleep 99", return_raw=True)
        self.assertEqual(run.call_args.kwargs["timeout"], 120)
        self.assertEqual(out, "ERROR: Command timed out after 120 seconds.")

    def test_timeout_is_capped_at_max(self):
        with mock.patch("server.subprocess.run") as run:
            run.return_value = mock.Mock(stdout="", stderr="", returncode=0)
            server.execute_local_bash("x", timeout=99_999_999, return_raw=True)
        self.assertEqual(run.call_args.kwargs["timeout"], server.BASH_MAX_TIMEOUT_MS / 1000)

    def test_custom_timeout_is_applied(self):
        out = server.execute_local_bash("sleep 3", timeout=1000, return_raw=True)
        self.assertEqual(out, "ERROR: Command timed out after 1 seconds.")

    def test_custom_timeout_allows_slower_command(self):
        out = server.execute_local_bash("sleep 1; echo done", timeout=5000, return_raw=True)
        self.assertTrue(out.endswith("done"))

    def test_invalid_cwd_returns_error(self):
        out = server.execute_local_bash("ls", cwd="/nonexistent-dir", return_raw=True)
        self.assertTrue(out.startswith("ERROR:"))

    def test_timeout_error_is_summarized_when_not_raw(self):
        server.execute_local_bash("sleep 3", timeout=1000)
        self.summarize.assert_called_once()
        self.assertIn("timed out after 1 seconds", self.summarize.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
