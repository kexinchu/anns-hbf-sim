"""Independent specification/model-assumption microtrace checks (no donor imports)."""
import collections,copy,hashlib,json,pathlib,random,subprocess,sys
exe=pathlib.Path(sys.argv[1]).resolve();out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)

def check(row,pages,sense,bandwidth):
 events=row['events'];assert {e[3] for e in events}<={p%2 for p in pages}
 starts={e[2]:e for e in events if e[0]=='sense-issue'};ends={e[2]:e for e in events if e[0]=='sense-finish'}
 media={e[2]:e for e in events if e[0]=='sense-media-finish'}
 assert len(starts)==len(ends)==len(media)==row['senses'] and starts.keys()==ends.keys()==media.keys()
 bybank=collections.defaultdict(list)
 for identity,e in starts.items():
  f=ends[identity];m=media[identity];assert f[3]==m[3]==e[3] and m[1]-e[1]==sense and f[1]>=m[1]
  bybank[e[3]].append((e[1],f[1]))
 for intervals in bybank.values():
  intervals.sort();assert all(b[0]>=a[1] for a,b in zip(intervals,intervals[1:]))
 if bandwidth:
  assert len(row['core'])==row['senses'];last={}
  assert sorted(x[2] for x in row['core'])==sorted(x[1] for x in media.values())
  assert sorted(x[4] for x in row['core'])==sorted(x[1] for x in ends.values())
  for ch,core,arrival,start,end in row['core']:
   assert end-start==(4096000+bandwidth-1)//bandwidth
   assert start==max(arrival,last.get((ch,core),0));last[ch,core]=end
  assert row['elapsed_ps']>=max(last.values(),default=0)
 else:
  assert row['core']==[]
  assert all(ends[k][1]==m[1] for k,m in media.items())
 assert row['elapsed_ps']>0 and row['elapsed_ps']>=max((e[1] for e in ends.values()),default=0)

def run(name,phases,sense=2720000,bandwidth=0,policy="fifo"):
 data=''.join(str(len(p))+' '+' '.join(map(str,p))+'\n' for p in phases)
 r=subprocess.run([str(exe),str(sense),str(bandwidth),policy],input=data,text=True,capture_output=True,timeout=60)
 (out/(name+'.input')).write_text(data);(out/(name+'.jsonl')).write_text(r.stdout);(out/(name+'.stderr')).write_text(r.stderr)
 assert r.returncode==0,r.stderr
 rows=[json.loads(x) for x in r.stdout.splitlines()];assert len(rows)==len(phases)
 for i,(row,pages) in enumerate(zip(rows,phases)):assert row['phase']==i;check(row,pages,sense,bandwidth)
 return rows

# Independent bounded FIFO/LRU references for quiescent phases. FIFO implements
# the OCP third-page example; the example is not a universal replacement mandate.
phases=[[0],[2],[0],[4],[0],[2]]
rng=random.Random(1729);phases += [[rng.randrange(6)] for _ in range(256)]
for policy in ['fifo','lru']:
 rows=run('cache-'+policy,phases,policy=policy);cache=collections.defaultdict(list)
 for row,(page,) in zip(rows,phases):
  bank=page%2;hit=page in cache[bank]
  assert row['senses']==int(not hit),(policy,row,page,cache)
  if hit:
   if policy=='lru':cache[bank].remove(page);cache[bank].append(page)
  else:
   if len(cache[bank])==2:cache[bank].pop(0)
   cache[bank].append(page)
# Default policy must agree with explicit FIFO, and invalid names fail closed.
data=''.join('1 '+str(p[0])+'\n' for p in phases)
default=subprocess.run([str(exe),'2720000','0'],input=data,text=True,capture_output=True,timeout=60)
assert default.returncode==0 and default.stdout==(out/'cache-fifo.jsonl').read_text()
invalid=subprocess.run([str(exe),'2720000','0','unknown'],input='1 0\n',text=True,capture_output=True,timeout=60)
assert invalid.returncode!=0 and 'cache policy must be' in invalid.stderr
# Cold independent vs same-bank requests, and duplicate in-flight page requests.
for name,pages,expected in [('same-page',[0,0],1),('same-bank',[0,2],2),('different-bank',[0,1],2)]:
 row=run(name,[pages])[0];assert row['senses']==expected
 if name=='different-bank':
  starts=[x[1] for x in row['events'] if x[0]=='sense-issue'];ends=[x[1] for x in row['events'] if x[0]=='sense-finish'];assert max(starts)<min(ends)
# Keep external nominal time distinct from sensitivity probes. Unloaded single
# miss must shift exactly by delta sense; a buffered hit must be unaffected.
a=run('sense-a',[[0],[0]],100000);b=run('sense-b',[[0],[0]],4000000)
assert b[0]['elapsed_ps']-a[0]['elapsed_ps']==3900000
assert b[1]['elapsed_ps']==a[1]['elapsed_ps']
for bandwidth in [8,16]:run('finite-core-'+str(bandwidth),[[0,1],[2,3],[4,5]],100000,bandwidth)
# Deliberately corrupt mechanism evidence; each checker must reject its fault.
base=run('negative-reference',[[0,2]],100000,8)[0];bad=[]
x=copy.deepcopy(base);x['senses']+=1;bad.append(x)
x=copy.deepcopy(base);next(e for e in x['events'] if e[0]=='sense-finish')[1]-=1;bad.append(x)
x=copy.deepcopy(base);x['core'][1][3]=x['core'][0][3];bad.append(x)
x=copy.deepcopy(base);x['elapsed_ps']=1;bad.append(x)
x=copy.deepcopy(base);x['events'][0][3]=1;bad.append(x)
for x in bad:
 try:check(x,[0,2],100000,8)
 except AssertionError:pass
 else:raise AssertionError('accepted corrupted mechanism evidence')
summary={'cache_reference_phases':2*len(phases),'directed_runs':8,'corrupt_traces_rejected':len(bad),'binary_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'independent_scope':'quiescent two-slot FIFO and opt-in LRU, event causality, bank exclusion/overlap, core FIFO serialization, sense sensitivity','not_proven':['OCP full compliance','physical sense timing','paper throughput reproduction','ANNS design benefit'],'performance_ready':False}
(out/'verdict.json').write_text(json.dumps(summary,indent=2));print(summary)
