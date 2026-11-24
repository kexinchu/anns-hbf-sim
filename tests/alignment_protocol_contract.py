"""Address-generation and cold-page activation contract, independent of driver indices."""
import pathlib,json,subprocess,sys,hashlib
exe=str(pathlib.Path(sys.argv[1]).resolve());out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
root=pathlib.Path(__file__).resolve().parents[1];protocol=root/'calibration/paper-curves/protocol-v2.json';cfg=json.loads(protocol.read_text())
assert protocol.with_suffix('.sha256').read_text().split()[0]==hashlib.sha256(protocol.read_bytes()).hexdigest(), 'frozen protocol hash changed'
assert cfg['mocs_primary_per_channel']==4096 and cfg['requests_per_run']==1024
cases=[('contiguous-256',list(range(0,1024*256,256)),64),('page-stride-256',list(range(0,1024*4096,4096)),1024)]
records=[]
for name,addresses,expected_senses in cases:
 assert len({a//4096 for a in addresses})==expected_senses
 data=''.join(str(a)+'\n' for a in addresses)
 r=subprocess.run([exe,'256','128','0','0','4096','byte-addresses'],input=data,text=True,capture_output=True,timeout=90)
 (out/(name+'.jsonl')).write_text(r.stdout);(out/(name+'.stderr')).write_text(r.stderr)
 assert r.returncode==0,r.stderr
 summary=json.loads(r.stdout.splitlines()[-1]);assert summary['senses']==expected_senses and summary['requests']==1024
 records.append({'case':name,'senses':expected_senses,'page_efficiency':262144/(4096*expected_senses)})
for mode,data,reason in [('bad-mode','', 'unknown address mode'),('byte-addresses','64\n','address outside frozen footprint/alignment'),('byte-addresses','4194304\n','address outside frozen footprint/alignment')]:
 r=subprocess.run([exe,'256','128','0','0','4096',mode],input=data,text=True,capture_output=True,timeout=5)
 assert r.returncode!=0 and reason in r.stderr and 'initialization-start' not in r.stderr and not r.stdout
(out/'verdict.json').write_text(json.dumps({'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'cases':records,'invalid_inputs_rejected':3,'paper_curve_reproduced':False},indent=2));print(records)
