"""Contract-only tests; no evaluation data or model inference."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from agent.pipeline import KINDS, ORIGINS, RELATIONS, validate_extraction
from agent.response_schemas import RESPONSE_SCHEMAS, STAGE_SCHEMAS
from agent.structured import COMPILER_OPTIONS, JSONGrammar, StructuredDecodingError


def intent(kind='feature_request', statement='First intent'):
    return {'kind':kind,'origin':'user_explicit','statement':statement,
            'evidence_refs':[{'span_id':'span_0001'},{'span_id':'span_0002'}],'uncertainties':[]}


def cases():
    base={'status':'ok','intents':[intent(),intent('incident','Second intent')]}
    good=[('extraction',base),('extraction',{'status':'ok','intents':[]}),
          ('extraction',{'status':'needs_review','intents':[dict(intent('unknown'),uncertainties=['Review'])]}),
          ('verification',{'verdict':'supported','reason':'Test','evidence_span_ids':['id one','id two']}),
          ('verification',{'verdict':'unclear','reason':'Test','evidence_span_ids':[]}),
          ('matching',{'matches':[{'candidate_id':'arbitrary ID','relation':'related','basis':'Test'},
                                  {'candidate_id':'second ID','relation':'different','basis':'Test'}]}),
          ('matching',{'matches':[]})]
    bad=[]
    for key,value in [('kind','no_feature_request'),('kind','observed_pain'),('origin','operator'),('statement',''),('evidence_refs',[]),('uncertainties','none')]:
        x=copy.deepcopy(base);x['intents'][0][key]=value;bad.append(('extraction',x))
    x=copy.deepcopy(base);x['status']='ready';bad.append(('extraction',x))
    x=copy.deepcopy(base);x['intents'][0]['extra']=True;bad.append(('extraction',x))
    x=copy.deepcopy(base);del x['intents'][0]['origin'];bad.append(('extraction',x))
    bad += [('verification',{'verdict':'approved','reason':'Test','evidence_span_ids':[]}),
            ('verification',{'verdict':'unclear','reason':'Test','evidence_quote':None}),
            ('matching',{'matches':[{'candidate_id':'id','relation':'equivalent','basis':'Test'}]}),
            ('matching',{'matches':[{'candidate_id':1,'relation':'same','basis':'Test'}]})]
    return good,bad


class ContractTests(unittest.TestCase):
    def test_enums_and_fields_match_existing_validators(self):
        props=RESPONSE_SCHEMAS['extraction']['properties']['intents']['items']['properties']
        self.assertEqual(set(props['kind']['enum']),KINDS)
        self.assertEqual(set(props['origin']['enum']),ORIGINS)
        self.assertEqual(set(props),{'kind','origin','statement','evidence_refs','uncertainties'})
        relation=RESPONSE_SCHEMAS['matching']['properties']['matches']['items']['properties']['relation']
        self.assertEqual(set(relation['enum']),RELATIONS)
        self.assertEqual(STAGE_SCHEMAS['extraction_repair'],'extraction')

    def test_multiple_intents_refs_and_empty_intents_stay_valid(self):
        source={'id':'test','product_id':'test','speaker':'user','text':'First sentence. Second sentence.'}
        for value in [cases()[0][0][1],{'status':'ok','intents':[]}]:
            result=validate_extraction(json.dumps(value),source)
            self.assertTrue(result.ok,result.errors)

    def test_runner_routes_and_logs_extraction_repair_schema(self):
        from agent.runner import run
        class Backend:
            provenance={'backend':'TEST_ONLY_SCRIPTED_FIXTURE'}
            def __init__(self):self.schemas=[]
            def generate(self,messages,max_tokens,schema_name='generic'):
                self.schemas.append(schema_name)
                return ('{}' if len(self.schemas)==1 else '{"status":"ok","intents":[]}'),{'fixture':True}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);source=path/'input.jsonl'
            source.write_text(json.dumps({'id':'routing','product_id':'test','speaker':'user','text':'Test.'})+'\n')
            b=Backend();run(source,path/'run',b,'2026-11-02T12:00:00Z')
            self.assertEqual(b.schemas,['extraction','extraction'])
            calls=[json.loads(x) for x in (path/'run/calls.jsonl').read_text().splitlines()]
            self.assertEqual([c['stage'] for c in calls],['extraction','extraction_repair'])
            self.assertTrue(all(c['response_schema']=='extraction' for c in calls))


@unittest.skipUnless(importlib.util.find_spec('llguidance'),'optional native grammar')
class NativeStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from llguidance import LLMatcher,LLTokenizer,TokenizerWrapper
        class Bytes:
            eos_token_id=256;bos_token_id=None
            tokens=[bytes([i]) for i in range(256)]+[b'<eos>'];special_token_ids=[256]
            def __call__(self,value):return list(value if isinstance(value,bytes) else value.encode())
        cls.tokenizer=LLTokenizer(TokenizerWrapper(Bytes()),eos_token=256)
        cls.matcher_type=LLMatcher
        cls.grammars={n:LLMatcher.grammar_from_json_schema(s,overrides=COMPILER_OPTIONS) for n,s in RESPONSE_SCHEMAS.items()}

    def accepts(self,stage,value):
        m=self.matcher_type(self.tokenizer,self.grammars[stage],log_level=0)
        self.assertFalse(m.is_error(),m.get_error());self.assertEqual(m.get_grammar_warnings(),[])
        for token in json.dumps(value,ensure_ascii=False).encode():
            mask=m.compute_bitmask()
            if not mask[token//8]&(1<<(token%8)) or not m.consume_token(token):return False
        m.compute_bitmask();return m.is_accepting() and not m.is_error()

    def test_valid_shapes_and_invalid_enums_keys_types(self):
        for expected,values in [(True,cases()[0]),(False,cases()[1])]:
            for stage,value in values:
                with self.subTest(stage=stage,value=value):self.assertEqual(self.accepts(stage,value),expected)

    def test_limits_match_existing_contract(self):
        self.assertTrue(self.accepts('extraction',{'status':'ok','intents':[intent(statement=str(i)) for i in range(30)]}))
        self.assertFalse(self.accepts('extraction',{'status':'ok','intents':[intent(statement=str(i)) for i in range(31)]}))
        self.assertFalse(self.accepts('matching',{'matches':[{'candidate_id':str(i),'relation':'same','basis':'Test'} for i in range(6)]}))

    def test_authorship_and_membership_remain_validator_checks(self):
        value={'status':'ok','intents':[intent()]}
        source={'id':'test','product_id':'test','speaker':'unknown','text':'First sentence. Second sentence.'}
        self.assertTrue(self.accepts('extraction',value))
        self.assertFalse(validate_extraction(json.dumps(value),source).ok)
        value['intents'][0]['evidence_refs']=[{'span_id':'arbitrary unknown ID'}]
        self.assertTrue(self.accepts('extraction',value))
        self.assertFalse(validate_extraction(json.dumps(value),dict(source,speaker='user')).ok)


@unittest.skipUnless(os.environ.get('STRUCTURED_TOKENIZER_MANIFEST'),'set local tokenizer manifest')
class LocalStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from transformers import AutoTokenizer
        manifest=json.loads(Path(os.environ['STRUCTURED_TOKENIZER_MANIFEST']).read_text());path=Path(manifest['local_path'])
        config=json.loads((path/'config.json').read_text())
        cls.hf=AutoTokenizer.from_pretrained(str(path),local_files_only=True,trust_remote_code=False)
        cls.factory=JSONGrammar(SimpleNamespace(_tokenizer=cls.hf,eos_token_ids={cls.hf.eos_token_id}),config['vocab_size'],schemas=RESPONSE_SCHEMAS)

    def test_actual_bpe_accepts_shapes_and_blocks_invalid_enums(self):
        for expected,values in [(True,cases()[0]),(False,cases()[1])]:
            for stage,value in values:
                with self.subTest(stage=stage,value=value):
                    m=self.factory._new_matcher(stage);allowed=True
                    for token in self.hf.encode(json.dumps(value,ensure_ascii=False),add_special_tokens=False):
                        mask=m.compute_bitmask()
                        if not mask[token//8]&(1<<(token%8)) or not m.consume_token(token):allowed=False;break
                    m.compute_bitmask();self.assertEqual(allowed and m.is_accepting() and not m.is_error(),expected)

    def test_schema_provenance_processor_hash_and_unknown_name(self):
        self.assertEqual(set(self.factory.provenance['schemas']),{'generic',*RESPONSE_SCHEMAS})
        for name,schema in RESPONSE_SCHEMAS.items():
            h=hashlib.sha256(json.dumps(schema,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
            self.assertEqual(self.factory.provenance['schemas'][name]['schema_sha256'],h)
            p=self.factory.new_processor(apply_mask=lambda a,b:b,schema_name=name)
            self.assertEqual(p.stats()['schema_name'],name);self.assertEqual(p.stats()['schema_sha256'],h)
        with self.assertRaises(StructuredDecodingError):self.factory.new_processor(apply_mask=lambda a,b:b,schema_name='typo')


if __name__=='__main__':unittest.main()
