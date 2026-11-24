"""Compile broken production Host implementations and require oracle rejection."""
import pathlib,shutil,subprocess,sys,json
build=pathlib.Path(sys.argv[1]).resolve();out=pathlib.Path(sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=False)
root=pathlib.Path(__file__).resolve().parents[1];overlay=build/'eventlab-overlay';source=(overlay/'src/host/host_driver.cpp').read_text()
mutants={
 'omit_cursor_reset':('fcfs_cursor.reset(); // A successful handoff may unblock read predecessors.','// MUTANT: retain stale cursor after a successful handoff'),
 'reverse_age':('for(auto age_it=fcfs_cursor?channel.age_queue.upper_bound(*fcfs_cursor):channel.age_queue.begin();age_it!=channel.age_queue.end();++age_it) {','for(auto age_it=channel.age_queue.rbegin();age_it!=channel.age_queue.rend();++age_it) {'),
 'omit_handoff_cleanup':('u.stage=UnitStage::Handed;erase_queued(u);','u.stage=UnitStage::Handed;channel.queue.erase(chosen);')}
results=[]
for name,(old,new) in mutants.items():
 assert source.count(old)==1
 d=out/name;d.mkdir();(d/'host_driver.cpp').write_text(source.replace(old,new));lib=d/'libhbf_eventlab.a';shutil.copy2(build/'eventlab/libhbf_eventlab.a',lib)
 commands=[['c++','-std=c++20','-O2','-DHBF_FCFS_SCAN_ORACLE=1','-I'+str(overlay/'include'),'-c',str(d/'host_driver.cpp'),'-o',str(d/'host_driver.cpp.o')],['ar','r',str(lib),str(d/'host_driver.cpp.o')],['c++','-std=c++20','-O2','-I'+str(overlay/'include'),str(root/('src/fcfs_cursor_contract.cpp' if name=='omit_cursor_reset' else 'vendor/EventLab/tests/host_send_policy.cpp')),str(lib),'-o',str(d/'probe')]]
 for i,cmd in enumerate(commands):
  r=subprocess.run(cmd,capture_output=True,text=True,timeout=120);(d/f'build-{i}.txt').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
 killed=False
 for case in (['cursor'] if name=='omit_cursor_reset' else ['fcfs','release_order','not_taken','retry_tail','preflight_cancel']):
  r=subprocess.run([str(d/'probe'),case],capture_output=True,text=True,timeout=30);(d/(case+'.txt')).write_text(r.stdout+r.stderr)
  if r.returncode and ('FCFS' in r.stderr):killed=True;results.append({'mutant':name,'case':case,'diagnostic':r.stderr.strip()});break
 assert killed,name
# Terminal-index faults must be exposed by incremental reclamation/retry cases.
for name,filename,old,new in [
 ('omit_terminal_completion','host_driver.cpp','u.stage=UnitStage::Done;terminal_units_.insert(u.id);u.successful=success;','u.stage=UnitStage::Done;u.successful=success;'),
 ('omit_terminal_requeue','write_retry.cpp','terminal_units_.erase(u.id);','/* MUTANT: stale terminal entry */')]:
 original=(overlay/'src/host'/filename).read_text();assert original.count(old)==1
 d=out/name;d.mkdir();(d/filename).write_text(original.replace(old,new))
 lib=d/'libhbf_eventlab.a';shutil.copy2(build/'eventlab/libhbf_eventlab.a',lib)
 commands=[['c++','-std=c++20','-O2','-DHBF_FCFS_SCAN_ORACLE=1','-I'+str(overlay/'include'),'-c',str(d/filename),'-o',str(d/(filename+'.o'))],['ar','r',str(lib),str(d/(filename+'.o'))],['c++','-std=c++20','-O2','-I'+str(overlay/'include'),str(root/('src/fcfs_incremental_retry_contract.cpp' if name=='omit_terminal_requeue' else 'vendor/EventLab/tests/host_incremental.cpp')),str(lib),str(build/'eventlab/libhbf_eventlab_workload_io.a'),'-o',str(d/'probe')]]
 for i,cmd in enumerate(commands):
  r=subprocess.run(cmd,capture_output=True,text=True,timeout=120);(d/f'build-{i}.txt').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
 killed=False
 for case in (['retry'] if name=='omit_terminal_requeue' else ['split','recovery_append','recovered_sealed','abort_append','equivalent']):
  r=subprocess.run([str(d/'probe'),case],capture_output=True,text=True,timeout=30);(d/(case+'.txt')).write_text(r.stdout+r.stderr)
  if r.returncode and 'terminal' in r.stderr:
   killed=True;results.append({'mutant':name,'case':case,'diagnostic':r.stderr.strip()});break
 assert killed,name
(out/'verdict.json').write_text(json.dumps(results,indent=2));print(results)
