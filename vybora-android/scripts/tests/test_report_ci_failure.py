import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from report_ci_failure import ANNOTATION_CHARS, MAX_MESSAGE_CHARS, diagnostic_excerpt, escape_command, main


class FailureDiagnosticsTest(unittest.TestCase):
    def test_workflow_command_data_is_escaped(self):
        self.assertEqual(escape_command("100%\r\n::error::fake"), "100%25%0D%0A::error::fake")

    def test_gradle_failure_survives_a_long_stacktrace(self):
        text = "FAILURE: Build failed\n* What went wrong:\nMissing dependency\n"
        text += "\tat stacktrace line\n" * 1_000
        text += "BUILD FAILED\n"
        excerpt = diagnostic_excerpt(text)
        self.assertIn("Missing dependency", excerpt)
        self.assertIn("BUILD FAILED", excerpt)
        self.assertLessEqual(len(excerpt), MAX_MESSAGE_CHARS)

    def test_early_compiler_errors_are_retained(self):
        text = "e: file:///src/App.kt:12 Unresolved reference: Player\n" + "normal output\n" * 200
        self.assertIn("Unresolved reference: Player", diagnostic_excerpt(text))

    def test_large_messages_are_bounded(self):
        self.assertLessEqual(len(diagnostic_excerpt("x" * 100_000)), MAX_MESSAGE_CHARS)

    def test_missing_and_empty_logs_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            empty = Path(directory) / "empty.log"
            empty.touch()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                main([str(empty), str(Path(directory) / "missing.log")])
            self.assertEqual(output.getvalue(), "")

    def test_logs_produce_one_escaped_annotation(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "build.log"
            log.write_text("error: failed\n::warning::not a command\n", encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                main([str(log)])
            self.assertEqual(len(output.getvalue().splitlines()), 1)
            self.assertIn("::error title=CI failure details: build.log::", output.getvalue())
            self.assertIn("%0A::warning::not a command", output.getvalue())


    def test_all_gradle_failure_summaries_are_retained(self):
        text = "* What went wrong:\nFirst task failed\n* Try:\n" + "\tat stack\n" * 1_000
        text += "* What went wrong:\nSecond task failed\n* Try:\n"
        excerpt = diagnostic_excerpt(text)
        self.assertIn("First task failed", excerpt)
        self.assertIn("Second task failed", excerpt)

    def test_only_the_last_nonempty_log_is_annotated(self):
        with tempfile.TemporaryDirectory() as directory:
            sdk = Path(directory) / "sdk.log"
            build = Path(directory) / "build.log"
            sdk.write_text("SDK installation successful", encoding="utf-8")
            build.write_text("error: Kotlin compilation failed", encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                main([str(sdk), str(build)])
            self.assertNotIn("SDK installation successful", output.getvalue())
            self.assertIn("Kotlin compilation failed", output.getvalue())

    def test_annotations_are_chunked_below_the_api_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "build.log"
            log.write_text("x" * 20_000, encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                main([str(log)])
            annotations = output.getvalue().splitlines()
            self.assertGreater(len(annotations), 1)
            for annotation in annotations:
                self.assertLessEqual(len(unquote(annotation.split("::", 2)[2])), ANNOTATION_CHARS)


if __name__ == "__main__":
    unittest.main()
