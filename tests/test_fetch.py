"""Exercise optional fetch boundaries without network access or credentials."""
import io
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from strc import fetch


class FetchTests(unittest.TestCase):
    def test_cache_replay_needs_no_network_or_sec_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(fetch, 'RAW', Path(folder)), patch.object(fetch.urllib.request, 'urlopen') as request:
                path = Path(folder) / 'edgar' / 'fixture'
                path.parent.mkdir()
                path.write_bytes(b'cached public fixture')
                self.assertEqual(fetch.get('https://www.sec.gov/example', name='fixture'), path.read_bytes())
                request.assert_not_called()

    def test_retry_429_persists_body_and_metadata_then_reuses_cache(self):
        url = 'https://example.org/public-fixture'
        busy = urllib.error.HTTPError(url, 429, 'busy', {}, None)
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(fetch, 'RAW', Path(folder)), patch.object(fetch.time, 'sleep'), patch.object(
                fetch.urllib.request, 'urlopen', side_effect=[busy, io.BytesIO(b'fixture')]) as request:
                self.assertEqual(fetch.get(url, 'test', 'body'), b'fixture')
                self.assertEqual(fetch.get(url, 'test', 'body'), b'fixture')
                self.assertEqual(request.call_count, 2)
                self.assertIn(url, (Path(folder) / 'test/body.meta.json').read_text())
                busy.close()

    def test_nonretryable_error_does_not_persist_success(self):
        url = 'https://example.org/public-fixture'
        denied = urllib.error.HTTPError(url, 403, 'denied', {}, None)
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(fetch, 'RAW', Path(folder)), patch.object(fetch.time, 'sleep'), patch.object(
                fetch.urllib.request, 'urlopen', side_effect=denied) as request:
                with self.assertRaises(urllib.error.HTTPError):
                    fetch.get(url, 'test', 'body')
                self.assertEqual(request.call_count, 1)
                self.assertFalse((Path(folder) / 'test/body').exists())
                denied.close()
