"""Independent schedule/ledger oracle; imports no simulator code.
Not a second implementation of PCIe's full retry state machine.
"""
import json,pathlib,subprocess,sys,random
trace,probe=map(lambda x:str(pathlib.Path(x).resolve()),sys.argv[1:3]);out=pathlib.Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=True)
def run(name,exe,args=(),stdin=''):
 r=subprocess.run([exe,*args],input=stdin,text=True,capture_output=True,timeout=90)
 for suffix,value in [('stdin',stdin),('stdout',r.stdout),('stderr',r.stderr)]: (out/(name+'.'+suffix)).write_text(value)
 (out/(name+'.run.json')).write_text(json.dumps({'args':list(args),'exit':r.returncode}))
 assert r.returncode==0,(name,r.stderr)
 return r.stdout
class Schedule:
 def __init__(self):self.ops=[];self.checks=[]
 def add(self,op,ok=1,**fields):
  self.ops.append(op);self.checks.append({0:ok,**{int(k):v for k,v in fields.items()}})
 def at(self,index,value):self.checks[-1][index]=value
 def boot(self):
  for e in (0,1):self.add(f'req {e} 1');self.add(f'sts {e}',0)
  self.add('tick')
  for e in (0,1):self.add(f'sts {e}');self.add(f'state {e} 1')
 def close(self,state=3):
  for e in (0,1):
   self.add(f'req {e} 0');self.add(f'state {e} {state}',0);self.add(f'sts {e}');self.add(f'state {e} {state}')
 def verify(self,name):
  rows=[list(map(int,l.split())) for l in run(name,trace,stdin='\n'.join(self.ops)+'\n').splitlines()]
  assert len(rows)==len(self.checks)
  for op,row,want in zip(self.ops,rows,self.checks):
   assert len(row)==26
   assert all(row[k]==v for k,v in want.items()),(name,op,row,want)
   # conservation bounds independently checked at EVERY step
   assert all(0<=row[i]<=8 for i in (13,14,15,16,22,23,24,25))
  return rows
# 300 unique payloads cross the reserved-zero sequence wrap; every seventh
# loses an ACK, every eleventh experiences corruption. Ordered payload ledger.
s=Schedule();s.boot();accepted=crc=dup=0
for i in range(300):
 seq=i%255+1;s.add(f'send 0 {i%251}');s.at(11,(i+1)%255+1);s.add('launch 0')
 if i%11==0:
  crc+=1;s.add('arrive 0 1');s.at(5,crc);s.add('consume 1',0);s.add('replay 0');s.add('launch 0')
 s.add('arrive 0');accepted+=1;s.at(3,accepted);s.add('consume 1');s.at(1,i%251)
 if i%7==0:
  s.add('replay 0');s.add('launch 0');s.add('arrive 0');dup+=1;s.at(6,dup);s.add('consume 1',0)
 s.add(f'ack 0 {seq}');s.at(13,0);s.add(f'ack 0 {seq}',0)
s.verify('wrap-retry')
# Capacity, bad ACK, no receiver readiness, and Retrain preserves retries.
s=Schedule();s.add('send 0 1',0);s.add('sts 0',0);s.add('state 0 1',0);s.boot()
for i in range(8):s.add(f'send 0 {i}')
s.add('send 0 9',0);s.add('ack 0 0',0);s.add('ack 0 9',0);s.add('reset',0)
s.close(2);s.add('clean 0',0);s.at(13,8);s.add('reset',0)
# Receive handshake while Retrain; cannot bypass its one-cycle latency.
s.boot();s.at(13,8)
for i in range(8):s.add('launch 0');s.add('arrive 0');s.add('consume 1');s.at(1,i)
s.add('ack 0 8');s.at(13,0);s.verify('capacity-retrain')
# ACKed transport may still be waiting for protocol consumption. A full RX
# queue stalls modeled flight, preserving its payload until space exists.
s=Schedule();s.boot()
for i in range(8):
 s.add(f'send 0 {i}');s.add('launch 0');s.add('arrive 0');s.add(f'ack 0 {i+1}')
s.add('send 0 99');s.add('launch 0');s.add('arrive 0',0);s.at(16,1);s.at(24,8)
s.add('consume 1');s.at(1,0);s.add('arrive 0');s.at(16,0)
for i in range(1,8):s.add('consume 1');s.at(1,i)
s.add('consume 1');s.at(1,99);s.add('ack 0 9');s.verify('rx-backpressure')
# 36 seeded reset schedules: backlog, partial launch, partial arrival. Oracle
# tracks item counts instead of copying production reset/queue algorithms.
r=random.Random(2302)
for case in range(36):
 n=r.randrange(1,9);launched=r.randrange(n+1);received=r.randrange(launched+1)
 s=Schedule();s.boot()
 for i in range(n):s.add(f'send 1 {i+1}')
 for i in range(launched):s.add('launch 1')
 for i in range(received):s.add('arrive 1')
 s.add('reset',0);s.close(3 if case%2==0 else 4);s.add('send 1 99',0);s.add('replay 1',0);s.add('ack 1 1',0);s.add('consume 0',0);s.add('reset',0)
 for i in range(launched-received):s.add('arrive 1');s.at(4,i+1)
 # Explicit physical removal of TX + retry + RX entries in varied endpoint order.
 work=[0]*received+[1]*(n+n-launched);r.shuffle(work)
 for ix,e in enumerate(work):s.add(f'clean {e}');s.at(7,ix+1)
 s.add('clean 0',0);s.add('clean 1',0);s.add('reset');s.at(11,1);s.at(21,1)
 s.boot();s.add('send 1 99');s.add('launch 1');s.add('arrive 1');s.add('consume 0');s.at(1,99);s.add('ack 1 1');s.verify(f'reset-{case:02}')
# Local endpoint cleaned but partner / physical queue still owns old bytes.
s=Schedule();s.boot();s.add('send 1 12');s.add('launch 1')
s.add('req 0 0');s.add('sts 0');s.add('state 0 3');s.add('reset',0)
s.add('arrive 1');s.at(4,1);s.add('reset',0);s.verify('one-sided-reset')
# Owned flight can remain after BOTH adapters are empty; it still blocks exit.
s=Schedule();s.boot();s.add('send 1 31');s.add('launch 1');s.close();s.add('clean 1');s.add('reset',0);s.add('arrive 1');s.at(4,1);s.add('reset');s.verify('flight-fence')
# LinkError is fail-closed in this subset; no invented 16-ms recovery shortcut.
s=Schedule();s.boot();s.add('send 1 32');s.add('launch 1');s.add('state 0 5');s.add('arrive 1');s.at(4,1);s.add('consume 0',0);s.add('reset',0);s.add('state 0 1',0);s.verify('link-error')
# A delayed ACK is owned traffic too; it cannot free a reused sequence slot.
s=Schedule();s.boot();s.add('queue_ack 0',0);s.add('send 0 55');s.add('launch 0');s.add('arrive 0');s.add('consume 1');s.add('queue_ack 1');s.add('launch 1');s.close();s.add('clean 0');s.add('reset',0);s.add('arrive 1');s.at(4,1);s.add('reset');s.boot();s.add('send 0 56');s.at(13,1);s.add('launch 0');s.add('arrive 0');s.add('queue_ack 1');s.add('launch 1');s.add('arrive 1');s.at(13,0);s.add('consume 1');s.at(1,56);s.verify('old-ack')
if '--transport-only' in sys.argv:
 print('PASS: transport ledger checks');sys.exit(0)
# Negative evidence: closed receiver is isolated; arbitrary old bytes introduced
# after reopening are fundamentally indistinguishable. AoU suite retains witness.
v=(((7*0x9e3779b97f4a7c15)&((1<<64)-1))^2)%97+20
score=[sum((v+(k*32+j)%17-3)**2 for j in range(32)) for k in range(32)]
def check(row,t,st):
 assert row['type']==t and row['stage']==st and row['callbacks']==1 and row['drained']
 assert row['discarded']==[2,1,2][st] and row['flight_drops']==[0,1,0][st]
 assert row['crc_errors']==1 and row['duplicates']==1
 assert row['performance_ready'] is False and row['wire_conformance'] is False
 assert row['scores']==score,'distance mismatch'
for t in range(3):
 for st in range(3):check(json.loads(run(f'flow-{t}-{st}',probe,[str(t),str(st)])),t,st)
try:check(json.loads(run('bad-score',probe,['2','1','bad_score'])),2,1)
except AssertionError as e:assert str(e)=='distance mismatch'
else:raise AssertionError('mutation escaped')
print('PASS: 43 transport schedules (300-payload wrap/retry, capacity/retrain/backpressure, 36 reset permutations, one-sided reset, flight fence, LinkError, delayed ACK), 9 DeviceDriver/CUDA flows, distance mutant; full wire/PCIe/PHY conformance OPEN; performance CLOSED')
