"""Independent device-state reference. No implementation imports or recorded goldens."""
import json,pathlib,subprocess,sys,uuid
root=pathlib.Path(sys.argv[2])/uuid.uuid4().hex;root.mkdir(parents=True)
def address(ch=0,die=0,bank=0,page=0,block=0):
 local=(((block*4+page)*2+die)*2+bank)*4096
 return 4096+local*2+ch*64
def oracle(trace):
 t=0;power=False;link=[False]*2;en=[False]*2;epoch=[0]*2;boot=[0]*2;typ=[0]*2
 dies={};de={};writes={};responses={};data={};unknown=set();nxt={};repl={};spares=set();used=set();out=[]
 def mapping(a):
  assert 4096<=a<4096+2*2*2*4*2*4096
  stripe,offset=divmod(a-4096,64);ch=stripe%2;local=(stripe//2)*64+offset
  dlu,byte=divmod(local,4096);lane=dlu%4;page=(dlu//4)%4;block=dlu//16
  return (ch,lane//2,lane%2,repl.get((ch,lane//2,lane%2,block),block),page,byte)
 def ready(p):return power and link[p[0]] and en[p[0]] and dies.get(p[:2],0)<=t
 def interrupt(ch,die=None):
  for w in writes.values():
   if w['live'] and w['p'][0]==ch and (die is None or w['p'][1]==die):unknown.add(w['p'][:4]);w['live']=False
 for op,a,b,c in trace:
  r=dict(result='ok',value=0,map=[],scores=[])
  try:
   if op=='M':r['map']=list(mapping(a))
   elif op=='O':
    assert not power;power=True
    for ch in range(2):link[ch]=en[ch]=False;boot[ch]=t+5;epoch[ch]+=1
   elif op=='P':
    for ch in range(2):interrupt(ch);link[ch]=en[ch]=False;boot[ch]=0;epoch[ch]+=1
    power=False;dies.clear()
   elif op=='A':
    assert a>=t;t=a
    for ch in range(2):
     if power and boot[ch] and boot[ch]<=t:link[ch]=True;boot[ch]=0
    for i,w in writes.items():
     if w['live'] and w['due']<=t:
      p=w['p'];data[p[:5]]=w['v'];nxt[p[:4]]=p[4]+1;w['live']=False;responses[i]=(p[:2],w['e'],w['d'])
   elif op=='C':
    assert a<2 and power and b in (12,16,20);r['value']={12:int(en[a]),16:int(link[a]),20:typ[a]}[b]
   elif op=='S':
    assert a<2 and power
    if b==12:assert c<=1;en[a]=bool(c);r['result']='enabled'
    else:
     assert b==20
     if c>>8!=0x484246:r['result']='ignored'
     else:
      assert not c&252 and c&3!=3
      
      for w in writes.values():
       if w['live'] and w['p'][0]==a:unknown.add(w['p'][:4])
      typ[a]=c&3;epoch[a]+=1;link[a]=False;boot[a]=t+5;r['result']='reset'
      if typ[a]==2:interrupt(a);en[a]=False
   elif op=='D':
    assert power and a<2 and b<2;interrupt(a,b);de[a,b]=de.get((a,b),0)+1;dies[a,b]=t+5
   elif op=='W':
    p=mapping(b);assert a not in used
    if not ready(p):r['result']='blocked'
    else:
     assert p[5]==0
     if p[:4] in unknown:r['result']='unknown'
     elif any(w['live'] and w['p'][:4]==p[:4] for w in writes.values()):r['result']='busy'
     elif p[4]!=nxt.get(p[:4],0):r['result']='order'
     else:
      used.add(a);writes[a]=dict(p=p,v=c,due=t+10,e=epoch[p[0]],d=de.get(p[:2],0),live=True);r['result']='accepted'
   elif op=='L':
    if a not in responses:r['result']='absent'
    else:
     (ch,di),e,d=responses.pop(a);r['result']='success' if power and epoch[ch]==e and de.get((ch,di),0)==d else 'stale'
   elif op in ('E','X'):
    p=mapping(a);assert not any(w['live'] and w['p'][:4]==p[:4] for w in writes.values())
    if op=='E':
     assert ready(p);data={k:v for k,v in data.items() if k[:4]!=p[:4]};unknown.discard(p[:4]);nxt[p[:4]]=0
    else:
     assert p[:3] not in spares;spares.add(p[:3]);repl[p[:4]]=2
   elif op in ('R','G'):
    p=mapping(a)
    if not ready(p):r['result']='blocked'
    elif p[:4] in unknown:r['result']='unknown'
    elif p[:5] not in data:r['result']='erased'
    else:
     r['result']='known';r['value']=data[p[:5]]
     if op=='G':r['scores']=[sum((r['value']+(k*32+j)%17-3)**2 for j in range(32)) for k in range(32)]
   else:assert False
  except (AssertionError,KeyError):r=dict(result='error',value=0,map=[],scores=[])
  out.append(r)
 return out
start=[('O',0,0,0),('C',0,16,0),('W',99,address(),30),('A',5,0,0),('S',0,12,1),('S',1,12,1)]
traces=[]
# Independent inverse mapping enumerates each physical tuple, including channel/die/bank boundaries.
traces.append([('M',address(ch,di,ba,pa,bl)+off*2,0,0) for ch in range(2) for di in range(2) for ba in range(2) for pa in range(4) for bl in range(2) for off in (0,64)]+[('M',4095,0,0),('M',266240,0,0)])
for kind in ['warm','power','die','link0','link1']:
 for completion_first in [False,True]:
  tr=start+[('W',1,address(),30),('W',2,address(die=1),40),('W',3,address(ch=1),50)]
  if completion_first:tr += [('A',15,0,0)]
  tr += [('P',0,0,0)] if kind=='power' else [('D',0,0,0)] if kind=='die' else [('S',0,20,(0x484246<<8)+({'warm':2,'link0':0,'link1':1}[kind]))]
  tr += [('G',address(),0,0),('G',address(ch=1),0,0),('L',1,0,0)]
  if kind=='power':tr += [('O',0,0,0)]
  tr += [('A',20,0,0),('S',0,12,1),('S',1,12,1),('C',0,16,0),('C',0,20,0),('G',address(),0,0),('G',address(die=1),0,0),('G',address(ch=1),0,0),('L',1,0,0),('L',2,0,0),('L',3,0,0),('E',address(),0,0),('W',4,address(),60),('A',30,0,0),('G',address(),0,0),('L',4,0,0)]
  traces.append(tr)
traces += [start+[('S',0,20,0),('C',0,16,0),('S',0,20,0x48424603),('S',0,20,0x48424604),('S',0,16,1),('S',2,12,1),('C',0,99,0),('D',0,2,0),('W',1,address(),30),('E',address(),0,0),('X',address(),0,0),('W',1,address(),30),('A',15,0,0),('L',1,0,0),('L',1,0,0),('X',address(),0,0),('M',address(),0,0),('R',address(),0,0),('W',2,address(),70),('A',25,0,0),('G',address(),0,0),('X',address(),0,0)]]
for i,tr in enumerate(traces):
 text=''.join(f'{o} {a} {b} {c}\n' for o,a,b,c in tr)
 p=subprocess.run([sys.argv[1]],input=text,text=True,capture_output=True,timeout=90)
 rows=[json.loads(x) for x in p.stdout.splitlines()]
 (root/f'{i}.json').write_text(json.dumps(dict(input=text,exit=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2))
 assert p.returncode==0,p.stderr
 expected=oracle(tr)
 for j,(x,y) in enumerate(zip(rows,expected)):assert x==y,(i,j,tr[j],x,y)
 assert len(rows)==len(expected)
# Mutation must produce a normal exit but disagree specifically on unknown-data publication.
tr=traces[1];text=''.join(f'{o} {a} {b} {c}\n' for o,a,b,c in tr)
p=subprocess.run([sys.argv[1],'publish_unknown'],input=text,text=True,capture_output=True,timeout=90)
(root/'mutation.json').write_text(json.dumps(dict(input=text,exit=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2))
assert p.returncode==0,p.stderr
rows=[json.loads(x) for x in p.stdout.splitlines()];expected=oracle(tr)
assert any(x['result']=='known' and y['result']=='unknown' for x,y in zip(rows,expected))
print('PASS 12 device traces, 128 physical mappings, directed invalid commands, unknown-data mutation detected')

for name,index in [('alias_die',0),('early_ready',1)]:
 tr=traces[index];text=''.join(f'{o} {a} {b} {c}\n' for o,a,b,c in tr)
 p=subprocess.run([sys.argv[1],name],input=text,text=True,capture_output=True,timeout=90)
 (root/(name+'.json')).write_text(json.dumps(dict(input=text,exit=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2))
 assert p.returncode==0,p.stderr
 rows=[json.loads(x) for x in p.stdout.splitlines()];assert rows!=oracle(tr)
print('PASS physical-die alias and premature RDY mutations detected')
