import frappe
from frappe.tests import IntegrationTestCase

from buzz.events.doctype.event_topic.topic_page import TopicPage


class TestTopicPage(IntegrationTestCase):
	def page(self) -> TopicPage:
		return TopicPage(
			frappe._dict(name="no-such-topic", route="topics/no-such-topic", short_description=None)
		)

	def test_a_topic_has_no_community_events_to_look_up(self):
		self.assertEqual(self.page().external_events, [])

	def test_the_page_builds_without_a_team(self):
		context = self.page().as_context()
		self.assertEqual((context["upcoming_days"], context["past_days"]), ([], []))
