"""Independent specification subset. No donor imports or donor-produced expected answers.
OCP 0.7: 5.3.1, 5.4.1, 5.4.3, Tables 12/13, 5.9.2.
Scope: one channel/bank; initial sequential pages; unordered IDs; explicit timeout drain; no remap/ECC.
P is explicit successful media completion, D is explicit response acceptance.
"""
import argparse,json,pathlib,random,subprocess
class Reference:
    def __init__(self):
        self.erase_pending=False;self.erase_started=False;self.serial=0;self.live={};self.responses={};self.partial={};self.media={};self.ordered=[];self.deferred={}
    def step(self,line,i):
        op,addr,val=line.split();addr=int(addr);val=int(val);acceptance='none'
        if op in ('R','W','Q'):
            self.serial+=1;ident=self.serial
            if len(self.live)==256: acceptance='backpressured'
            elif addr%64: acceptance='invalid_api'
            elif op in ('R','Q') and addr<65536 and self.erase_pending and addr//4096 not in self.partial:
                acceptance='backpressured' # declared adapter policy during auto-erase
            else:
                acceptance='accepted';ordered=op=='Q';op='R' if ordered else op;self.live[ident]=op
                if ordered:self.ordered.append(ident)
                page,slot=divmod(addr//64,64)
                def response(status,data=None):
                    target=self.deferred if ordered and self.ordered[0]!=ident else self.responses
                    target[ident]=[ident,op,status,data]
                if addr>=65536:response(1)
                elif op=='R':
                    if page in self.partial:
                        response(0,self.partial[page][slot][1]) if slot in self.partial[page] else response(10)
                    elif page in self.media:response(0,self.media[page][slot])
                    else:response(7)
                elif page in self.media:raise NotImplementedError('committed-page rewrite outside reference subset')
                elif page not in self.partial and page!=len(self.media):raise NotImplementedError('nonsequential write outside reference subset')
                elif slot in self.partial.get(page,{}):response(2)
                else:
                    if page==0 and not self.erase_started:
                        self.erase_pending=True;self.erase_started=True
                    self.partial.setdefault(page,{})[slot]=(ident,val)
        elif op=='P':
            self.erase_pending=False
            for page,fragments in list(self.partial.items()):
                if len(fragments)==64:
                    self.media[page]={s:v for s,(_,v) in fragments.items()}
                    for ident,_ in fragments.values():self.responses[ident]=[ident,'W',0,None]
                    del self.partial[page]
        elif op=='T':
            for page, fragments in list(self.partial.items()):
                if len(fragments)<64:
                    for ident,_ in fragments.values(): self.responses[ident]=[ident,'W',5,None]
                    del self.partial[page]
        elif op=='D':
            for ident in self.responses:
                self.live.pop(ident)
                if ident in self.ordered:self.ordered.remove(ident)
            self.responses={}
            if self.ordered and self.ordered[0] in self.deferred:
                ident=self.ordered[0];self.responses[ident]=self.deferred.pop(ident)
        else:raise ValueError(op)
        return dict(step=i,acceptance=acceptance,outstanding=len(self.live),responses=sorted(self.responses.values()))
def compare(actual,expected):
    if len(actual)!=len(expected):raise AssertionError('receipt count')
    for i,(a,e) in enumerate(zip(actual,expected)):
        a=dict(a,responses=sorted(a['responses']))
        if a!=e:raise AssertionError(f'step {i}: actual {a}, expected {e}')
def workload(seed):
    r=random.Random(seed);ops=['R 0 0','R 65536 0','D 0 0','R 1 0','W 1 7']
    # Timeout destroys the incomplete generation, but credits last until D.
    # A retry must not inherit old fragments or expose stale data.
    for attempt in range(3):
        slots=r.sample(range(64),r.randrange(1,32))
        ops += [f'W {s*64} {seed*1000+s}' for s in slots]
        ops += ['T 0 0','R 0 0','P 0 0','R 0 0','D 0 0']
    for page in range(3):
        slots=list(range(64));r.shuffle(slots)
        for j,s in enumerate(slots):
            ops.append(f'W {page*4096+s*64} {seed*10000+page*100+s}')
            if j%7==0:
                ops += [f'R {page*4096+s*64} 0',f'R {page*4096+r.randrange(64)*64} 0',f'W {page*4096+s*64} 999','D 0 0']
            if j==31:ops+=['P 0 0'] # incomplete pages cannot program/ack success
        ops+=['P 0 0','D 0 0']
        for _ in range(40):ops.append(f'R {r.randrange(page+1)*4096+r.randrange(64)*64} 0')
        ops+=['D 0 0']
    # Exhaust credit with unconsumed read responses; then release and recover.
    ops+=['Q 0 0','Q 64 0','Q 128 0','D 0 0','D 0 0','D 0 0']
    ops+=['R 0 0']*258+['D 0 0','R 0 0','D 0 0']
    return ops
def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=False)
    cases=[]
    for seed in range(16):
        ops=workload(seed);ref=Reference();expected=[ref.step(x,i) for i,x in enumerate(ops)]
        run=subprocess.run([a.binary],input='\n'.join(ops)+'\n',text=True,capture_output=True,timeout=30)
        (out/f'{seed}.input').write_text('\n'.join(ops)+'\n');(out/f'{seed}.actual.jsonl').write_text(run.stdout);(out/f'{seed}.stderr').write_text(run.stderr)
        (out/f'{seed}.expected.json').write_text(json.dumps(expected))
        if run.returncode:raise RuntimeError(run.stderr)
        actual=[json.loads(x) for x in run.stdout.splitlines()];compare(actual,expected)
        # Ensure the differential checker detects a status/credit/data mutation.
        for field in ('outstanding','responses'):
            mutated=json.loads(json.dumps(actual));mutated[0][field]=999 if field=='outstanding' else [[1,'R',0,123]]
            try:compare(mutated,expected)
            except AssertionError:pass
            else:raise AssertionError('mutation escaped')
        mutated=json.loads(json.dumps(actual))
        for row in mutated:
            found=next((x for x in row['responses'] if x[1]=='R' and x[2]==0),None)
            if found is not None:found[3]^=1;break
        try:compare(mutated,expected)
        except AssertionError:pass
        else:raise AssertionError('payload mutation escaped')
        cases.append({'seed':seed,'commands_and_control_steps':len(ops),'matched':True})
    report={'status':'PASS','cases':cases,'scope':'READ_WRITE_ASSEMBLY_TIMEOUT_RETRY_CREDIT_EXPLICIT_ID_GROUP_SUBSET','performance_ready':False}
    (out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':main()
