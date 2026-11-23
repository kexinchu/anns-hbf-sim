import json,pathlib,subprocess,sys
binary=sys.argv[1];out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=False)
db=[[i//64*100+(i*17+j*13)%23-11 for j in range(32)] for i in range(256)]
def validate(rows):
 answers=[r for r in rows if 'query' in r];assert len(answers)==2
 for r in answers:
  q=r['query'];v=db[[27,172][q]];lists=sorted(range(4),key=lambda l:(sum((l*100-x)**2 for x in v),l))[:2]
  expected=[[i,sum((a-b)**2 for a,b in zip(db[i],v))] for l in lists for i in range(l*64,(l+1)*64)]
  assert r['candidates']==expected
  assert r['topk']==[i for i,s in sorted(expected,key=lambda x:(x[1],x[0]))[:10]]
 assert rows[-1]['status']=='PASS'
for mode in ['clean','retry','cecc','uecc','die','refresh_fail','no_backup','bad_stage','corrupt_gpu','early_publish']:
 p=subprocess.run([binary,mode],text=True,capture_output=True,timeout=30)
 (out/(mode+'.jsonl')).write_text(p.stdout);(out/(mode+'.stderr')).write_text(p.stderr)
 (out/(mode+'.exit')).write_text(str(p.returncode))
 rows=[json.loads(x) for x in p.stdout.splitlines()]
 if mode in ['refresh_fail','no_backup','bad_stage','early_publish']:
  assert p.returncode!=0 and not any('query' in r for r in rows)
  expected_error={'refresh_fail':'refresh program failure; quarantined','no_backup':'unsafe refresh','bad_stage':'transport retry stage mismatch','early_publish':'device data not visible before H2D completion'}[mode]
  assert expected_error in p.stderr,(mode,p.stderr)
  continue
 assert p.returncode==0,p.stderr
 if mode=='corrupt_gpu':
  try:validate(rows)
  except AssertionError:pass
  else:raise AssertionError('corrupt GPU input escaped')
  continue
 validate(rows)
 events=[r['event'] for r in rows if 'event' in r]
 if mode in ['cecc','uecc']:
  assert events.count('refresh_page_verified')==8
  assert events.index('refresh_complete')<events.index('publish')
 if mode=='die':assert events.index('die_poll_busy')<events.index('die_poll_ready')<events.index('publish')
 if mode=='retry':assert [r['value'] for r in rows if r.get('event')=='retry_send']==[3]
print('PASS five CUDA functional recovery cases and five negative cases; not EventLab wire integration or physical HBF calibration')
