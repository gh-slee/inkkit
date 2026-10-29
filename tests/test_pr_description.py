"""PR format checks use synthetic descriptions; no GitHub requests or reader data."""
import contextlib
import io
import json
import re
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check_pr_description as pr_format

TEMPLATE = pr_format.TEMPLATE.read_text(encoding='utf-8')


def valid_body():
    return '''## Change Summary

A synthetic change makes the sample behavior explicit.

- Add the first meaningful example behavior.
- Preserve the second documented behavior.

## Files Changed

- `README.md`: Explain the synthetic change.

## Testing & Evidence

### Local Verification

- NOT RUN: Synthetic fixture only.

### CI Verification

- NOT RUN: No remote run exists for this fixture.

### Independent QA / Architecture Review

- NOT RUN: No independent review was requested for this fixture.

### Required Pre-PR Validation

- NOT RUN: Synthetic fixture; no publication audit is claimed.
'''


class PrDescriptionTests(unittest.TestCase):
    def test_small_complete_body_and_all_explicit_result_states_are_valid(self):
        for status in ('PASS', 'FAIL', 'NOT RUN'):
            with self.subTest(status=status):
                self.assertEqual(pr_format.validate(valid_body().replace('NOT RUN', status), TEMPLATE), [])

    def test_pending_is_a_ci_status_not_a_completed_local_check(self):
        body = valid_body().replace('- NOT RUN: No remote run exists for this fixture.', '- PENDING: Synthetic CI run is in progress.')
        self.assertEqual(pr_format.validate(body, TEMPLATE), [])
        self.assertTrue(pr_format.validate(valid_body().replace('- NOT RUN: Synthetic fixture only.', '- PENDING: Local check is still running.'), TEMPLATE))

    def test_plain_prose_and_missing_duplicate_or_reordered_required_sections_fail(self):
        good = valid_body()
        cases = [
            'A long narrative with no review structure.',
            good.replace('## Files Changed', '## Arbitrary Inventory'),
            good + '\n## Change Summary\nA duplicated section.\n',
            good[good.index('## Files Changed'):] + good[:good.index('## Files Changed')],
        ]
        for body in cases:
            with self.subTest(body=body[:60]):
                self.assertTrue(pr_format.validate(body, TEMPLATE))

    def test_summary_sentence_and_two_to_six_bullets_are_required(self):
        good = valid_body()
        for body in (good.replace('A synthetic change makes the sample behavior explicit.\n\n', ''),
                     good.replace('- Preserve the second documented behavior.\n', ''),
                     good.replace('## Files Changed', '- Extra.\n' * 5 + '\n## Files Changed')):
            self.assertTrue(pr_format.validate(body, TEMPLATE))

    def test_file_inventory_needs_formatted_paths_and_explanations(self):
        for row in ('- README.md: Changed.', '- `README.md`', '- No paths listed.'):
            self.assertTrue(pr_format.validate(valid_body().replace('- `README.md`: Explain the synthetic change.', row), TEMPLATE))
        body = valid_body().replace('- `README.md`:', '- `docs/`, `scripts/example.py`:')
        self.assertEqual(pr_format.validate(body, TEMPLATE), [])

    def test_evidence_categories_and_statuses_cannot_be_collapsed_into_prose(self):
        good = valid_body()
        for body in (good.replace('### CI Verification\n', ''),
                     good.replace('### Independent QA / Architecture Review', '### Developer Self Review'),
                     good.replace('- NOT RUN: Synthetic fixture only.', 'All checks look good.'),
                     good.replace('- NOT RUN: Synthetic fixture only.', '- <STATUS>: Add results later.')):
            self.assertTrue(pr_format.validate(body, TEMPLATE))

    def test_optional_sections_are_ordered_and_empty_placeholders_fail(self):
        self.assertEqual(pr_format.validate(valid_body() + '\n## Reviewer Focus\n\n- Review the changed behavior.\n', TEMPLATE), [])
        self.assertTrue(pr_format.validate(valid_body() + '\n## Screenshots / Visual Evidence\n\n', TEMPLATE))
        body = valid_body() + '\n## Reviewer Focus\n\n- Review behavior.\n\n## Behavior & Compatibility\n\n- Existing input remains accepted.\n'
        self.assertTrue(pr_format.validate(body, TEMPLATE))

    def test_fenced_or_commented_fake_headers_do_not_satisfy_the_format(self):
        good = valid_body()
        for body in ('```markdown\n' + good + '\n```', '<!--\n' + good + '\n-->', '<!--\n' + good):
            self.assertTrue(pr_format.validate(body, TEMPLATE))
        self.assertEqual(pr_format.validate(good + '\n```markdown\n## Unrelated Example\n```\n', TEMPLATE), [])

    def test_template_is_the_format_authority(self):
        changed = TEMPLATE.replace('Change Summary', 'Outcome Summary')
        self.assertEqual(pr_format.validate(valid_body().replace('Change Summary', 'Outcome Summary'), changed), [])
        with self.assertRaises(ValueError):
            pr_format.validate(valid_body(), '# Incomplete template')
        with self.assertRaises(ValueError):
            pr_format.validate(valid_body(), TEMPLATE.replace('### CI Verification', '### Local Verification'))
        self.assertTrue(pr_format.validate(TEMPLATE, TEMPLATE))

    def test_format_does_not_pretend_to_prove_factual_claims(self):
        # A shape check cannot authenticate a CI claim; human evidence review is separate.
        body = valid_body().replace('- NOT RUN: No remote run exists for this fixture.', '- PASS: A synthetic claim without a real CI run.')
        self.assertEqual(pr_format.validate(body, TEMPLATE), [])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'body.md';path.write_text(body)
            result = pr_format.check(path)
            self.assertIn('no proof of factual accuracy', result['limitations'])

    def test_cli_distinguishes_valid_invalid_and_unreadable_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'body.md'
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pr_format.main(['--body-file', str(path)]), 2)
                path.write_text('Unstructured prose.')
                self.assertEqual(pr_format.main(['--body-file', str(path)]), 1)
                path.write_text(valid_body())
                self.assertEqual(pr_format.main(['--body-file', str(path)]), 0)


    def test_saved_body_uses_existing_privacy_patterns_without_echoing_secrets(self):
        secret = 'ghp_' + 'X' * 36
        body = valid_body() + '\n' + secret
        result = pr_format.check_body(body)
        self.assertFalse(result['passed'])
        self.assertTrue(result['privacy_violations'])
        self.assertNotIn(secret, json.dumps(result))
        private_path = '/Users/' + 'synthetic-user/private-note'
        self.assertFalse(pr_format.check_body(valid_body() + '\n' + private_path)['passed'])

    def test_pull_request_events_validate_the_current_body_and_explicit_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'event.json'
            for action in ('opened', 'reopened', 'synchronize', 'edited'):
                path.write_text(json.dumps({'action': action, 'pull_request': {'body': valid_body()}}))
                self.assertTrue(pr_format.check_event(path)['passed'])
            for body in (None, '', 'Unstructured prose'):
                path.write_text(json.dumps({'pull_request': {'body': body}}))
                self.assertFalse(pr_format.check_event(path)['passed'])

    def test_event_cli_fails_closed_on_malformed_or_non_pr_events(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'event.json'
            for value in ('{broken', '[]', '{}', '{"pull_request": 7}', '{"pull_request": {"body": 7}}'):
                path.write_text(value)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(pr_format.main(['--event-file', str(path)]), 2)

    def test_event_body_is_data_and_never_shell_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / 'must-not-exist'
            body = valid_body() + '\n`$(touch ' + str(marker) + ')`\n'
            path = root / 'event.json'
            path.write_text(json.dumps({'pull_request': {'body': body}}))
            result = subprocess.run([sys.executable, str(pr_format.TEMPLATE.parents[1] / 'scripts/check_pr_description.py'),
                                     '--event-file', str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)['passed'])
            self.assertFalse(marker.exists())
            self.assertNotIn(body, result.stdout)

    def test_separate_readonly_workflow_covers_description_updates(self):
        root = pr_format.TEMPLATE.parents[1]
        workflow = (root / '.github/workflows/pr-description.yml').read_text()
        self.assertIn('types: [opened, reopened, synchronize, edited]', workflow)
        self.assertIn('contents: read', workflow)
        self.assertIn('persist-credentials: false', workflow)
        self.assertIn('--event-file "$GITHUB_EVENT_PATH"', workflow)
        self.assertNotIn('pull_request_target', workflow)
        self.assertNotIn('pull_request.body', workflow)
        self.assertNotIn('secrets.', workflow)
        self.assertTrue(all(re.fullmatch(r'[^@]+@[0-9a-f]{40}', action)
                            for action in re.findall(r'- uses: (\S+)', workflow)))
        # Description edits must not introduce skipped replacement unit checks.
        main = (root / '.github/workflows/tests.yml').read_text()
        self.assertNotIn('edited', main)


if __name__ == '__main__':
    unittest.main()
