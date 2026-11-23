"""Independent, declarative OCP host-policy transcripts; no implementation imports.
Each expected line is a reviewed protocol action, not a timing/calibration oracle.
"""
import subprocess,sys
cases=[]
def add(lines): cases.append(lines)
for ecc,valid,action in [(4,0,'backup_required'),(5,1,'deliver_refresh')]:
 add([('issue 1 0 0 0','accepted'),(f'response 1 {ecc} 1 {valid}',action),
 ('write 0 0 0 0','blocked'),('refresh 0 2 0 0','invalid'),
 ('refresh 0 2 1 0','ok'),('page 0 1 1 0','invalid'),
 ('page 0 0 1 0','ok'),('issue 2 0 0 0','blocked'),
 ('page 0 1 0 0','ok'),('write 0 0 0 0','blocked'),
 ('refresh 0 2 1 0','ok'),('page 0 0 1 0','ok'),('page 0 1 1 0','ok'),
 ('issue 2 0 0 0','accepted'),('response 2 0 0 1','deliver')])
for stage in range(8):
 add([('issue 1 0 0 0','accepted'),(f'response 1 6 {stage} 0',f'retry:{stage}'),
 ('stage 1 0 0 0',str(stage)),('response 1 6 7 0','retry:7'),
 ('response 1 6 2 0','retry:2'),('response 1 6 3 0','retry_exhausted'),
 ('response 1 0 0 1','invalid')])
add([('issue 1 1 0 0','accepted'),('response 1 9 1 0','poll_die'),
 ('issue 2 3 0 0','blocked'),('write 2 0 0 0','blocked'),
 ('issue 3 4 0 0','accepted'),('response 3 0 0 1','deliver'),
 ('poll 0 0 0 0','ok'),('write 0 0 0 0','blocked'),
 ('poll 0 1 0 0','ok'),('issue 2 3 0 0','accepted')])
for gran in range(1,5):
 lines=[('issue 1 1 0 0','accepted'),(f'response 1 8 {gran} 0','retired')]
 bad={1:{1},2:{0,1},3:set(range(4)),4:set(range(8))}[gran]
 lines += [(f'write {b} 0 0 0','blocked' if b in bad else 'allowed') for b in range(8)]
 add(lines)
for status,info,valid in [(4,3,0),(5,0,1),(9,2,0),(8,5,0),(4,1,1),(5,1,0),(6,2,1)]:
 add([('issue 1 0 0 0','accepted'),(f'response 1 {status} {info} {valid}','invalid'),('response 1 0 0 1','deliver')])
for lines in cases:
 p=subprocess.run([sys.argv[1]],input='\n'.join(x for x,_ in lines)+'\n',text=True,capture_output=True,timeout=10)
 assert p.returncode==0,p.stderr
 expected=[y for _,y in lines]
 assert p.stdout.splitlines()==expected,(lines,p.stdout)
 mutant=expected.copy();mutant[0]='forged'
 assert p.stdout.splitlines()!=mutant
print(f'PASS {len(cases)} independent transcripts; reserved metadata, invalid data, retry bounds, refresh order and die isolation')
