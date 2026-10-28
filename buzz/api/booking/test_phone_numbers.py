from frappe.tests import UnitTestCase

from buzz.api.booking.services import without_trunk_zero


class TestWithoutTrunkZero(UnitTestCase):
	def test_the_zero_after_the_country_code_goes(self):
		self.assertEqual(without_trunk_zero("+27-0735997905"), "+27-735997905")
		self.assertEqual(without_trunk_zero("+91-0735997905"), "+91-735997905")

	def test_a_clean_number_is_left_alone(self):
		self.assertEqual(without_trunk_zero("+27-735997905"), "+27-735997905")

	def test_italy_keeps_its_zero(self):
		self.assertEqual(without_trunk_zero("+39-0612345678"), "+39-0612345678")

	def test_empty_and_unseparated_values_pass_through(self):
		self.assertIsNone(without_trunk_zero(None))
		self.assertEqual(without_trunk_zero(""), "")
		self.assertEqual(without_trunk_zero("not a phone"), "not a phone")
