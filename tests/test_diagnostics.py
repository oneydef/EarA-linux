import io
import json
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from eara import diagnostics, operations


class TimingTests(unittest.TestCase):
    def test_disabled_has_no_output_or_clock_reads(self):
        result = object()
        with patch.dict("os.environ", {"EARA_TRACE": "0"}), \
                patch.object(diagnostics.time, "monotonic") as clock, \
                redirect_stderr(io.StringIO()) as output:
            self.assertIs(diagnostics.timed("test")(lambda: result)(), result)
        clock.assert_not_called()
        self.assertEqual(output.getvalue(), "")

    def test_nested_spans_duration_and_no_payload_or_identity(self):
        @diagnostics.timed("child")
        def child(secret):
            return secret

        @diagnostics.timed("parent")
        def parent(secret):
            return child(secret)

        with patch.dict("os.environ", {"EARA_TRACE": "1"}), \
                patch.object(diagnostics.time, "monotonic", side_effect=[1, 2, 3, 5]), \
                redirect_stderr(io.StringIO()) as output:
            self.assertEqual(parent("private-device-data"), "private-device-data")
        child_event, parent_event = map(json.loads, output.getvalue().splitlines())
        self.assertEqual(child_event["parent"], parent_event["span"])
        self.assertIsNone(parent_event["parent"])
        self.assertEqual(child_event["elapsed_ms"], 1000)
        self.assertEqual(parent_event["elapsed_ms"], 4000)
        self.assertNotIn("private-device-data", output.getvalue())

    def test_exception_identity_outcome_and_context_restored(self):
        for error, outcome in ((operations.Cancelled("private"), "cancelled"),
                               (TimeoutError("private"), "timeout"),
                               (OSError("private"), "error")):
            with self.subTest(outcome=outcome):
                @diagnostics.timed("test")
                def fail():
                    raise error
                with patch.dict("os.environ", {"EARA_TRACE": "1"}), \
                        redirect_stderr(io.StringIO()) as output:
                    with self.assertRaises(type(error)) as caught:
                        fail()
                self.assertIs(caught.exception, error)
                self.assertIsNone(diagnostics._parent.get())
                self.assertEqual(json.loads(output.getvalue())["outcome"], outcome)
                self.assertNotIn("private", output.getvalue())

    def test_failed_results_and_missing_response_are_not_completed(self):
        for result, outcome in ((False, "unavailable"), (True, "completed"),
                                ({"ok": False}, "unavailable"),
                                ({"available": False}, "unavailable"),
                                (None, "no_response"), (b"", "completed")):
            with self.subTest(outcome=outcome), \
                    patch.dict("os.environ", {"EARA_TRACE": "1"}), \
                    redirect_stderr(io.StringIO()) as output:
                actual = diagnostics.timed("test", response=True)(lambda: result)()
                self.assertIs(actual, result)
                self.assertEqual(json.loads(output.getvalue())["outcome"], outcome)

    def test_broken_diagnostic_output_cannot_fail_command(self):
        with patch.dict("os.environ", {"EARA_TRACE": "1"}), \
                patch.object(diagnostics.sys, "stderr") as output:
            output.write.side_effect = BrokenPipeError()
            self.assertEqual(diagnostics.timed("test")(lambda: 42)(), 42)
