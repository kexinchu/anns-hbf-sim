"""Independent Python transition oracle and integer-distance/top-k oracle.
Held streams make pending observations deterministic; opened events are waited.
No C++ state or simulator output is used to generate expected answers.
"""
import copy,json,pathlib,random,subprocess,sys,uuid
class Reference:
 def __init__(self):
  self.f=[[-1,0,'free',0,0] for _ in range(2)];self.v={};self.fill={};self.lease={};self.write={};self.blocked=set();self.values={};self.backing={}
 def free(self,i):self.f[i]=[-1,0,'free',0,0]
 def apply(self,line):
  op,*raw=line.split();a,b,c,d=(list(map(int,raw))+[0]*4)[:4];r='invalid';gpu=[]
  if op=='fill':
   if a>=0 and 0<=b<8 and a not in self.fill:
    if b//4 in self.blocked:r='blocked'
    else:
     g=self.v.setdefault(b,1)
     if any(p==b and gen==g and st!='free' for p,gen,st,_,_ in self.f):r='busy'
     elif all(f[2]!='free' for f in self.f):r='full'
     else:
      i=next(i for i,f in enumerate(self.f) if f[2]=='free');self.f[i]=[b,g,'filling',0,0];self.values[i]=c;self.fill[a]=[i,bool(d),True];r='accepted'
  elif op=='publish' and a in self.fill and self.fill[a][2]:
   i,held,_=self.fill[a]
   if held:r='pending'
   else:
    self.fill[a][2]=False
    if self.f[i][1]!=self.v[self.f[i][0]]:self.free(i);r='stale'
    else:self.f[i][2]='ready';r='ready'
  elif op=='refresh':
   if 0<=a<8:
    if a//4 in self.blocked:r='blocked'
    elif any(f[0]==a and (f[2]=='writeback' or f[4]) for f in self.f):r='busy'
    else:
     self.v[a]=self.v.get(a,1)+1;r='refreshed'
     for i,f in enumerate(self.f):
      if f[0]==a and f[2]!='free':
       if f[2] in ('filling','retired_fill'):f[2]='retired_fill'
       elif f[3]:f[2]='retired'
       else:self.free(i)
  elif op=='acquire':
   if a>=0 and 0<=b<8 and a not in self.lease:
    if b//4 in self.blocked:r='blocked'
    else:
     self.v.setdefault(b,1);r='unavailable'
     for i,f in enumerate(self.f):
      if f[:3]==[b,self.v[b],'ready']:
       f[3]+=1;self.lease[a]=[i,bool(c),True,self.values[i]];r='acquired';break
  elif op=='release' and a in self.lease and self.lease[a][2]:
   i,held,_,value=self.lease[a]
   if held:r='pending'
   else:
    self.lease[a][2]=False;self.f[i][3]-=1
    if self.f[i][3]==0 and self.f[i][2]=='retired':self.free(i)
    scores=[sum((value+(k*32+j)%17-3)**2 for j in range(32)) for k in range(32)]
    gpu=scores+sorted(range(32),key=lambda k:(scores[k],k))[:10];r='released'
  elif op in ('dirty','evict','writeback'):
   r='unavailable'
   for i,f in enumerate(self.f):
    if f[0]!=a or f[2]!='ready':continue
    if op!='evict' and a//4 in self.blocked:r='blocked'
    elif f[3] or (op=='evict' and f[4]):r='busy'
    elif op=='dirty':f[4]=1;r='dirty'
    elif op=='evict':self.free(i);r='evicted'
    elif not f[4]:r='clean'
    else:f[2]='writeback';self.write[a]=[i,bool(b),True,self.values[i]];r='writing'
    break
  elif op=='commit' and a in self.write:
   i,held,_,value=self.write[a]
   if self.f[i][0]==a and self.f[i][2]=='writeback':
    if held:r='pending'
    else:
     self.f[i][2]='ready';r='committed' if c else 'failed'
     if c:self.f[i][4]=0;self.backing[a]=[a,value,value+1023%17]
  elif op=='block' and 0<=a<2:
   if b:self.blocked.add(a)
   else:self.blocked.discard(a)
   r='blocked' if b else 'resumed'
  elif op=='open':
   group=self.fill if a==0 else self.lease if a==1 else self.write
   if b in group:group[b][1]=False;r='opened'
  return copy.deepcopy(dict(result=r,frames=self.f,gpu=gpu,backing=[self.backing[k] for k in sorted(self.backing)]))

def cases(value=10):
 return {
 'late_response':[f'fill 1 0 {value} 1','publish 1 0','refresh 0',f'fill 2 0 {value+100} 0','publish 2 1','acquire 1 0 0','release 1 1','open 0 1','publish 1 1','publish 1 1','acquire 2 0 0','release 2 1'],
 'refresh_reader':[f'fill 1 0 {value} 0','publish 1 1','acquire 1 0 1','refresh 0',f'fill 2 0 {value+100} 0','publish 2 1','release 1 0',f'fill 3 2 {value} 0','acquire 2 0 0','release 2 1','open 1 1','release 1 1','release 1 1',f'fill 3 2 {value} 0','publish 3 1'],
 'writeback_failure':[f'fill 1 0 {value} 0','publish 1 1','dirty 0','refresh 0','writeback 0 1','commit 0 0 0','refresh 0','acquire 1 0 0','open 2 0','commit 0 1 0','evict 0','acquire 1 0 0','release 1 1','writeback 0 0','commit 0 1 1','evict 0'],
 'writeback_new_generation':[f'fill 1 0 {value} 0','publish 1 1','acquire 1 0 1','refresh 0',f'fill 2 0 {value+100} 0','publish 2 1','dirty 0','writeback 0 0','commit 0 1 1','open 1 1','release 1 1','acquire 2 0 0','release 2 1'],
 'die_isolation':[f'fill 1 0 {value} 0','publish 1 1',f'fill 2 4 {value+20} 0','publish 2 1','acquire 1 0 1','block 0 1','acquire 2 0 0','refresh 0','dirty 0',f'fill 3 1 {value} 0','acquire 3 4 0','release 3 1','open 1 1','release 1 1','block 0 0','acquire 2 0 0','release 2 1'],
 }
def varied(seed):
 rng=random.Random(seed);lines=cases(rng.randrange(20,200))
 # Move old completion across the new read while preserving controlled waits.
 if seed%2:
  x=lines['late_response'];x.remove('open 0 1');x.remove('publish 1 1');k=x.index('acquire 1 0 0');x[k:k]=['open 0 1','publish 1 1']
 if seed%3:
  x=lines['refresh_reader'];x.remove('open 1 1');x.remove('release 1 1');k=x.index('acquire 2 0 0');x[k:k]=['open 1 1','release 1 1']
 if seed%2:
  x=lines['die_isolation'];k=x.index('block 0 0');x[k:k]=['acquire 7 0 0','writeback 0 0']
 return lines

def run(binary,lines,args=()):
 p=subprocess.run([binary,*args],input='\n'.join(lines)+'\n',text=True,capture_output=True,timeout=30)
 if p.returncode:raise AssertionError(p.stderr)
 return p,[json.loads(x) for x in p.stdout.splitlines()]
def main():
 binary=sys.argv[1];out=pathlib.Path(sys.argv[2])/uuid.uuid4().hex;out.mkdir(parents=True,exist_ok=False);count=0
 for seed in range(5):
  value=random.Random(seed).randrange(10,200)
  for name,lines in varied(seed).items():
   ref=Reference();expected=[ref.apply(s) for s in lines];p,actual=run(binary,lines)
   (out/f'{seed}-{name}.json').write_text(json.dumps(dict(input=lines,expected=expected,actual=actual,stderr=p.stderr),indent=2))
   assert actual==expected,(seed,name,next((i,x,y) for i,(x,y) in enumerate(zip(actual,expected)) if x!=y))
   count+=1
 # Real mutation of bytes copied to GPU, not alteration of expected answers.
 lines=cases()['refresh_reader'];ref=Reference();expected=[ref.apply(s) for s in lines]
 p,bad=run(binary,lines,['corrupt_fill']);(out/'corrupt-fill.json').write_text(json.dumps(dict(input=lines,actual=bad,expected=expected),indent=2))
 assert len(bad)==len(expected) and any(x['gpu']!=y['gpu'] for x,y in zip(bad,expected))
 print(json.dumps(dict(status='PASS',backend=sys.argv[3] if len(sys.argv)>3 else 'CUDA',traces=count,corrupt_fill_rejected=True,performance_ready=False)))
if __name__=='__main__':main()
