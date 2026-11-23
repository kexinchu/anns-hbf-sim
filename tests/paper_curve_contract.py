"""Fail closed on out-of-protocol requests without executing a sweep."""
import subprocess,sys
cases=[(['128','1','0','0'],'','outside frozen grid'),(['256','0','0','0'],'','outside frozen grid'),(['256','1025','0','0'],'','outside frozen grid'),(['256','1','0','0'],'1024\n','page outside footprint'),(['256','1','0','0'],'0\n','expected 1024 requests')]
for args,data,reason in cases:
 r=subprocess.run([sys.argv[1],*args],input=data,text=True,capture_output=True,timeout=5)
 assert r.returncode==1 and reason in r.stderr and not r.stdout,(args,r)
print('PASS: five out-of-protocol inputs rejected before initialization')
