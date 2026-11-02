"""Protect human-label provenance and holdout separation before any training."""
import copy
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tools.annotation_workflow import (checked_review, digest, export_training,
                                       prepare, prepare_adjudication, review_template)


class AnnotationWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.sources = [{"id": f"source-{i}", "product_id": "demo", "speaker": "user",
                         "customer_id": f"customer-{i}", "episode_id": f"episode-{i}",
                         "episode_at": "2026-10-20T12:00:00Z", "text": f"Нужна новая возможность {i}."}
                        for i in range(6)]
        first = review_template(self.sources)
        first.update(reviewer_id="test-reviewer-A", label_author="human", attested_independent=True)
        for i, item in enumerate(first["items"]):
            item.update(reviewed=True, family_id=f"family-{i}", split=["train", "valid", "test"][i % 3])
            item["annotation"] = {"status": "ok", "intents": [{"kind": "feature_request",
                "origin": "user_explicit", "statement": self.sources[i]["text"],
                "evidence_refs": [{"span_id": "span_0001"}], "uncertainties": []}]}
        second = copy.deepcopy(first)
        second["reviewer_id"] = "test-reviewer-B"
        self.reviews = [first, second]
        self.tmp = tempfile.TemporaryDirectory()
        self.output = Path(self.tmp.name) / "export"

    def tearDown(self):
        self.tmp.cleanup()

    def export(self, **kwargs):
        return export_training(self.sources, self.reviews, self.output, **kwargs)

    def test_blank_template_contains_no_model_labels(self):
        blank = review_template(self.sources)
        self.assertEqual(blank["label_author"], "")
        self.assertFalse(blank["attested_independent"])
        self.assertTrue(all(not x["reviewed"] and x["annotation"]["intents"] == [] for x in blank["items"]))

    def test_ai_labels_cannot_be_exported_as_human(self):
        self.reviews[0]["label_author"] = "AI"
        with self.assertRaisesRegex(ValueError, "human"):
            self.export()
        self.assertFalse(self.output.exists())

    def test_independence_requires_explicit_attestation(self):
        self.reviews[0]["attested_independent"] = False
        with self.assertRaisesRegex(ValueError, "independent"):
            self.export()

    def test_reviewer_names_must_differ(self):
        self.reviews[1]["reviewer_id"] = " TEST-REVIEWER-a "
        with self.assertRaisesRegex(ValueError, "different"):
            self.export()

    def test_unreviewed_hard_case_blocks_whole_export(self):
        self.reviews[0]["items"][0]["reviewed"] = False
        with self.assertRaisesRegex(ValueError, "unreviewed"):
            self.export()

    def test_omitted_case_is_not_silently_dropped(self):
        self.reviews[0]["items"].pop()
        with self.assertRaisesRegex(ValueError, "every source"):
            self.export()

    def test_changed_source_hash_rejected(self):
        self.sources[0]["text"] += " Изменение."
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.export()

    def test_invented_evidence_span_rejected(self):
        self.reviews[0]["items"][0]["annotation"]["intents"][0]["evidence_refs"] = [{"span_id": "nonexistent"}]
        with self.assertRaisesRegex(ValueError, "invalid annotation"):
            self.export()

    def test_disagreement_writes_no_training_data(self):
        self.reviews[1]["items"][0]["annotation"]["intents"][0]["kind"] = "service_request"
        result = self.export()
        self.assertEqual(result["status"], "blocked_disagreement")
        self.assertEqual(result["source_ids"], ["source-0"])
        self.assertFalse(self.output.exists())

    def test_third_human_can_resolve_a_record(self):
        self.reviews[1]["items"][0]["annotation"]["intents"][0]["kind"] = "service_request"
        third = copy.deepcopy(self.reviews[0])
        third.update(reviewer_id="test-reviewer-C", attested_independent=False)
        third["items"] = third["items"][:1]
        self.assertEqual(self.export(adjudication=third)["status"], "exported; training not run")

    def test_human_family_cannot_cross_splits(self):
        for review in self.reviews:
            review["items"][1]["family_id"] = "family-0"
        with self.assertRaisesRegex(ValueError, "leakage.*family"):
            self.export()

    def test_same_episode_cannot_cross_splits_even_with_different_family(self):
        self.sources[1]["episode_id"] = self.sources[0]["episode_id"]
        for review in self.reviews:
            review["dataset_sha256"] = digest(self.sources)
            review["items"][1]["source_sha256"] = digest(self.sources[1])
        with self.assertRaisesRegex(ValueError, "leakage.*episode"):
            self.export()

    def test_test_material_kept_out_of_training_directory(self):
        result = self.export()
        self.assertEqual(result["counts"], {"train": 2, "valid": 2, "test": 2})
        self.assertEqual({p.name for p in (self.output / "training").iterdir()}, {"train.jsonl", "valid.jsonl"})
        train = (self.output / "training/train.jsonl").read_text()
        self.assertNotIn('source-2', train)
        self.assertEqual(len((self.output / "heldout/inputs.jsonl").read_text().splitlines()), 2)
        self.assertIn("self-attested", result["limits"][0])

    def test_export_refuses_overwrite(self):
        self.export()
        with self.assertRaisesRegex(ValueError, "new training"):
            self.export()

    def test_html_escapes_literal_script_close_in_untrusted_source(self):
        self.sources[0]["text"] = '</script><script>alert("bad")</script>'
        prepare(self.sources, self.output)
        html = (self.output / "index.html").read_text()
        self.assertNotIn('</script><script>alert', html)
        self.assertIn('\\u003c/script>', html)
        self.assertIn("connect-src 'none'", html)

    def package_payload(self):
        html = (self.output / "index.html").read_text()
        return json.loads(re.search(r'<script id="payload" type="application/json">(.*?)</script>', html, re.S).group(1))

    def test_adjudication_package_contains_only_conflicts_and_full_dataset_hash(self):
        self.reviews[1]["items"][1]["annotation"]["intents"][0]["kind"] = "service_request"
        result = prepare_adjudication(self.sources, self.reviews, self.output)
        payload = self.package_payload()
        self.assertEqual(result["source_ids"], ["source-1"])
        self.assertEqual(payload["mode"], "adjudication")
        self.assertEqual([s["id"] for s in payload["sources"]], ["source-1"])
        self.assertEqual(payload["review"]["dataset_sha256"], digest(self.sources))
        self.assertNotEqual(payload["review"]["dataset_sha256"], digest(payload["sources"]))
        self.assertEqual([x["reviewer_id"] for x in payload["first_pass_answers"]["source-1"]],
                         ["test-reviewer-A", "test-reviewer-B"])
        item = payload["review"]["items"][0]
        self.assertFalse(item["reviewed"])
        self.assertEqual(item["annotation"]["intents"], [])
        self.assertEqual(len((self.output / "inputs.jsonl").read_text().splitlines()), 1)
        self.assertEqual(payload["first_pass_review_sha256"], [digest(r) for r in self.reviews])

    def test_adjudication_from_package_exports_without_manual_subset_edit(self):
        self.reviews[1]["items"][0]["annotation"]["intents"][0]["kind"] = "service_request"
        prepare_adjudication(self.sources, self.reviews, self.output)
        payload = self.package_payload()
        third = payload["review"]
        third.update(reviewer_id="test-reviewer-C", label_author="human")
        # Choosing a first-pass answer and explicitly checking it matches the UI.
        third["items"][0].update(copy.deepcopy(payload["first_pass_answers"]["source-0"][0]["item"]))
        result = export_training(self.sources, self.reviews, Path(self.tmp.name) / "training", third)
        self.assertEqual(result["status"], "exported; training not run")

    def test_adjudication_prepare_requires_valid_independent_distinct_reviewers(self):
        mutations = [lambda r: r.update(attested_independent=False),
                     lambda r: r.update(label_author="AI"),
                     lambda r: r.update(reviewer_id="TEST-REVIEWER-A"),
                     lambda r: r["items"][0].update(reviewed=False)]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                reviews = copy.deepcopy(self.reviews)
                mutation(reviews[1])
                with self.assertRaises(ValueError):
                    prepare_adjudication(self.sources, reviews, self.output)
                self.assertFalse(self.output.exists())

    def test_no_disagreements_creates_no_adjudication_package(self):
        result = prepare_adjudication(self.sources, self.reviews, self.output)
        self.assertEqual(result["status"], "no_disagreements")
        self.assertFalse(self.output.exists())

    def test_reviewed_empty_intents_still_export(self):
        for review in self.reviews:
            review["items"][0]["annotation"]["intents"] = []
        self.assertEqual(self.export()["status"], "exported; training not run")

    def run_ui(self, assertions):
        """Execute actual template JavaScript with a minimal DOM, no browser/network."""
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for annotation UI behavior tests")
        html = (self.output / "index.html").read_text()
        script = re.findall(r'<script>(.*?)</script>', html, re.S)[0]
        harness = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const nodes=new Map();
class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.listeners={};this.textContent='';this.value='';this.checked=false;}
 set id(value){this._id=value;nodes.set(value,this);} get id(){return this._id;}
 append(...children){this.children.push(...children);} replaceChildren(...children){this.children=children;}
 addEventListener(event,handler){this.listeners[event]=handler;} click(){if(this.onclick)this.onclick();}
}
for(const id of ['payload','card','position','progress','prev','next','reviewer','human','independent','download','restore','message','heading','intro','independent-label']){const node=new Element('div');node.id=id;}
nodes.get('payload').textContent=JSON.stringify(input.payload);
const context=vm.createContext({document:{getElementById:id=>nodes.get(id)||null,createElement:tag=>new Element(tag)},
 assert,Blob,URL,setTimeout:fn=>fn(),console,nodes});
vm.runInContext(input.script,context);
vm.runInContext(input.assertions,context);
'''
        result = subprocess.run([node, "-e", harness],
                                input=json.dumps({"payload": self.package_payload(), "script": script, "assertions": assertions}),
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_ui_invalid_restore_preserves_unsaved_draft_and_identity(self):
        prepare(self.sources, self.output)
        self.run_ui(r'''
review.items[0].note='unsaved work';byId('reviewer').value='unsaved identity';
const before=JSON.stringify(review);
for(const mutate of [
 x=>x.items[0].annotation.intents.push({kind:'unknown'}),
 x=>x.items[0].annotation.intents.push({kind:'unknown',origin:'observed_pain',statement:'',evidence_refs:[{span_id:'invented'}],uncertainties:[]}),
 x=>x.items[0].annotation.intents.push({kind:'unknown',origin:'observed_pain',statement:'',evidence_refs:[],uncertainties:[42]}),
 x=>x.items[0].reviewed='yes',x=>x.items[0].source_id='changed',x=>x.items[0].annotation.status='invalid',
 x=>x.reviewer_id=null,x=>x.items[0].annotation.intents.push(null)
]){const bad=JSON.parse(before);mutate(bad);assert.throws(()=>restoreDraft(bad));assert.equal(JSON.stringify(review),before);assert.equal(byId('reviewer').value,'unsaved identity');}
const valid=JSON.parse(before);valid.items[0].note='restored work';valid.reviewer_id='restored identity';restoreDraft(valid);
assert.equal(review.items[0].note,'restored work');assert.equal(byId('reviewer').value,'restored identity');
''')

    def test_ui_render_failure_rolls_back_valid_import(self):
        prepare(self.sources, self.output)
        self.run_ui(r'''
review.items[0].note='unsaved';const before=JSON.stringify(review),realRender=render;
let failOnce=true;render=()=>{if(failOnce){failOnce=false;throw Error('render failure');}realRender();};
const loaded=JSON.parse(before);loaded.items[0].note='new';assert.throws(()=>restoreDraft(loaded));
assert.equal(JSON.stringify(review),before);
''')

    def test_ui_adjudication_choice_is_editable_unreviewed_and_exports_subset(self):
        self.reviews[1]["items"][0]["annotation"]["intents"][0]["kind"] = "service_request"
        prepare_adjudication(self.sources, self.reviews, self.output)
        self.run_ui(r'''
assert.equal(adjudicating,true);assert.equal(byId('independent-label').hidden,true);
const item=review.items[0],answer=data.first_pass_answers[item.source_id][1];
chooseFirstPass(item,answer);assert.equal(item.annotation.intents[0].kind,'service_request');assert.equal(item.reviewed,false);
item.reviewed=true;edit(item,()=>item.annotation.intents[0].statement='edited');assert.equal(item.reviewed,false);
assert.notEqual(answer.item.annotation.intents[0].statement,'edited');
item.annotation.intents=[];item.reviewed=true;validateDraft(review);assert.equal(item.reviewed,true);
byId('reviewer').value='third human';byId('human').checked=true;byId('independent').checked=true;
byId('download').onclick();assert.equal(review.items.length,1);assert.equal(review.items[0].source_id,'source-0');
assert.equal(review.attested_independent,false);assert.equal(review.dataset_sha256,data.review.dataset_sha256);
''')

    def test_ui_real_field_edits_clear_reviewed(self):
        prepare(self.sources, self.output)
        self.run_ui(r'''
const item=review.items[0];item.reviewed=true;render();
const descendants=node=>[node,...node.children.flatMap(descendants)];
const family=descendants(byId('card')).find(n=>n.placeholder==='Например: contract-expiry-email');
family.value='changed family';family.listeners.input();assert.equal(item.family_id,'changed family');assert.equal(item.reviewed,false);assert.equal(byId('record-reviewed').checked,false);
''')


if __name__ == "__main__":
    unittest.main()
