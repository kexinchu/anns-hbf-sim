"""Independent boundary oracle: <= deadline admitted before settlement is a policy.
OCP requires a configured deadline, but does not prescribe same-tick event phases.
"""
import json,subprocess,sys
for offset in (-1,0,1):
    for nested in (0,1):
        p=subprocess.run([sys.argv[1],str(offset),str(nested)],capture_output=True,text=True,check=True,timeout=30)
        actual=sorted(json.loads(p.stdout))
        expected=[[i,0 if offset<=0 else 5] for i in range(1,65)]
        if actual!=expected:raise AssertionError((offset,nested,actual,expected))
        mutated=[r[:] for r in actual];mutated[-1][1]=5 if offset<=0 else 0
        if mutated==expected:raise AssertionError('boundary mutation not detected')
print(json.dumps({'status':'PASS','boundary_cases':6,'negative_cases':6,'performance_ready':False}))
