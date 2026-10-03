import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from codekit.builtin_projections import ProjectionEvent  # noqa: E402
from codekit.planner_projection import (  # noqa: E402
    PlannerOutboxCursor,
    PlannerProjectionError,
    project_planning,
)


class PlannerProjectionTests(unittest.TestCase):
    def test_states_are_orthogonal_and_brief_cannot_grant_dispatch(self):
        projection = project_planning(planning_state="APPROVED", review_state="APPROVED",
                                      publication_state="PAIR_COMPLETE", execution_state="START_UNKNOWN",
                                      currentness="CURRENT")
        brief = PlannerOutboxCursor().brief(projection)
        self.assertEqual(brief["review_state"], "APPROVED")
        self.assertEqual(brief["execution_state"], "START_UNKNOWN")
        self.assertEqual(brief["dispatch_eligibility"], "not_evaluated")
        with self.assertRaisesRegex(PlannerProjectionError, "E_PROJECTION_STATE"):
            project_planning(planning_state="APPROVED", currentness="bad")

    def test_cursor_deduplicates_and_rebuilds(self):
        cursor = PlannerOutboxCursor()
        event = ProjectionEvent(1, "planning", "published", {"id": "p1"})
        self.assertEqual(cursor.consume([event], generation=1), "APPLIED")
        self.assertEqual(cursor.consume([event], generation=1), "REPLAY")
        cursor.rebuild([{"id": "p1"}], generation=1)
        self.assertEqual(cursor.cursor, 0)
        with self.assertRaisesRegex(Exception, "E_FENCED"):
            cursor.consume([event], generation=2)

    def test_published_is_a_valid_publication_projection_state(self):
        projection = project_planning(planning_state="APPROVED", review_state="APPROVED",
                                      publication_state="PUBLISHED", execution_state="NOT_STARTED",
                                      currentness="CURRENT")
        self.assertEqual(projection.publication_state, "PUBLISHED")


if __name__ == "__main__":
    unittest.main()
