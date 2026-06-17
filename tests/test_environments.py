"""Тесты инструментов доменов EDU/MFC (возраст, места, отмена, неизвестная справка)."""
import unittest
from ruservicebench.environments import Environment


class TestEdu(unittest.TestCase):
    def _env(self, init=None):
        env = Environment(["edu"])
        env.reset(init)
        return env

    def test_enroll_happy_path_records_enrollment(self):
        env = self._env()
        r = env.call_tool("edu_enroll", {"child": "Аня", "circle_id": "art"})
        self.assertTrue(r["ok"])
        self.assertEqual(env.composite_state()["edu"]["enrollments"][0]["circle_id"], "art")

    def test_enroll_age_out_of_range_refused_no_mutation(self):
        env = self._env()
        r = env.call_tool("edu_enroll", {"child": "Дима", "circle_id": "robotics", "age": 5})
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "age_out_of_range")
        self.assertEqual(env.composite_state()["edu"]["enrollments"], [])

    def test_enroll_no_slots_refused(self):
        env = self._env()
        r = env.call_tool("edu_enroll", {"child": "Оля", "circle_id": "swimming"})
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "no_slots")

    def test_cancel_enrollment_removes_it(self):
        env = self._env({"edu": {"enrollments": [{"child": "Костя", "circle_id": "art"}]}})
        r = env.call_tool("edu_cancel_enrollment", {"child": "Костя", "circle_id": "art"})
        self.assertTrue(r["ok"])
        self.assertEqual(env.composite_state()["edu"]["enrollments"], [])


class TestMfc(unittest.TestCase):
    def _env(self):
        env = Environment(["mfc"])
        env.reset(None)
        return env

    def test_request_known_certificate(self):
        r = self._env().call_tool("mfc_request_certificate", {"cert_type": "income"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["type"], "income")

    def test_request_unknown_certificate_refused_no_mutation(self):
        env = self._env()
        r = env.call_tool("mfc_request_certificate", {"cert_type": "nonexistent"})
        self.assertFalse(r["ok"])
        self.assertEqual(env.composite_state()["mfc"]["requests"], [])

    def test_unknown_tool_raises_keyerror(self):
        with self.assertRaises(KeyError):
            self._env().call_tool("does_not_exist", {})


class TestTransport(unittest.TestCase):
    def _env(self, init=None):
        env = Environment(["transport"])
        env.reset(init)
        return env

    def test_pay_fine_happy_path(self):
        env = self._env()
        r = env.call_tool("transport_pay_fine", {"fine_id": "f-2026-001"})
        self.assertTrue(r["ok"])
        self.assertTrue(env.composite_state()["transport"]["fines"][0]["paid"])

    def test_pay_already_paid_fine_refused(self):
        env = self._env({"transport": {"fines": [{"id": "f-2026-001", "amount": 500, "paid": True}]}})
        r = env.call_tool("transport_pay_fine", {"fine_id": "f-2026-001"})
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "already_paid")

    def test_pay_unknown_fine_refused(self):
        r = self._env().call_tool("transport_pay_fine", {"fine_id": "nope"})
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "fine_not_found")

    def test_apply_parking_permit(self):
        env = self._env()
        r = env.call_tool("transport_apply_parking_permit", {"zone": "Тверская", "plate": "А123ВС777"})
        self.assertTrue(r["ok"])
        self.assertEqual(env.composite_state()["transport"]["permits"][0]["zone"], "Тверская")


if __name__ == "__main__":
    unittest.main()
