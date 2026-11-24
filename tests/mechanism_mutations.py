"""Production cache mutations checked by a separate Python mechanism reference."""
import json,pathlib,shutil,subprocess,sys
b=pathlib.Path(sys.argv[1]).resolve();out=pathlib.Path(sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=False)
root=pathlib.Path(__file__).resolve().parents[1];overlay=b/'eventlab-overlay';src=(overlay/'src/runtime/bank_cache.cpp').read_text();results=[]
for name,old,new in [('one_slot','i<2;++i) {\n        const auto& s=slots[i]','i<1;++i) {\n        const auto& s=slots[i]'),('fifo_instead_of_assumed_lru','s.age=checked_add(age_,1); age_=s.age;\n    return ReadResultLease','/* MUTANT: no hit recency update */\n    return ReadResultLease')]:
 assert src.count(old)==1
 d=out/name;d.mkdir();(d/'bank_cache.cpp').write_text(src.replace(old,new));lib=d/'libhbf_eventlab.a';shutil.copy2(b/'eventlab/libhbf_eventlab.a',lib)
 commands=[['c++','-std=c++20','-O2','-I'+str(overlay/'include'),'-c',str(d/'bank_cache.cpp'),'-o',str(d/'bank_cache.cpp.o')],['ar','r',str(lib),str(d/'bank_cache.cpp.o')],['c++','-std=c++20','-O2','-I'+str(overlay/'include'),str(root/'src/mechanism_probe.cpp'),str(lib),'-o',str(d/'probe')]]
 for i,cmd in enumerate(commands):
  r=subprocess.run(cmd,capture_output=True,text=True,timeout=120);(d/f'build-{i}.txt').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
 r=subprocess.run([sys.executable,str(root/'tests/mechanism_diff.py'),str(d/'probe'),str(d/'observations')],capture_output=True,text=True,timeout=60)
 (d/'rejection.txt').write_text(r.stdout+r.stderr)
 assert r.returncode!=0 and 'AssertionError' in r.stderr and "row['senses']==int(not hit)" in r.stderr,r.stderr
 results.append({'mutant':name,'rejected':True,'scope':'two-buffer capacity' if name=='one_slot' else 'declared replacement assumption, not OCP certification'})
(out/'verdict.json').write_text(json.dumps(results,indent=2));print(results)
