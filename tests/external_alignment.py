"""External numeric anchors + bounded production-engine microtraces.
The output explicitly refuses to call parameter propagation hardware validation.
"""
import pathlib,sys,subprocess,json,hashlib
exe=pathlib.Path(sys.argv[1]).resolve();out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=90)
(out/'raw.jsonl').write_text(r.stdout);(out/'stderr.txt').write_text(r.stderr)
(out/'run.json').write_text(json.dumps({'exit':r.returncode,'binary_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}))
assert r.returncode==0,r.stderr
rows=[json.loads(s) for s in r.stdout.splitlines()];assert len(rows)==15
summary={'performance_ready':False,'hardware_calibrated':False,'paper_curve_reproduced':False,'bandwidth_comparison':[],'microtraces':[]}
# Independently transcribed OCP Table 4 and sections 5.1.2.1-3; do NOT merge.
for row,section,table in zip(rows[:3],[(48,8),(94,16),(188,16)],[384,1536,3072]):
 assert (row['GBps_per_module'],row['max_modules'])==section
 assert row['cube_GBps']==section[0]*section[1]
 summary['bandwidth_comparison'].append({'grade':row['grade'],'engine_GBps':row['cube_GBps'],'ocp_table4_GBps':table,'relative_difference_pct':100*(row['cube_GBps']/table-1),'classification':'SOURCE_CONFLICT' if row['cube_GBps']!=table else 'PARAMETER_MATCH'})
for row in rows[3:]:
 p,m=row['profile'],row['mode'];assert row['drained'];assert row['senses']==[1,1,2,2][m]
 starts,ends=row['starts_ps'],row['finishes_ps'];target=[100000,2720000,4000000][p]
 assert len(starts)==len(ends)==row['senses'];assert all(b-a==target for a,b in zip(starts,ends))
 if m==2:assert starts[1]<ends[0],'missing bank overlap'
 if m==3:assert starts[1]>=ends[0],'same bank overlap'
 efficiency=row['useful_bytes']/(4096*row['senses'])
 assert efficiency==[.0625,.125,.0625,.0625][m]
 summary['microtraces'].append({'profile':p,'mode':m,'observed_sense_ns':target/1000,'page_efficiency':efficiency,'classification':'PARAMETER_PROPAGATION_AND_ARCHITECTURAL_CHECK_ONLY'})
summary['default_to_retrieval_paper_sense_ratio']=2720000/100000
summary['paper_nominal_media_ceiling_GBps']=16*4*16*4096/2720
(out/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n')
print('PASS: 3 source-profile checks and 12 production-engine microtraces; SG2/3 source conflicts exposed; default sense differs 27.2x; NOT hardware or paper-curve validation')
