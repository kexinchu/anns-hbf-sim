"""Independent directed reference contract; no simulator imports or generated goldens."""
import json,pathlib,subprocess,sys,uuid
root=pathlib.Path(sys.argv[2])/uuid.uuid4().hex;root.mkdir(parents=True)
def run(mode,target,mutation=''):
 args=[str(mode),str(target)]+([mutation] if mutation else [])
 p=subprocess.run([sys.argv[1],*args],capture_output=True,text=True,timeout=90)
 (root/('-'.join(args)+'.json')).write_text(json.dumps(dict(args=args,exit=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2))
 return p,[json.loads(x) for x in p.stdout.splitlines()]
def verify(mode,rows):
 # Reference state at observable handoffs. Cancellation never discards the backup.
 expected=[[2,1,'ready',1,0],[4,1,'ready',0,0],[0,1,'writeback',0,1],[1,1,'writeback',0,1]]
 parent=0;fences=0;seen=[]
 for r in rows[:-1]:
  event=r['event'];seen.append(event)
  if event=='parent':parent+=1
  if event=='fenced':fences+=1
  if event=='settled':
   for f in expected[2:]:f[2]='ready';f[4]=int(mode!=4)
  if event=='isolated':expected[0][2]='retired'
  if event=='parent' and parent>2:
   for f in expected[2:]:f[2]='writeback';f[4]=1
  if event=='replayed':
   for f in expected[2:]:f[2]='ready';f[4]=0
  assert r['frames']==expected,(mode,event,r['frames'],expected)
  assert r['old_pending'] and r['responses']<=r['accepted']
 assert fences==int(mode not in (4,5,8))
 assert seen[0]=='submitted' and seen[-1]==('exhausted' if mode in (5,8) else 'replayed')
 assert parent==(2 if mode in (5,8) else 4)
 final=rows[-2]
 # Two permanent program failures consume original+one spare per failed channel.
 failed_channels=2 if mode==5 else 1 if mode==8 else 0
 faults=2*failed_channels if failed_channels else int(mode==4)
 replay=66*failed_channels if failed_channels else 64*int(mode==4)
 base=128 if failed_channels else 256
 assert final['faults']==faults
 assert final['accepted']==final['responses']==base+replay
 assert final['errors']==64*faults+2*failed_channels
 assert final['replay']==replay
 answer=rows[-1]
 assert answer['scores']==[sum((30+(k*32+j)%17-3)**2 for j in range(32)) for k in range(32)]
 assert answer['backend']==sys.argv[3] and answer['performance_ready'] is False
for mode in range(9):
 for target in range(2):
  p,rows=run(mode,target);assert p.returncode==0,(mode,target,p.stderr);verify(mode,rows)
for mode,mutation in [(1,'stale_commit'),(3,'stale_commit'),(2,'reuse_frame')]:
 p,rows=run(mode,0,mutation)
 if mutation=='stale_commit':
  assert p.returncode==1 and p.stderr.strip()==('terminal policy' if mode==1 else 'unacknowledged reset'),p.stderr
 else:assert p.returncode==0,p.stderr
 detected=p.returncode!=0
 if not detected:
  try:verify(mode,rows)
  except AssertionError:detected=True
 assert detected,(mode,mutation)
print('PASS 18 directed variants (9 families), 3 detected mutations')
