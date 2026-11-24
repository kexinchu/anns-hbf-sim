"""Offline completeness and provenance audit; never substitutes missing sweep points."""
import csv,json,pathlib,sys,hashlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from paper_curves_v2 import ROOT,cases,addresses,validate,sha
out=pathlib.Path(sys.argv[1]);cfg=json.loads((ROOT/'calibration/paper-curves/protocol-v2.json').read_text());grid=cases(cfg);manifest=json.loads((out/'manifest.json').read_text());rows=list(csv.DictReader((out/'curves.csv').open()))
assert manifest['protocol_sha256']==sha(ROOT/'calibration/paper-curves/protocol-v2.json')
assert manifest['runner_sha256']==sha(ROOT/'tests/paper_curves_v2.py') and manifest['cases']==grid
assert not manifest['fit']['performed'] and manifest['fit']['observations_used']==[]
assert len(rows)==len(grid)==192
for c,row in zip(grid,rows):
 key='-'.join(str(c[k]) for k in ['size','cache','pattern','qd','mocs','seed']);addr=addresses(c)
 assert (out/(key+'.input')).read_text()==''.join(f'{x}\n' for x in addr)
 status=json.loads((out/(key+'.status.json')).read_text());assert status['case']==c and status['valid'] and status['exit']==0
 computed=validate(c,addr,(out/(key+'.jsonl')).read_text(),(out/(key+'.stderr')).read_text())
 for k,v in computed.items():assert str(v)==row[k],(key,k)
 if c['pattern']=='sequential' and c['seed']==8301:
  other=key.removesuffix('8301')+'2718'
  for ext in ['input','jsonl','stderr']:assert (out/(key+'.'+ext)).read_bytes()==(out/(other+'.'+ext)).read_bytes(),'deterministic replay mismatch'
assert json.loads((out/'verdict.json').read_text())['cases']==192
files={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and (p.suffix in ['.jsonl','.stderr','.input'] or p.name.endswith('.status.json'))}
(out/'audit.json').write_text(json.dumps({'cases':192,'offline_recheck':'PASS','sequential_seed_duplicates_byte_identical':True,'fit_performed':False,'file_sha256':files,'paper_curve_reproduced':False,'hardware_calibrated':False,'performance_ready':False},indent=2));print('PASS: 192 cases and per-request records audited; no fitting')
