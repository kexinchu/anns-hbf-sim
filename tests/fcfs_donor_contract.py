"""Run all named pinned-donor Host scenarios against the overlay."""
import pathlib,re,subprocess,sys
source=pathlib.Path(sys.argv[2]).read_text().split('int main',1)[1]
cases=re.findall(r'\{\s*"([a-z_0-9]+)"\s*,',source)
assert cases and len(cases)==len(set(cases)),cases
for case in cases:
 r=subprocess.run([sys.argv[1],case],capture_output=True,text=True,timeout=60)
 print(r.stdout,end='')
 assert r.returncode==0,(case,r.stderr,r.stdout)
print('PASS',len(cases),'pinned donor scenarios')
