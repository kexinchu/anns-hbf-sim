"""Independent successful host replay of whole-page writes; OCP 11.5.2.6-8.
Probe actions E/P/F/U/D are external environment actions, not wire opcodes.
"""
import json,pathlib,subprocess,sys
class Ref:
    def __init__(self):
        self.seq=0;self.live={};self.reply={};self.pending={};self.media={}
        self.physical=0;self.next=0;self.replay=None;self.failed=False;self.unusable=False;self.spares=1;self.retired=False
    def step(self,line):
        op,p,v=line.split();p=int(p);v=int(v);a='none'
        def response(i,status,info=0,data=None):self.reply[i]=[i,self.live[i],status,info,data]
        if op in ('W','R'):
            self.seq+=1;i=self.seq
            if self.failed and self.reply:a='backpressured'
            elif op=='W' and not self.failed and self.replay is not None and p>self.replay:a='backpressured'
            else:
                a='accepted';self.live[i]=op
                if self.retired:response(i,1)
                elif op=='R':
                    if p in self.media:response(i,0,data=self.media[p])
                    else:raise NotImplementedError('read before recovery completes')
                elif self.failed and p!=0:response(i,6,2)
                elif self.failed and self.unusable and not self.spares:
                    self.retired=True;response(i,8,1) # Table 13: NAND-block granularity
                else:
                    if self.failed:
                        if self.unusable:self.spares-=1;self.physical=2
                        self.failed=False;self.unusable=False;self.media={};self.next=0
                    if p!=self.next:response(i,6,1)
                    else:self.pending[p]=(i,v);self.next+=1
        elif op in ('P','F','U'):
            i,v=self.pending.pop(p)
            if op=='P':
                self.media[p]=v;response(i,0)
                if self.replay==p:self.replay=None
            else:
                response(i,7);self.replay=max(p,self.replay if self.replay is not None else p);self.failed=True;self.unusable=op=='U'
                for q,(j,_) in list(self.pending.items()):
                    if q>p:response(j,6,2);del self.pending[q]
        elif op=='D':
            for i in self.reply:del self.live[i]
            self.reply={}
        elif op=='E':pass
        else:raise ValueError(op)
        return {'acceptance':a,'outstanding':len(self.live),'responses':sorted(self.reply.values()),'physical_block':None if self.retired else self.physical}
def compare(a,e):
    if len(a)!=len(e):raise AssertionError('missing receipt')
    for n,(x,y) in enumerate(zip(a,e)):
        x=dict(x,responses=sorted(x['responses']))
        if x!=y:raise AssertionError((n,x,y))
def trace(failed,hard,repeated=False):
    ops=[]
    for p in range(failed):ops += [f'W {p} {10+p}','E 0 0',f'P {p} 0','D 0 0']
    ops += [f'W {failed} {10+failed}',f'W {failed+1} {11+failed}',f'W {failed+2} {12+failed}','E 0 0',f'{"U" if hard else "F"} {failed} 0','W 0 99','D 0 0',f'W {failed+1} 99','D 0 0']
    if repeated:ops += ['W 0 10','E 0 0','F 0 0','D 0 0']
    for p in range(failed+2):
        ops += [f'W {p} {10+p}','E 0 0']
        if p==failed:ops += [f'W {p+1} 999'] # cannot resume beyond replay prefix yet
        ops += [f'P {p} 0','D 0 0']
    for p in range(failed+2):ops += [f'R {p} 0','D 0 0']
    if hard:
        p=failed+2;ops += [f'W {p} 42',f'U {p} 0','D 0 0','W 0 99','D 0 0','W 0 99','D 0 0']
    return ops
out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=False)
cases=[(p,h,False) for p in (0,1,3) for h in (False,True)]+[(3,False,True)]
for page,hard,repeated in cases:
    ops=trace(page,hard,repeated);ref=Ref();expected=[ref.step(x) for x in ops]
    p=subprocess.run([sys.argv[1]],input='\n'.join(ops)+'\n',text=True,capture_output=True,timeout=30)
    tag=f'{page}-{hard}-{repeated}';(out/(tag+'.input')).write_text('\n'.join(ops));(out/(tag+'.actual')).write_text(p.stdout);(out/(tag+'.stderr')).write_text(p.stderr);(out/(tag+'.expected')).write_text(json.dumps(expected))
    if p.returncode:raise RuntimeError(p.stderr)
    actual=[json.loads(x) for x in p.stdout.splitlines()];compare(actual,expected)
    bad=json.loads(json.dumps(actual));next(r for x in bad for r in x['responses'] if r[2]==7)[2]=0
    try:compare(bad,expected)
    except AssertionError:pass
    else:raise AssertionError('false success escaped')
    for field in ('physical_block','outstanding'):
        bad=json.loads(json.dumps(actual));bad[0][field]=999
        try:compare(bad,expected)
        except AssertionError:pass
        else:raise AssertionError('mapping/credit mutation escaped')
print(json.dumps({'status':'PASS','recovery_traces':len(cases),'performance_ready':False}))
