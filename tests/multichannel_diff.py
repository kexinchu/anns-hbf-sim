"""Independent address inversion and transition/score checks, no donor imports."""
import json,pathlib,subprocess,sys,uuid
root=pathlib.Path(sys.argv[2])/uuid.uuid4().hex;root.mkdir(parents=True)
def run(args,name):
 p=subprocess.run([sys.argv[1],*args],text=True,capture_output=True,timeout=90)
 (root/(name+'.json')).write_text(json.dumps(dict(args=args,stdout=p.stdout,stderr=p.stderr,exit=p.returncode),indent=2))
 return p,[json.loads(x) for x in p.stdout.splitlines()]
if len(sys.argv)>3 and sys.argv[3]=='mapping':
 n=0
 for c in [1,2,4]:
  for stripe in [64,128,256,4096]:
   for first in [0,c]:
    p,rows=run(list(map(str,[c,stripe,first,4096])),str(n));n+=1;assert p.returncode==0,p.stderr
    expected=[]
    # Enumerate a complete local NAND page on each channel, then invert stripes.
    for ch in range(c):
     for local in range(first//c*4096,(first//c+1)*4096,64):
      block,within=divmod(local,stripe)
      expected.append([4096+(block*c+ch)*stripe+within,ch,local])
    assert rows[0]['plan']==sorted(expected)
    assert rows[1:-1]==[dict(completed=i,aggregate=i==c) for i in range(1,c+1)]
    assert rows[-1]==dict(accepted=c*64,responses=c*64,duplicate='stale_ack')
 for args in [['2','96','0'],['2','64','1'],['4','64','6'],['5','64','0']]:
  p,_=run(args,'invalid-'+'-'.join(args));assert p.returncode!=0
 print('PASS 24 mapping/aggregation cases and 4 rejected profiles')
else:
 n=0
 for stripe in [64,128,4096]:
  for target in [0,1]:
   p,rows=run(list(map(str,[stripe,target,10+n])),str(n));n+=1;assert p.returncode==0,p.stderr
   events={x['event']:x for x in rows if 'event' in x}
   assert events['program_fail']['old_pending'] and events['recovered_held']['old_pending']
   assert events['fresh_done_old_pending']['old_pending'] and not events['old_released']['old_pending']
   free=[-1,0,'free',0,0];old=[2,1,'retired',1,0]
   assert events['old_retired']['frames']==[old,free,free,free]
   assert events['fresh_done_old_pending']['frames']==[old,[2,2,'ready',0,0],[3,1,'ready',0,0],free]
   assert events['old_released']['frames']==[free,[2,2,'ready',0,0],[3,1,'ready',0,0],free]
   for tag,total in [('old_retired',320),('before_group',320),('submitted',320),('recovered_held',512),('first_commit',512),('old_ack_rejected',512),('fresh_done_old_pending',832),('old_released',832)]:
    assert events[tag]['accepted']==events[tag]['responses']==total,(tag,events[tag])
   for tag in ['submitted','recovered_held','old_ack_rejected']:
    f=events[tag]['frames'];assert f[1][2:] == ['writeback',0,1] and f[2][2:]==['writeback',0,1],(tag,f)
   for x in [r for r in rows if r.get('event')=='partial_parent']:
    assert sum(f[2]=='writeback' and f[4]==1 for f in x['frames'])==2
   for r in [r for r in rows if 'answer' in r]:
    value=10+n-1+(20 if r['answer']=='old' else 200)
    expected=[sum((value+(i*32+j)%17-3)**2 for j in range(32)) for i in range(32)]
    assert r['scores']==expected
    assert r['top10']==[64+i for i in sorted(range(32),key=lambda i:(expected[i],i))[:10]]
   final=rows[-1];assert final['status']=='PASS' and not final['performance_ready']
   assert final['accepted']==final['responses']==832 and final['errors']==final['replay']==64,final
   if len(sys.argv)>3 and sys.argv[3]=='CUDA':assert final['backend']=='CUDA_A6000'
 for mutation in ['misbind_ack','reuse_old_frame']:
  p,rows=run(['64','0','10',mutation],mutation)
  if mutation=='misbind_ack':assert p.returncode!=0
  else:
   old=next(x['scores'] for x in rows if x.get('answer')=='old')
   assert old!=[sum((30+(i*32+j)%17-3)**2 for j in range(32)) for i in range(32)]
 print('PASS 6 joint recovery/race schedules and 2 rejected mutations')
