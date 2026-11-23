"""Compile real source mutants; require independent ledger tests to kill each."""
import pathlib,sys,subprocess,tempfile,json,shutil,os
root=pathlib.Path(__file__).resolve().parents[1];out=pathlib.Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=True)
mutants={
 'rx_gate':('if(!gate){','if(false){'),
 'duplicate':('if(f.seq!=r.expected){','if(false){'),
 'dirty_flight':('if(!flight[0].empty()||!flight[1].empty())return false;','// intentionally missing flight fence'),
 'same_cycle_rx':('(p.req&&clock<=p.raised)','false'),
 'retrain_cleanup':('p.state==Endpoint::LinkReset||p.state==Endpoint::Disabled','p.state==Endpoint::LinkReset||p.state==Endpoint::Disabled||p.state==Endpoint::Retrain'),
}
for name,(before,after) in mutants.items():
 with tempfile.TemporaryDirectory() as tmp:
  d=pathlib.Path(tmp);src=(root/'src/ucie_lifetime.hpp').read_text();assert before in src
  (d/'ucie_lifetime.hpp').write_text(src.replace(before,after))
  for f in ('aou_hbf_wire.hpp','ucie_trace.cpp'):shutil.copy(root/'src'/f,d/f)
  c=subprocess.run([os.environ.get('CXX','c++'),'-std=c++20',str(d/'ucie_trace.cpp'),'-o',str(d/'probe')],capture_output=True,text=True)
  (out/(name+'.compile')).write_text(c.stdout+c.stderr);assert c.returncode==0,c.stderr
  r=subprocess.run([sys.executable,str(root/'tests/ucie_diff.py'),str(d/'probe'),str(d/'unused'),str(out/name),'--transport-only'],capture_output=True,text=True)
  (out/(name+'.result.json')).write_text(json.dumps({'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr},indent=2))
  assert r.returncode!=0 and 'AssertionError' in r.stderr,(name,'surviving or non-oracle failure',r.stderr)
print('PASS: 5 compiled production-source mutants killed by independent ledger checks')
