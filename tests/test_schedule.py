"""When questions come back."""

from __future__ import annotations

import datetime as dt
import unittest

import support  # noqa: F401  (puts the library on the path)

from own_guide import schedule

DAY0 = dt.date(2026, 10, 26)


def day(n: int) -> dt.date:
    return DAY0 + dt.timedelta(days=n)


class LadderTest(unittest.TestCase):
    def test_right_first_time_comes_back_once_in_two_weeks_then_done(self) -> None:
        q = schedule.new_question(1, DAY0, kind="why", tests="t", answer="a")
        schedule.apply_result(q, "right", DAY0)
        self.assertEqual((q["status"], q["next_due"]), ("check", day(14).isoformat()))
        schedule.apply_result(q, "right", day(14))
        self.assertEqual(q["status"], "done")
        self.assertIsNone(q["next_due"])

    def test_missed_question_climbs_1_3_7_21_then_done(self) -> None:
        q = schedule.new_question(1, DAY0)
        schedule.apply_result(q, "miss", DAY0)
        self.assertEqual(q["next_due"], day(1).isoformat())
        when = day(1)
        for gap in (3, 7, 21):
            schedule.apply_result(q, "right", when)
            self.assertEqual(q["next_due"], (when + dt.timedelta(days=gap)).isoformat())
            when += dt.timedelta(days=gap)
        schedule.apply_result(q, "right", when)
        self.assertEqual(q["status"], "done")

    def test_a_miss_anywhere_restarts_at_one_day(self) -> None:
        q = schedule.new_question(1, DAY0)
        schedule.apply_result(q, "miss", DAY0)
        schedule.apply_result(q, "right", day(1))
        schedule.apply_result(q, "right", day(4))
        schedule.apply_result(q, "miss", day(11))
        self.assertEqual((q["step"], q["next_due"], q["misses"]), (0, day(12).isoformat(), 2))

    def test_not_sure_counts_as_a_miss(self) -> None:
        q = schedule.new_question(1, DAY0)
        schedule.apply_result(q, "not-sure", DAY0)
        self.assertEqual((q["status"], q["next_due"]), ("learning", day(1).isoformat()))

    def test_check_question_missed_goes_onto_the_ladder(self) -> None:
        q = schedule.new_question(1, DAY0)
        schedule.apply_result(q, "right", DAY0)
        schedule.apply_result(q, "miss", day(14))
        self.assertEqual((q["status"], q["next_due"]), ("learning", day(15).isoformat()))

    def test_bad_result_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            schedule.apply_result(schedule.new_question(1, DAY0), "maybe", DAY0)


class DueTest(unittest.TestCase):
    def _q(self, qid: int, due: dt.date, misses: int) -> dict:
        q = schedule.new_question(qid, DAY0)
        q.update(status="learning", step=0, next_due=due.isoformat(), misses=misses)
        return q

    def test_oldest_first_then_most_missed_and_capped(self) -> None:
        questions = [
            self._q(1, day(3), 0),
            self._q(2, day(1), 1),
            self._q(3, day(1), 4),
            self._q(4, day(9), 9),  # not due yet on day 5
        ]
        picked = schedule.due(questions, day(5), limit=2)
        self.assertEqual([q["id"] for q in picked], ["q3", "q2"])
        self.assertEqual(schedule.due_count(questions, day(5)), 3)

    def test_done_questions_never_come_back(self) -> None:
        q = schedule.new_question(1, DAY0)
        q.update(status="done", next_due=None)
        self.assertEqual(schedule.due([q], day(100), limit=5), [])


if __name__ == "__main__":
    unittest.main()
