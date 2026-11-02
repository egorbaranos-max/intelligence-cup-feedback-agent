"""Parent-owned GPU smoke: no evaluation cases; save unchanged raw completions."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

p=argparse.ArgumentParser()
p.add_argument('--repo', required=True)
p.add_argument('--model-manifest', required=True)
p.add_argument('--output', required=True)
a=p.parse_args()
repo=Path(a.repo).resolve()
sys.path.insert(0,str(repo))
from agent.backend import LocalMLX
from agent.structured import StructuredDecodingError
import mlx.core as mx
import numpy as np
from llguidance.mlx import apply_token_bitmask

# Test the actual Metal mask adapter independently of model behavior.
masked=apply_token_bitmask(mx.array([[0.,1.,2.,3.,4.,5.,6.,7.]]),np.array([[0b1010]],dtype=np.int32))
mx.eval(masked)
values=masked.tolist()[0]
assert values[1]==1. and values[3]==3.
assert all(values[i]==-float('inf') for i in (0,2,4,5,6,7))
backend=LocalMLX(a.model_manifest)
report={'started_at':datetime.now(timezone.utc).isoformat(),'kind':'grammar integration smoke; not accuracy evaluation',
        'model':backend.provenance,'mask_adapter_passed':True,'calls':[],
        'code_sha256':{str(f.relative_to(repo)):hashlib.sha256(f.read_bytes()).hexdigest()
                       for f in [repo/'agent/backend.py',repo/'agent/structured.py']}}
output=Path(a.output)
def save():
 output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
save()
for message in [
 'Верни только JSON-объект {"ok":true,"message":"Проверка"}.',
 'Верни только JSON-объект с ключом a и значением [[[[[{"b":"ёж 🦔"}]]]]].',
 'Напиши обычный текст без JSON. Но ответ должен сохранять исходный смысл: проверка завершена.'
]:
 messages=[{'role':'system','content':'Return one JSON object only.'},{'role':'user','content':message}]
 raw,stats=backend.generate(messages,max_tokens=128)
 assert isinstance(json.loads(raw),dict)
 assert stats['finish_reason']=='stop'
 report['calls'].append({'messages':messages,'raw_response':raw,'stats':stats,'status':'passed'})
 save()
try:
 backend.generate([{'role':'user','content':'Верни JSON с длинным массивом из ста строк.'}],max_tokens=1)
except StructuredDecodingError as exc:
 assert exc.stats['finish_reason']=='length'
 report['truncation']={'status':'passed; rejected','raw_response':exc.raw_response,'stats':exc.stats,'error':str(exc)}
else:
 raise AssertionError('Truncation was not rejected')
report['status']='passed';save()
print(json.dumps({'status':'passed','output':str(output),'calls':len(report['calls']),'truncation':'rejected'},ensure_ascii=False))
