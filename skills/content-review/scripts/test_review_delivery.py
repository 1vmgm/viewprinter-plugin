import json
from pathlib import Path
import tempfile
import unittest
from review_delivery import attach, lanes, sync


class DeliveryTests(unittest.TestCase):
    def test_lanes(self):
        self.assertEqual(lanes([]), ['unscheduled'])
        self.assertEqual(lanes([{'status': 'canceled'}]), ['unscheduled'])
        self.assertEqual(lanes([{'status': 'published'}, {'status': 'scheduled'}]), ['posted', 'scheduled'])
        self.assertEqual(lanes([{'status': 'failed'}]), ['attention'])
        self.assertEqual(lanes([{'status': 'unknown'}]), ['attention'])

    def test_receipts_and_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / 'history/publications'
            log.mkdir(parents=True)
            link = {'postId': 'p', 'accountId': 'a', 'itemId': 'clip', 'version': 1, 'batchId': 'b'}
            (log / '2026-10.jsonl').write_text(json.dumps(link)+'\n')
            page = root / 'page.json'
            page.write_text(json.dumps({'posts': [{'post': {'id': 'p', 'status': 'scheduled'}, 'targets': [
                {'socialAccountId': 'a', 'status': 'published', 'url': 'https://example.com/post', 'account': {'handle': '@a', 'platform': 'instagram'}}]}]}))
            output = root / 'delivery.json'
            result = sync(root, [page], output)
            self.assertEqual(result['placements'][0]['status'], 'published')
            self.assertEqual(result['placements'][0]['accountName'], '@a')
            manifest = {'delivery': {'snapshot': 'delivery.json'}, 'items': [{'id': 'clip', 'version': 1}, {'id': 'clip', 'version': 2}]}
            attach(manifest, root)
            self.assertEqual(len(manifest['items'][0]['_placements']), 1)
            self.assertEqual(manifest['items'][1]['_placements'], [])
            # Missing from a partial response is not cancellation or deletion.
            self.assertEqual(sync(root, [], output)['placements'][0]['status'], 'published')
            page.write_text(json.dumps({'posts': [{'post': {'id': 'p', 'status': 'scheduled', 'scheduledAt': '2026-10-04T13:37:00Z'}, 'targets': [{'socialAccountId': 'a', 'status': 'pending'}]}]}))
            queued = sync(root, [page], output)['placements'][0]
            self.assertEqual(queued['status'], 'scheduled')
            self.assertEqual(queued['targetStatus'], 'pending')
            self.assertEqual(lanes([queued]), ['scheduled'])


if __name__ == '__main__':
    unittest.main()
