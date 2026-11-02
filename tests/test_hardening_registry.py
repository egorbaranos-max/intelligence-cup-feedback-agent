"""Complete-registry mechanics with scripted relation labels; no semantic claims."""
import copy
import unittest

from agent.pipeline import ValidationResult
from agent.registry import candidate_plan, resolve_registry_topic
from tests.test_live_pipeline import source, response, validate, candidate, comparison


class RegistryComparisonTests(unittest.TestCase):
    def setUp(self):
        self.source = source()
        self.intent = validate(response()).value['intents'][0]

    def plan(self, count):
        return candidate_plan(self.intent, self.source, [candidate(f'{i:02d}') for i in range(count)])

    def results(self, plan, same_ids=(), unclear_ids=()):
        return [comparison(batch, ['same' if c['id'] in same_ids else 'unclear' if c['id'] in unclear_ids else 'different'
                                   for c in batch]) for batch in plan['batches']]

    def test_sixth_candidate_is_examined_and_can_match(self):
        plan = self.plan(6)
        self.assertEqual([len(b) for b in plan['batches']], [5, 1])
        result = resolve_registry_topic(self.intent, self.source, plan, self.results(plan, same_ids={'05'}))
        self.assertEqual(result['status'], 'matched')
        self.assertEqual(result['topic_id'], '05')

    def test_complete_different_registry_can_create_new_theme_after_five(self):
        plan = self.plan(11)
        result = resolve_registry_topic(self.intent, self.source, plan, self.results(plan))
        self.assertEqual(result['status'], 'new')
        empty = self.plan(0)
        self.assertEqual(result['topic_id'], resolve_registry_topic(self.intent, self.source, empty, [])['topic_id'])

    def test_second_same_in_later_batch_never_silently_merges(self):
        plan = self.plan(6)
        result = resolve_registry_topic(self.intent, self.source, plan, self.results(plan, same_ids={'00', '05'}))
        self.assertEqual(result['status'], 'needs_review')
        self.assertIsNone(result['topic_id'])

    def test_unclear_or_invalid_later_batch_blocks_prior_match(self):
        plan = self.plan(6)
        for matches in (self.results(plan, same_ids={'00'}, unclear_ids={'05'}),
                        [self.results(plan, same_ids={'00'})[0], ValidationResult(False, None, ['bad JSON'])]):
            self.assertEqual(resolve_registry_topic(self.intent, self.source, plan, matches)['status'], 'needs_review')

    def test_overflow_is_visible_and_has_no_model_batches(self):
        accepted = self.plan(25)
        self.assertTrue(accepted['complete'])
        self.assertEqual(len(accepted['batches']), 5)
        overflow = self.plan(26)
        self.assertFalse(overflow['complete'])
        self.assertEqual(overflow['candidate_pool_size'], 26)
        self.assertEqual(len(overflow['candidate_ids']), 26)
        self.assertEqual(overflow['batches'], [])
        self.assertEqual(resolve_registry_topic(self.intent, self.source, overflow, [])['status'], 'needs_review')

    def test_scope_and_order_are_deterministic(self):
        topics = [candidate('z'), candidate('private', product_id='elsewhere'), candidate('a')]
        first = candidate_plan(self.intent, self.source, topics)
        second = candidate_plan(self.intent, self.source, list(reversed(topics)))
        self.assertEqual(first, second)
        self.assertEqual(first['candidate_ids'], ['a', 'z'])
        self.assertEqual(first['candidate_pool_size'], 2)

    def test_missing_duplicated_or_cross_product_coverage_is_rejected(self):
        for mutation in ('missing_result', 'duplicated_batch', 'wrong_product', 'missing_id', 'wrong_pool'):
            plan = self.plan(6)
            matches = self.results(plan)
            if mutation == 'missing_result':
                matches.pop()
            elif mutation == 'duplicated_batch':
                plan['batches'][1] = copy.deepcopy(plan['batches'][0])
                matches[1] = comparison(plan['batches'][1], ['different'] * 5)
            elif mutation == 'wrong_product':
                plan['batches'][1][0]['product_id'] = 'another'
            elif mutation == 'missing_id':
                plan['candidate_ids'].pop()
            else:
                plan['candidate_pool_size'] = True
            self.assertEqual(resolve_registry_topic(self.intent, self.source, plan, matches)['status'], 'needs_review')

    def test_foreign_result_ids_cannot_be_reused_across_batches(self):
        plan = self.plan(6)
        matches = self.results(plan)
        matches[1] = matches[0]
        self.assertEqual(resolve_registry_topic(self.intent, self.source, plan, matches)['status'], 'needs_review')

    def test_duplicate_registry_ids_fail_closed_before_matching(self):
        plan = candidate_plan(self.intent, self.source, [candidate('same'), candidate('same')])
        self.assertFalse(plan['complete'])
        self.assertEqual(plan['batches'], [])

    def test_noneligible_intent_cannot_acquire_a_topic_through_empty_plan(self):
        for changes, status in [({'kind': 'incident'}, 'not_eligible'), ({'review_required': True}, 'needs_review')]:
            result = resolve_registry_topic({**self.intent, **changes}, self.source, self.plan(0), [])
            self.assertEqual(result['status'], status)
            self.assertIsNone(result['topic_id'])


if __name__ == '__main__':
    unittest.main()
