"""Independent host ACK oracle; command accounting checks actual EventLab fragments.
Only sequential rewrites of NAND page zero: no random-page-write assumption.
"""
import json,pathlib,subprocess,sys,uuid
root=pathlib.Path(sys.argv[2])/uuid.uuid4().hex;root.mkdir(parents=True)
for seed in range(16):
 fault=seed>=8
 first=100+seed*10;second=first+1
 lines=['fill 1 0','dirty 0',f'send {first} 0 0','evict 0',f'send {first} 0 1',f'ack {first}','pump',f'ack {first}','dirty 0',f'send {first} 0 1',f'send {second} 0 1',f'oldfail {first}',f'ack {first}','refresh 0','evict 0','pump',f'ack {second}',f'ack {second}','evict 0']
 # Manual transition specification, independent of C++ owner/bridge.
 results=['ready','dirty','rejected','busy','sent','invalid','drained','committed','dirty','rejected','sent','stale_ack','stale_ack','busy','unavailable','drained','committed','stale_ack','evicted']
 states=['ready','ready','ready','ready','writeback','writeback','writeback','ready','ready','ready','writeback','writeback','writeback','writeback','writeback','writeback','ready','ready','free']
 dirty=[0,1,1,1,1,1,1,0,1,1,1,1,1,1,1,1,0,0,0]
 p=subprocess.run([sys.argv[1]]+(["program_fail"] if fault else []),input='\n'.join(lines)+'\n',text=True,capture_output=True,timeout=30)
 rows=[json.loads(x) for x in p.stdout.splitlines()]
 (root/f'{seed}.json').write_text(json.dumps(dict(input=lines,expected_results=results,expected_states=states,expected_dirty=dirty,actual=rows,stderr=p.stderr,exit=p.returncode),indent=2))
 assert p.returncode==0 and len(rows)==len(lines),(p.stderr,len(rows))
 for i,row in enumerate(rows):
  assert row['result']==results[i],(i,row)
  assert row['frames'][0][2]==states[i] and row['frames'][0][4]==dirty[i],(i,row)
  n=0 if i<6 else 1 if i<15 else 2
  extra=64 if fault and n else 0
  assert row['completed']==n and row['accepted']==row['responses']==64*n+extra,(i,row)
  assert row['errors']==row['replay']==extra,(i,row)
p=subprocess.run([sys.argv[1],'bad_ack'],input='\n'.join(lines)+'\n',text=True,capture_output=True,timeout=30)
(root/'bad-ack.json').write_text(json.dumps(dict(stdout=p.stdout,stderr=p.stderr,exit=p.returncode),indent=2))
assert p.returncode!=0 or [json.loads(x)['result'] for x in p.stdout.splitlines()]!=results
print('PASS 16 EventLab writeback traces: 64 responses per page, delayed ACK and duplicate isolation, D2H and ID-reuse rejection')
