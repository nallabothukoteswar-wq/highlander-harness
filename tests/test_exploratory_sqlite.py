"""Independent schedule checks for the SQLite exploratory study."""
import unittest

from analysis.exploratory_sqlite import database, one_after_grant, one_duplicate, submit


class InterleavingChecks(unittest.TestCase):
    def test_version_check_rejects_lower_source_version_without_lease(self):
        db = database()
        submit(db, 'C1v', 'feed', 'new', 8, 0, 'current', 0)
        old = submit(db, 'C1v', 'feed', 'old', 7, 0, 'former', 0)
        self.assertEqual(old['outcome'], 'rejected_version')
        self.assertEqual(db.execute('SELECT version FROM state').fetchone()[0], 8)
        db.close()

    def test_unique_key_does_not_prevent_different_key_regression(self):
        db = database()
        submit(db, 'C1u', 'feed', 'new', 8, 1, 'current', 1)
        old = submit(db, 'C1u', 'feed', 'old', 7, 1, 'former', 1)
        self.assertEqual(old['version_regression'], 1)
        db.close()

    def test_fence_rejects_former_holder_before_successor_effect(self):
        db = database()
        submit(db, 'C3', 'feed', 'old-initial', 1, 1, 'current', 1)
        old = submit(db, 'C3', 'feed', 'old-late', 2, 1, 'former', 2)
        self.assertEqual(old['outcome'], 'rejected_fence')
        db.close()

    def test_remote_fence_late_window_and_after_write(self):
        db = database()
        submit(db, 'C3r', 'feed', 'old-initial', 1, 1, 'current', 1)
        late = submit(db, 'C3r', 'feed', 'old-late', 2, 1, 'former', 2,
                      first_write_after_grant=True)
        self.assertEqual((late['late_accept'], late['epoch_regression'],
                          late['version_regression']), (1, 0, 0))
        submit(db, 'C3r', 'feed', 'new', 3, 2, 'current', 2)
        too_late = submit(db, 'C3r', 'feed', 'old-after', 2, 1, 'former', 2)
        self.assertEqual(too_late['outcome'], 'rejected_remote_epoch')
        db.close()

    def test_remote_feed_fence_rejects_different_key_after_successor(self):
        db = database()
        submit(db, 'C3r', 'feed-A', 'old-A', 1, 1, 'current', 1)
        submit(db, 'C3r', 'feed-B', 'old-B', 1, 1, 'current', 1)
        submit(db, 'C3r', 'feed-A', 'new-A', 3, 2, 'current', 2)
        former = submit(db, 'C3r', 'feed-B', 'old-late-B', 2, 1, 'former', 2)
        self.assertEqual(former['outcome'], 'rejected_remote_epoch')
        self.assertEqual(db.execute('SELECT max_epoch FROM remote_feed').fetchone()[0], 2)
        db.close()

    def test_delayed_v2_before_successor_v3_is_not_regression(self):
        db = database()
        submit(db, 'C1v', 'feed', 'initial', 1, 1, 'current', 1)
        delayed = submit(db, 'C1v', 'feed', 'delayed', 2, 1, 'former', 2)
        self.assertEqual((delayed['outcome'], delayed['version_regression']), ('accepted', 0))
        successor = submit(db, 'C1v', 'feed', 'successor', 3, 2, 'current', 2)
        self.assertEqual(successor['outcome'], 'accepted')
        db.close()

    def test_pause_duplicates_are_former_epoch_not_current_owner(self):
        for condition in ('C1', 'C1u', 'C2', 'C2f', 'C3', 'C3r', 'C4'):
            row = one_duplicate(condition, 0)
            with self.subTest(condition=condition):
                expected = 100 if condition in ('C1', 'C2') else 0
                self.assertEqual(row.get('accepted_duplicates', 0), expected)
                if condition in ('C2f', 'C3', 'C4'):
                    self.assertEqual(row['rejected_fence'], 100)

    def test_after_grant_batch_precedes_or_follows_first_remote_write(self):
        for d, expected in ((0, 100), (1, 100), (5, 0)):
            with self.subTest(delay=d):
                remote = one_after_grant('C3r', 0, d)
                colocated = one_after_grant('C3', 0, d)
                self.assertEqual(remote['late_accept'], expected)
                self.assertEqual(remote.get('accepted', 0), expected)
                self.assertEqual(remote.get('rejected_remote_epoch', 0), 100 - expected)
                self.assertEqual(colocated['late_accept'], 0)
                self.assertEqual(colocated['rejected_fence'], 100)

    def test_replay_returns_original_response(self):
        db = database()
        first = submit(db, 'C4', 'feed', 'same', 1, 1, 'current', 1)
        again = submit(db, 'C4', 'feed', 'same', 1, 1, 'current', 1)
        self.assertEqual(again['outcome'], 'replayed')
        self.assertEqual(first['response'], again['response'])
        db.close()


if __name__ == '__main__':
    unittest.main()
