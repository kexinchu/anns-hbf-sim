"""Negative controls for the offline auditor using a retained long random trace."""
import gzip,json,pathlib,sys,copy
from turnover_v3 import check,trace
root=pathlib.Path(sys.argv[1]);p=root/'results/payload-v3-256-3072-random.jsonl.gz'
rows=[json.loads(l) for l in gzip.open(p,'rt')];a=trace(256,3072,'random')
def audit(r):return check('\n'.join(json.dumps(x) for x in r),a,256,128,3072)
audit(rows)
mutations=[]
for kind,field in [('request','submit_ps'),('request','id'),('sense','ps'),('summary','useful_bytes'),('summary','senses')]:
 bad=copy.deepcopy(rows)
 if kind=='sense':x=next(x for x in bad if x.get('action')=='sense-finish')
 elif kind=='request' and field=='submit_ps':x=next(x for x in bad if x['kind']=='request' and x['id']>=10128)
 else:x=next(x for x in bad if x['kind']==kind)
 x[field]+=1;mutations.append(bad)
mutations.append([x for x in rows if not(x['kind']=='request' and x['id']==10000)])
for bad in mutations:
 try:audit(bad)
 except (AssertionError,KeyError):pass
 else:raise AssertionError('corrupted archive accepted')
print('six long-trace corruptions rejected')
