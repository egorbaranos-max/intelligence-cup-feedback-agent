"""The human-review view must preserve raw evidence and escape its HTML."""
import contextlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.render_live_report import main, render_card


class ParsedReport(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.ids = set()
        self.links = []
        self.blockquotes = []
        self.quote = None

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        if tag == 'a':
            self.links.append(attrs.get('href', ''))
        if tag == 'blockquote':
            self.quote = ''
        if any(key.startswith('on') for key in attrs):
            raise AssertionError('Unescaped event attribute in report')

    def handle_data(self, data):
        if self.quote is not None:
            self.quote += data

    def handle_endtag(self, tag):
        if tag == 'blockquote':
            self.blockquotes.append(self.quote)
            self.quote = None


class LiveReportTests(unittest.TestCase):
    def test_exact_quote_safe_anchor_and_report_only_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            unsafe = '<script>alert("x")</script><img src=x onerror="bad"> & Ия'
            source_id = 'source #"<img src=x onerror="bad">'
            quote = 'Первая строка\n  ' + unsafe
            source = {'id': source_id, 'origin': 'synthetic', 'text': 'Полный контекст\n' + quote + '\nКонец'}
            card = {'title': unsafe, 'recurring': True, 'raw_sources': unsafe,
                    'independent_episodes': 1, 'known_customers': 1,
                    'evidence': [{'source_id': source_id, 'quote': quote}]}
            files = {
                'inputs.jsonl': json.dumps(source, ensure_ascii=False) + '\n',
                'manifest.json': json.dumps({'model': {'model_id': unsafe, 'revision': 'fixture'},
                    'valid_extractions': unsafe, 'delivered_local_cards': 1,
                    'elapsed_seconds': 1.0, 'as_of': 'fixture'}),
                'results.jsonl': json.dumps({'source_id': source_id, 'extraction_call': 'call-1',
                    'extraction': {'ok': True, 'errors': [], 'value': {'status': 'ok', 'intents': []}}}) + '\n',
                'calls.jsonl': json.dumps({'call_id': 'call-1', 'raw_response': unsafe}) + '\n',
                'cards.json': json.dumps([card], ensure_ascii=False),
            }
            for name, value in files.items():
                (run / name).write_text(value, encoding='utf-8')
            before = {name: (run / name).read_bytes() for name in files}
            command = ['render_live_report.py', '--run', str(run), '--inputs', str(run / 'inputs.jsonl')]
            with patch('sys.argv', command), contextlib.redirect_stdout(io.StringIO()):
                main()
                with self.assertRaises(FileExistsError):
                    main()
            with patch('sys.argv', [*command, '--replace-report']), contextlib.redirect_stdout(io.StringIO()):
                main()
            self.assertEqual(before, {name: (run / name).read_bytes() for name in files})
            html = (run / 'report.html').read_text(encoding='utf-8')
            parsed = ParsedReport()
            parsed.feed(html)
            self.assertNotIn('script', parsed.tags)
            self.assertNotIn('img', parsed.tags)
            self.assertEqual(parsed.blockquotes, [quote])
            self.assertIn('#source-1', parsed.links)
            self.assertTrue(all(link[1:] in parsed.ids for link in parsed.links if link.startswith('#')))
            self.assertIn('Черновик модели — смысл и объединение ещё не одобрены человеком', html)
            self.assertIn('source_id:', html)

    def test_unavailable_source_is_explicit_and_does_not_get_a_broken_link(self):
        card = {'title': 'fixture', 'recurring': False, 'raw_sources': 1,
                'independent_episodes': 1, 'known_customers': 1,
                'evidence': [{'source_id': 'missing', 'quote': 'Recorded quote'}]}
        html = render_card(card, {})
        self.assertIn('Полного источника нет в этом отчете', html)
        self.assertNotIn('href=', html)
        self.assertIn('Recorded quote', html)


if __name__ == '__main__':
    unittest.main()
