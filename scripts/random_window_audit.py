"""Independent event conservation and finite-window diagnostics; no acceptance relabeling."""
import bisect,collections,gzip,hashlib,json,pathlib,sys
SENSE=2720000

def load(path):
 with gzip.open(path,'rt') as f:return [json.loads(l) for l in f]

def clipped(intervals,a,b):
 return sum(max(0,min(y,b)-max(x,a)) for x,y in intervals)

def sweep(intervals,boundaries,limit):
 changes=collections.Counter()
 for a,b in intervals:
  assert 0<=a<=b
  changes[a]+=1;changes[b]-=1
 for t in boundaries:changes[t]+=0
 count=area=last=0;values={}
 for t,delta in sorted(changes.items()):
  area+=(t-last)*count;last=t
  if t in boundaries:values[t]=area
  count+=delta;assert 0<=count<=limit,'occupancy bound'
 assert count==0,'resource leak'
 return [values[b]-values[a] for a,b in zip(boundaries,boundaries[1:])]

def page_ownership(rows,addresses,requests):
 # Independently decode channel/die/bank from global 4KiB stripe position.
 locations=collections.defaultdict(list)
 by={r['id']-10000:r for r in requests}
 for i,address in enumerate(addresses):
  p=address//4096;bank=(p%16)*64+((p//256)%4)*16+(p//16)%16
  locations[bank,p//1024].append((i,by[i]))
 for entries in locations.values():
  ordered=sorted(entries,key=lambda v:v[1]['submit_ps'])
  assert all(a[1]['complete_ps']<=b[1]['submit_ps'] for a,b in zip(ordered,ordered[1:])), 'fixture has same-page parent overlap'
 owned=collections.Counter();cache=collections.defaultdict(list);residency=collections.defaultdict(list)
 for row in rows:
  if row.get('action')!='sense-issue':continue
  bank,page,t=row['bank'],row['page'],row['ps'];c=cache[bank]
  owners=[i for i,r in locations[bank,page] if r['submit_ps']<=t<=r['complete_ps']]
  assert len(owners)==1,'unowned or ambiguous sense';owned[owners[0]]+=1
  assert page not in [p for p,_ in c],'sense for FIFO-resident page'
  if len(c)==2:
   old,ready=c.pop(0);assert ready<=t;residency[bank,old].append((ready,t))
  c.append((page,t+SENSE))
 end=requests[-1]['complete_ps']
 for bank,c in cache.items():
  for page,ready in c:residency[bank,page].append((ready,end))
 hits=[]
 for (bank,page),entries in locations.items():
  for i,r in entries:
   assert owned[i]<=1
   if not owned[i]:
    assert any(max(a,r['submit_ps'])<=min(b,r['complete_ps']) for a,b in residency[bank,page]),'hit without ready resident page'
    hits.append({'request_index':i,'bank':bank,'page':page})
 return {'sense_free_parents':len(hits),'banks':sorted({h['bank'] for h in hits}),'hits':hits,'scope':'No same-page parent overlap; exact sense ownership; independent FIFO residency feasibility, not exact pin-release reconstruction'}

def analyze(rows,addresses,size,qd=128):
 assert rows and rows[-1]['kind']=='summary'
 req=[];live={};intervals=[];finish=[];last=0;sense_ids=set()
 for row in rows[:-1]:
  assert row['kind'] in ['request','sense']
  t=row['complete_ps'] if row['kind']=='request' else row['ps'];assert t>=last,'event reversal';last=t
  if row['kind']=='request':req.append(row);continue
  bank=row['bank'];assert 0<=bank<1024
  if row['action']=='sense-issue':
   assert bank not in live,'bank overlap';assert row['id'] not in sense_ids,'duplicate sense';sense_ids.add(row['id']);live[bank]=row
  else:
   assert row['action']=='sense-finish' and bank in live
   old=live.pop(bank);assert (old['id'],old['page'])==(row['id'],row['page'])
   assert t-old['ps']==SENSE,'sense duration';intervals.append((old['ps'],t));finish.append(t)
 assert not live
 n=len(addresses);assert len(req)==n and {r['id'] for r in req}==set(range(10000,10000+n))
 by={r['id']-10000:r for r in req}
 for i in range(n):
  assert by[i]['submit_ps']==(0 if i<qd else req[i-qd]['complete_ps']),'closed loop'
  assert by[i]['complete_ps']>=by[i]['submit_ps']
 s=rows[-1];assert (s['requests'],s['senses'],s['useful_bytes'],s['elapsed_ps'])==(n,len(intervals),n*size,req[-1]['complete_ps'])
 bounds=[0]+[req[k*3072-1]['complete_ps'] for k in range(1,5)]
 bank_area=sweep(intervals,bounds,1024);parent_intervals=[(r['submit_ps'],r['complete_ps']) for r in req]
 parent_area=sweep(parent_intervals,[0,s['elapsed_ps']],qd)[0]
 assert parent_area==sum(b-a for a,b in parent_intervals),'request residence conservation'
 windows=[]
 for i,(a,b) in enumerate(zip(bounds,bounds[1:])):
  mass=clipped(intervals,a,b);assert mass==bank_area[i],'independent area differential'
  # Completed service plus work already done in unfinished senses at the boundaries.
  age=lambda t:sum(t-x for x,y in intervals if x<t<y)
  finished=sum(a<y<=b for y in finish)
  assert mass==finished*SENSE+age(b)-age(a),'sense work conservation'
  rr=req[i*3072:(i+1)*3072]
  windows.append({'GBps':3072*size*1000/(b-a),'duration_ps':b-a,'average_busy_banks':mass/(b-a),'finished_senses':finished,'sense_work_page_equivalents':mass/SENSE,'unfinished_sense_work_start_ps':age(a),'unfinished_sense_work_end_ps':age(b),'completion_cohorts':dict(collections.Counter((r['id']-10000)//3072 for r in rr))})
 rates=[w['GBps'] for w in windows]
 return {'windows':windows,'first_four_pass_5pct':max(rates[1:])/min(rates[1:])<=1.05,'ratio_last_three':max(rates[1:])/min(rates[1:]),'terminal_drain_ps':s['elapsed_ps']-by[n-1]['submit_ps'],'requests':n,'sense_count':len(intervals),'parent_residence_ps':parent_area,'page_ownership':page_ownership(rows,addresses,req)}

def prefix_equal(baseline,extended,qd=128):
 a=[r for r in baseline if r['kind']=='request'];b=[r for r in extended if r['kind']=='request'];n=len(a)-qd
 assert a[:n]==b[:n],'completion prefix changed'
 cut=a[n-1]['complete_ps']
 assert [r for r in baseline if r['kind']=='sense' and r['ps']<cut]==[r for r in extended if r['kind']=='sense' and r['ps']<cut],'sense prefix changed'
 return {'identical_completions':n,'sense_prefix_before_ps':cut}

def main():
 base=pathlib.Path(sys.argv[1]);guard=pathlib.Path(sys.argv[2]);out=pathlib.Path(sys.argv[3]);out.mkdir(exist_ok=True,parents=True);results=[]
 for mode in ['service-v2','payload-v3']:
  for size in [256,4096]:
   stem=f'{mode}-{size}-3072-random';a=load(base/(stem+'.jsonl.gz'));b=load(guard/f'{mode}-{size}.jsonl.gz')
   addresses=list(map(int,gzip.open(base/(stem+'.input.gz'),'rt').read().split()));extra=list(map(int,gzip.open(guard/f'{mode}-{size}.input.gz','rt').read().split()))
   assert extra==addresses+addresses[:128]
   assert json.loads((guard/f'{mode}-{size}.status.json').read_text())['exit']==0
   results.append({'mode':mode,'size':size,'baseline':analyze(a,addresses,size),'guard':analyze(b,extra,size),'prefix':prefix_equal(a,b)})
 (out/'diagnosis.json').write_text(json.dumps({'cases':results,'acceptance_reclassified':False,'fit_performed':False,'performance_ready':False},indent=2))
 print([(x['mode'],x['size'],x['baseline']['ratio_last_three'],x['guard']['ratio_last_three']) for x in results])
if __name__=='__main__':main()
