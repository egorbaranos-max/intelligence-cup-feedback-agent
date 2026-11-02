"""Counterexamples to false recurrence and false user-authorship claims."""
from dataclasses import replace
import unittest

from demo.case_contract_demo import (
    ContractDemo, ContractError, Forbidden, Fragment, Source, prepared_output, run_demo,
)


class RecurrenceTests(unittest.TestCase):
    def setUp(self):
        self.now = 40 * 86400
        self.demo = ContractDemo(now=self.now)
        self.demo.grant("owner", {"fuel"})
        self.demo.add_topic("csv", "fuel", "Экспорт CSV")

    def ingest(self, source_id, episode, customer="a", days=1, speaker="user",
               origin="user_explicit", topic="csv"):
        source = Source(source_id, 1, "fuel", customer, episode, self.now + 86400,
                        (Fragment("body", "Хочу CSV.", speaker=speaker),),
                        self.now - days * 86400)
        self.demo.register_source(source)
        self.demo.analyze("owner", prepared_output(source, topic_id=topic, origin=origin))
        return source

    def three_episodes(self):
        for n, customer in enumerate(("a", "b", "a"), 1):
            self.ingest(f"ticket-{n}", f"episode-{n}", customer)

    def test_unknown_links_do_not_manufacture_independent_episodes(self):
        for n in range(4):
            self.ingest(f"source-{n}", None, "a" if n < 2 else "b")
        card = self.demo.card("owner", "csv")
        self.assertEqual(card["raw_sources"], 4)
        self.assertEqual(card["independent_episodes"], 0)
        self.assertEqual(card["sources_with_unknown_episode"], 4)
        with self.assertRaises(ContractError):
            self.demo.queue_card("owner", "csv")

    def test_linked_call_ticket_are_two_sources_one_episode(self):
        self.ingest("ticket-1", "episode-1", "a")
        self.ingest("call-1", "episode-1", "a")
        self.ingest("ticket-2", "episode-2", "b")
        self.assertFalse(self.demo.card("owner", "csv")["recurring"])
        with self.assertRaises(ContractError):
            self.demo.queue_card("owner", "csv")
        self.ingest("ticket-3", "episode-3", "a")
        self.assertTrue(self.demo.card("owner", "csv")["recurring"])
        self.demo.queue_card("owner", "csv")

    def test_three_episodes_of_one_customer_do_not_meet_customer_threshold(self):
        for n in range(3):
            self.ingest(str(n), str(n))
        self.assertFalse(self.demo.card("owner", "csv")["recurring"])

    def test_unknown_customer_fallback_must_be_predeclared_and_labeled(self):
        for n in range(3):
            self.ingest(str(n), str(n), customer=None)
        self.assertFalse(self.demo.card("owner", "csv")["recurring"])
        fallback = ContractDemo(now=self.now, customer_policy="episodes_only")
        fallback.grant("owner", {"fuel"})
        fallback.add_topic("csv", "fuel", "CSV")
        for source in self.demo.sources.values():
            fallback.register_source(source)
            fallback.analyze("owner", prepared_output(source))
        card = fallback.card("owner", "csv")
        self.assertTrue(card["recurring"])
        self.assertEqual(card["known_customers"], 0)
        self.assertEqual(card["customer_policy"], "episodes_only")

    def test_hidden_episode_does_not_complete_visible_threshold(self):
        self.three_episodes()
        self.demo.grant("limited", {"fuel"}, {"ticket-1", "ticket-2"})
        card = self.demo.card("limited", "csv")
        self.assertEqual(card["independent_episodes"], 2)
        self.assertEqual({c["source_id"] for c in card["evidence"]}, {"ticket-1", "ticket-2"})
        self.assertFalse(card["recurring"])
        with self.assertRaises(ContractError):
            self.demo.queue_card("limited", "csv")

    def test_old_episode_is_excluded_at_exact_30_day_boundary(self):
        self.ingest("old", "old", days=30)
        self.ingest("a", "a", "a", days=2)
        self.ingest("b", "b", "b", days=1)
        self.assertEqual(self.demo.card("owner", "csv")["independent_episodes"], 2)
        with self.assertRaises(ContractError):
            self.demo.queue_card("owner", "csv")

    def test_aging_out_between_queue_and_send_blocks_stale_card(self):
        self.ingest("oldest", "oldest", "a", days=29)
        self.ingest("a", "a", "a", days=2)
        self.ingest("b", "b", "b", days=1)
        key = self.demo.queue_card("owner", "csv")
        # Keep source TTLs alive to test the recurrence window, not source expiry.
        for source in list(self.demo.sources.values()):
            self.demo.sources[source.source_id] = replace(source, expires_at=self.now + 3 * 86400)
        self.demo.now += 86400
        with self.assertRaises(ContractError):
            self.demo.deliver_once("owner", key)
        self.assertFalse(self.demo.receiver)

    def test_time_window_retracts_already_delivered_card_without_source_ttl(self):
        self.ingest("oldest", "oldest", "a", days=29)
        self.ingest("a", "a", "a", days=2)
        self.ingest("b", "b", "b", days=1)
        for source in list(self.demo.sources.values()):
            self.demo.sources[source.source_id] = replace(source, expires_at=self.now + 3 * 86400)
        self.demo.deliver_once("owner", self.demo.queue_card("owner", "csv"))
        self.demo.now += 86400
        self.assertEqual(len(self.demo.sources), 3)
        self.assertFalse(self.demo.receiver)
        self.assertFalse(self.demo.card("owner", "csv")["recurring"])

    def test_operator_or_unknown_voice_cannot_be_explicit_user_wish(self):
        for speaker in ("support", "unknown"):
            with self.subTest(speaker=speaker), self.assertRaises(ContractError):
                self.ingest(speaker, speaker, speaker=speaker)
        self.assertFalse(self.demo.analyses)

    def test_unspecified_speaker_is_unknown_not_user(self):
        fragment = Fragment("body", "Добавьте CSV", modality="audio")
        self.assertEqual(fragment.speaker, "unknown")
        source = Source("call", 1, "fuel", "a", "a", self.now + 1,
                        (fragment,), self.now - 1)
        self.demo.register_source(source)
        with self.assertRaises(ContractError):
            self.demo.analyze("owner", prepared_output(source))

    def test_no_visible_sources_means_no_topic_metadata(self):
        self.three_episodes()
        self.demo.grant("limited", {"fuel"}, set())
        with self.assertRaises(Forbidden):
            self.demo.card("limited", "csv")

    def test_limited_view_does_not_copy_global_derived_title_or_decision(self):
        self.three_episodes()
        self.demo.rename_topic("owner", "csv", "Secret wish from hidden client")
        self.demo.decide("owner", "csv", "accepted")
        self.demo.grant("limited", {"fuel"}, {"ticket-1"})
        card = self.demo.card("limited", "csv")
        self.assertNotIn("Secret", card["title"])
        self.assertNotEqual(card["decision"], "accepted")

    def test_hypothesis_does_not_enter_explicit_wish_topic(self):
        with self.assertRaises(ContractError):
            self.ingest("hypothesis", "episode", origin="hypothesis")
        self.ingest("observed", "episode", origin="observed_pain", topic=None)
        self.assertEqual(self.demo.card("owner", "csv")["raw_sources"], 0)

    def test_conflicting_customer_for_same_trusted_episode_requires_review(self):
        self.ingest("ticket", "episode", "a")
        with self.assertRaises(ContractError):
            self.ingest("call", "episode", "b")

    def test_recipient_cannot_deliver_another_recipients_outbox_payload(self):
        self.three_episodes()
        key = self.demo.queue_card("owner", "csv")
        self.demo.grant("other-owner", {"fuel"})
        with self.assertRaises(Forbidden):
            self.demo.deliver_once("other-owner", key)

    def test_revoke_one_source_after_delivery_retracts_and_blocks_republish(self):
        self.three_episodes()
        key = self.demo.queue_card("owner", "csv")
        self.demo.deliver_once("owner", key)
        self.demo.grant("owner", {"fuel"}, {"ticket-1", "ticket-2"})
        self.assertFalse(self.demo.receiver)
        with self.assertRaises(ContractError):
            self.demo.queue_card("owner", "csv")

    def test_cli_walkthrough_cannot_publish_two_episodes(self):
        result = run_demo()
        self.assertFalse(result["three_sources_two_episodes_blocked"]["recurring"])
        self.assertTrue(result["four_sources_three_episodes_eligible"]["recurring"])
        self.assertEqual(result["mock_destination_cards_after_retry"], 1)
        self.assertEqual(result["after_call_delete"]["independent_episodes"], 3)
        self.assertTrue(result["old_card_retracted_before_regeneration"])
        self.assertFalse(result["after_episode_delete_below_threshold"]["recurring"])
        self.assertEqual(result["destination_cards_after_episode_delete"], 0)


if __name__ == "__main__":
    unittest.main()
