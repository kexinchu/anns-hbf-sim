"""Independent cycle interpreter + timing invariant checker for declared bank model.
Synthetic cycles; not a JEDEC or OCP HBM specification. No C++/donor state imported.
"""
import json,random,subprocess,sys,pathlib,uuid
from collections import deque

def reference(inputs):
    queues=[deque() for _ in range(4)];rows=[None]*4
    col=[0]*4;pre=[0]*4;act=[0]*4;history=[];pending=[]
    bus=column=activate=0;direction=None;used=0;idx=0;out=[]
    for tick in range(10000):
        while idx<len(inputs) and inputs[idx][0]==tick:
            at,i,b,r,w=inputs[idx];idx+=1
            accepted=used<8;out.append([tick,i,b,r,'ACCEPT' if accepted else 'REJECT'])
            if accepted:queues[b].append((at,i,b,r,w));used+=1
        for end,q in list(pending):
            if end==tick:
                _,i,b,r,w=q;out.append([tick,i,b,r,'DONE']);pending.remove((end,q));used-=1
        history=[v for v in history if v+8>tick];choices=[]
        for b,q in enumerate(queues):
            if not q:continue
            at,i,_,r,w=q[0];kind=None
            if rows[b] is None:
                if tick>=max(act[b],activate) and len(history)<4:kind='ACT'
            elif rows[b]!=r:
                if tick>=pre[b]:kind='PRE'
            elif tick>=max(col[b],column) and tick+(3 if w else 4)>=bus+(2 if direction is not None and direction!=w else 0):kind='WR' if w else 'RD'
            if kind:
                aged=tick-at>=32
                choices.append(((0 if aged else 1,0 if aged else {'RD':0,'WR':0,'ACT':1,'PRE':2}[kind],at,i,b),kind,q[0]))
        if choices:
            _,kind,q=min(choices);at,i,b,r,w=q;out.append([tick,i,b,r,kind])
            if kind=='ACT':rows[b]=r;col[b]=tick+4;pre[b]=tick+8;act[b]=tick+12;activate=tick+2;history.append(tick)
            elif kind=='PRE':rows[b]=None;act[b]=max(act[b],tick+4)
            else:
                end=tick+(3 if w else 4)+2;bus=end;column=tick+2;direction=w
                pre[b]=max(pre[b],end+3 if w else tick+2);pending.append((end,q));queues[b].popleft()
        if idx==len(inputs) and used==0:return out
    raise AssertionError('reference failed to drain')

def invariants(trace):
    live={};issued={};done=set();commands=set();bus=[];opened={};act_times={}
    pre_floor={};act_floor={};acts=[];last_column=-2;last_end=0;last_direction=None
    for t,i,b,r,op in trace:
        if op=='ACCEPT':
            if i in live or len(live)>=8:raise AssertionError('admission conservation')
            live[i]=t
        elif op=='REJECT':continue
        elif op=='DONE':
            if i not in issued or t!=issued[i] or i in done:raise AssertionError('invalid completion')
            del live[i];done.add(i)
        else:
            if i not in live or t<live[i] or t in commands:raise AssertionError('causality/command bus')
            commands.add(t)
            if op=='ACT':
                if b in opened or t<act_floor.get(b,0) or (acts and t<acts[-1]+2) or sum(x+8>t for x in acts)>=4:raise AssertionError('ACT timing')
                opened[b]=r;act_times[b]=t;pre_floor[b]=t+8;act_floor[b]=t+12;acts.append(t)
            elif op=='PRE':
                if b not in opened or t<pre_floor[b]:raise AssertionError('PRE timing')
                opened.pop(b);act_floor[b]=max(act_floor[b],t+4)
            else:
                if opened.get(b)!=r or t<act_times[b]+4:raise AssertionError('row/tRCD')
                start=t+(3 if op=='WR' else 4);end=start+2
                gap=2 if last_direction is not None and last_direction!=op else 0
                if t<last_column+2 or start<last_end+gap:raise AssertionError('column/turnaround timing')
                last_column=t;last_end=end;last_direction=op
                pre_floor[b]=max(pre_floor[b],end+3 if op=='WR' else t+2)
                bus.append((start,end));issued[i]=end
    if live:raise AssertionError('leaked credit')
    bus.sort()
    if any(a[1]>b[0] for a,b in zip(bus,bus[1:])):raise AssertionError('data bus overlap')

cases=[[(0,1,0,0,0)],[(0,1,0,0,0),(0,2,1,0,0)],[(0,1,0,0,0),(1,2,0,1,1),(2,3,1,0,0)]]
for seed in range(32):
    rng=random.Random(seed)
    cases.append(sorted([(rng.randrange(80),i,rng.randrange(4),rng.randrange(3),rng.randrange(2)) for i in range(1,81)]))
out=pathlib.Path(sys.argv[2])/uuid.uuid4().hex if len(sys.argv)>2 else None
if out:out.mkdir(parents=True)
for number,case in enumerate(cases):
    p=subprocess.run([sys.argv[1]],input='\n'.join(' '.join(map(str,r)) for r in case)+'\n',capture_output=True,text=True,check=True,timeout=30)
    actual=[json.loads(x) for x in p.stdout.splitlines()];expected=reference(case)
    if out:
        (out/f'{number}.json').write_text(json.dumps({'input':case,'actual':actual,'expected':expected}))
    if actual!=expected:raise AssertionError((number,actual,expected))
    invariants(actual)
    broken=[x[:] for x in actual];next(x for x in broken if x[4]=='DONE')[0]-=1
    try:invariants(broken)
    except AssertionError:pass
    else:raise AssertionError('early completion mutation escaped')
if reference(cases[0])[-1][0]!=10:raise AssertionError('cold analytic ACT+RCD+CL+burst')
parallel=reference(cases[1]);acts=[x[0] for x in parallel if x[4]=='ACT']
if acts!=[0,2] or parallel[-1][0]!=12:raise AssertionError('bank overlap analytic')
print(json.dumps({'status':'PASS','traces':len(cases),'negative_cases':len(cases),'scope':'SYNTHETIC_BANK_COMMAND_MODEL','performance_ready':False}))

for invalid in ('0 1 4 0 0\n','1 1 0 0 0\n0 2 0 0 0\n','0 1 0 0 0\n0 1 1 0 0\n'):
    bad=subprocess.run([sys.argv[1]],input=invalid,text=True,capture_output=True,timeout=30)
    if bad.returncode==0:raise AssertionError('invalid bank/order/identity accepted')
