"""AoU Appendix D independent bit-string oracle and bounded link contract."""
import pathlib,subprocess,json,random,sys
exe=str(pathlib.Path(sys.argv[1]).resolve());out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
def run(name,args,data=''):
 r=subprocess.run([exe]+args,input=data,text=True,capture_output=True,timeout=90)
 (out/(name+'.stdout')).write_text(r.stdout);(out/(name+'.stderr')).write_text(r.stderr)
 (out/(name+'.run.json')).write_text(json.dumps({'args':args,'exit':r.returncode}));assert r.returncode==0,r.stderr
 return r.stdout.splitlines()
def bits(n,x):
 if not 0<=x<2**n:raise ValueError()
 return f'{x:0{n}b}'
def wire(v):
 k,r,i,u,s,c,t,a=v
 if k==2: fields=[(4,k),(2,r),(2,0),(9,u),(3,0),(14,i),(3,6),(3,0),(8,0),(8,0),(8,s),(56,a)]
 elif k==4:fields=[(4,k),(2,r),(2,1),(9,u),(3,0),(14,i),(3,t),(1,1),(2,0)]+[(8,x) for x in range(64)]+[(8,s)]
 elif k==5:fields=[(4,k),(2,r),(2,s>>6),(9,u),(3,(s>>3)&7),(14,i),(3,t),(3,s&7)]
 else:fields=[(4,0),(3,7),(15,0),(2,r),(8,c),(8,s)]
 b=''.join(bits(n,x) for n,x in fields);return int(b,2).to_bytes(len(b)//8,'big').hex()
rng=random.Random(2308);vectors=[]
for k in [0,2,4,5]:
 for s in [0,1,127,254,255]+[rng.randrange(256) for _ in range(20)]:vectors.append([k,rng.randrange(4),rng.randrange(16384),rng.randrange(512),s,rng.randrange(256),rng.randrange(8),rng.randrange(2**56)])
expected=[wire(v) for v in vectors];actual=run('codec',['codec'],'\n'.join(' '.join(map(str,v)) for v in vectors)+'\n');assert actual==expected
# Decode reference fields independently; unused inputs were never transmitted.
decoded=run('decode',['decode'],'\n'.join(expected)+'\n')
for v,line in zip(vectors,decoded):
 k,r,i,u,s,c,t,a=v
 want=[k,r,i if k else 0,u if k else 0,s,c if not k else 0,t if k in [4,5] else 0,a if k==2 else 0]
 assert list(map(int,line.split()))==want
bad=[expected[25][:-2],expected[25]+'00','ff','0e00040000']
b=bytearray.fromhex(wire([2,0,42,0,0,0,0,0]));b[0]|=2;bad.append(b.hex())
b=bytearray.fromhex(wire([4,0,42,0,0,0,0,0]));b[0]&=0xfc;bad.append(b.hex())
assert run('malformed',['decode'],'\n'.join(bad)+'\n')==['rejected']*len(bad)
invalid=[[2,4,42,0,0,0,0,0],[2,0,16384,0,0,0,0,0],[2,0,42,512,0,0,0,0],[2,0,42,0,256,0,0,0],[2,0,42,0,0,0,0,2**56]]
assert run('range',['codec'],'\n'.join(' '.join(map(str,v)) for v in invalid)+'\n')==['rejected']*len(invalid)
v=(((7*0x9e3779b97f4a7c15)&((1<<64)-1))^2)%97+20
score=[sum((v+(k*32+j)%17-3)**2 for j in range(32)) for k in range(32)]
def check(row,t):
 assert row['type']==t and row['callbacks']==2 and row['drained']
 assert row['ambiguous_old_bytes'] is True,'hidden identity claim'
 assert row['performance_ready'] is False
 assert row['scores']==score,'distance mismatch'
for t in range(3):check(json.loads(run(f'flow-{t}',[str(t)])[0]),t)
for m,reason in [('bad_score','distance mismatch'),('pretend_sync_epoch','hidden identity claim')]:
 try:check(json.loads(run(m,['2',m])[0]),2)
 except AssertionError as e:assert str(e)==reason
 else:raise AssertionError('oracle mutation escaped')
print('PASS: 100 independent wire vectors, 11 malformed/range negatives, 3 driver/CUDA flows, 2 oracle mutants; arbitrary stale-byte ambiguity remains OPEN')
