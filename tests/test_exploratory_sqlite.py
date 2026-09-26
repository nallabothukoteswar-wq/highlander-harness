"""Independent schedule checks for the SQLite exploratory study."""
import unittest

from analysis.exploratory_sqlite import database, submit


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
        old = submit(db, 'C3', 'feed', 'old-late', 0, 1, 'former', 2)
        self.assertEqual(old['outcome'], 'rejected_fence')
        db.close()

    def test_remote_fence_late_window_and_after_write(self):
        db = database()
        submit(db, 'C3r', 'feed', 'old-initial', 1, 1, 'current', 1)
        late = submit(db, 'C3r', 'feed', 'old-late', 0, 1, 'former', 2,
                      first_write_after_grant=True)
        self.assertEqual((late['late_accept'], late['epoch_regression']), (1, 0))
        submit(db, 'C3r', 'feed', 'new', 2, 2, 'current', 2)
        too_late = submit(db, 'C3r', 'feed', 'old-after', 0, 1, 'former', 2)
        self.assertEqual(too_late['outcome'], 'rejected_remote_epoch')
        db.close()

    def test_replay_returns_original_response(self):
        db = database()
        first = submit(db, 'C4', 'feed', 'same', 1, 1, 'current', 1)
        again = submit(db, 'C4', 'feed', 'same', 1, 1, 'current', 1)
        self.assertEqual(again['outcome'], 'replayed')
        self.assertEqual(first['response'], again['response'])
        db.close()


if __name__ == '__main__':
    unittest.main()
