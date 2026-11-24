"""Compile broken production stage transitions; require the scan oracle to reject."""
import pathlib,subprocess,shutil,json,sys
build=pathlib.Path(sys.argv[1]).resolve();out=pathlib.Path(sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=False)
root=pathlib.Path(__file__).resolve().parents[1];overlay=build/'eventlab-overlay';source=(overlay/'src/runtime/device_driver.cpp').read_text();results=[]
mutations=[('ignore_prior_sense','const bool result=indexed();','const bool result=false;'),('skip_ingress_index','set_stage(t,Stage::Ingress);','t.stage=Stage::Ingress;'),('leak_feedback_index','''        if(channels_[ch]->stages[static_cast<unsigned>(Stage::Feedback)].erase(id)!=1)
            throw std::logic_error("missing feedback stage entry");''','        // deliberately retain stale feedback directory')]
for name,old,new in mutations:
 assert source.count(old)==1
 d=out/name;d.mkdir();(d/'device_driver.cpp').write_text(source.replace(old,new));shutil.copyfile(build/'eventlab/libhbf_eventlab.a',d/'lib.a')
 cmds=[['c++','-std=c++20','-O2','-DHBF_DEVICE_INDEX_ORACLE=1','-I'+str(overlay/'include'),'-I'+str(overlay/'src/runtime'),'-c',str(d/'device_driver.cpp'),'-o',str(d/'device_driver.cpp.o')],['ar','r',str(d/'lib.a'),str(d/'device_driver.cpp.o')],['c++','-std=c++20','-O2','-DHBF_DEVICE_INDEX_ORACLE=1','-I'+str(overlay/'include'),str(root/'src/mechanism_probe.cpp'),str(d/'lib.a'),'-o',str(d/'probe')]]
 for i,cmd in enumerate(cmds):
  r=subprocess.run(cmd,text=True,capture_output=True,timeout=120);(d/f'build-{i}.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
 r=subprocess.run([str(d/'probe'),'100000','0'],input='2 0 2\n',text=True,capture_output=True,timeout=30);(d/'rejection.txt').write_text(r.stdout+r.stderr)
 assert r.returncode!=0 and ('device stage scan mismatch' in r.stderr or 'device stage identity mismatch' in r.stderr or 'prior-sense differential mismatch' in r.stderr),r.stderr
 results.append({'mutation':name,'rejected_by_independent_scan':True})
(out/'verdict.json').write_text(json.dumps(results,indent=2));print(results)
