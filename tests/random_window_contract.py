"""Retained traces, independent conservation arithmetic, and adversarial inputs."""
import copy,gzip,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from random_window_audit import load,analyze,prefix_equal,sweep,clipped
base=ROOT/'calibration/turnover-v3/20261124/results'
assert sweep([(0,10),(5,15)],[0,5,10,15],2)==[5,10,5]
assert [clipped([(0,10),(5,15)],a,b) for a,b in [(0,5),(5,10),(10,15)]]==[5,10,5]
try:sweep([(0,10),(5,15)],[0,15],1)
except AssertionError:pass
else:raise AssertionError('overcapacity accepted')
rejected=0
for mode in ['service-v2','payload-v3']:
 for size in [256,4096]:
  stem=f'{mode}-{size}-3072-random';rows=load(base/(stem+'.jsonl.gz'));addresses=list(map(int,gzip.open(base/(stem+'.input.gz'),'rt').read().split()))
  original=analyze(rows,addresses,size);assert not original['first_four_pass_5pct'],'historical verdict changed'
  for kind,field in [('request','submit_ps'),('request','id'),('sense-finish','ps'),('sense-finish','page'),('summary','senses')]:
   bad=copy.deepcopy(rows)
   x=next(x for x in bad if x['kind']==kind or x.get('action')==kind);x[field]+=1
   try:analyze(bad,addresses,size)
   except (AssertionError,KeyError):rejected+=1
   else:raise AssertionError('corruption accepted')
  for bad in [rows[1:],list(reversed(rows[:-1]))+[rows[-1]]]:
   try:analyze(bad,addresses,size)
   except (AssertionError,KeyError):rejected+=1
   else:raise AssertionError('missing/reversed event accepted')
  bad=copy.deepcopy(rows);next(x for x in bad if x['kind']=='request')['complete_ps']+=1
  try:prefix_equal(rows,bad)
  except AssertionError:rejected+=1
  else:raise AssertionError('changed prefix accepted')
assert rejected==32
print('PASS: four historical failures preserved; two independent area methods; 32 trace mutations and one overcapacity rejected')
