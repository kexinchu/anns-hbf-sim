"""Plot all frozen points; seed envelopes are not confidence intervals."""
import csv,json,pathlib,sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
out=pathlib.Path(sys.argv[1]);rows=list(csv.DictReader((out/'curves.csv').open()));assert len(rows)==192
for metric,label in [('GBps','Modeled useful GB/s'),('p99_ps','P99 latency (us)')]:
 fig,axes=plt.subplots(4,2,figsize=(13,15),sharex=True)
 for ax,(size,cache,mocs) in zip(axes.flat,[(s,c,m) for s in [256,4096] for c in ['cold','hot'] for m in [4096,256]]):
  for pattern,color in [('sequential','tab:blue'),('random','tab:orange'),('pointer_chasing','tab:green')]:
   lo=[];hi=[];qds=[1,16,128,1024]
   for q in qds:
    rr=[r for r in rows if (int(r['size']),r['cache'],int(r['mocs']),r['pattern'],int(r['qd']))==(size,cache,mocs,pattern,q)];assert len(rr)==2
    vv=[float(r[metric])/(1e6 if metric=='p99_ps' else 1) for r in rr];lo.append(min(vv));hi.append(max(vv))
   ax.plot(qds,lo,marker='o',color=color,label=pattern);ax.plot(qds,hi,linestyle=':',color=color);ax.fill_between(qds,lo,hi,color=color,alpha=.12)
  if metric=='GBps':ax.axhline(16*64*1000/852,color='grey',linestyle='--',linewidth=.7,label='v2 service-budget ceiling')
  ax.set(xscale='log',yscale='log',title=f'{size} B | {cache} | MOCS {mocs}',ylabel=label,xlabel='Configured parent QD (pointer effective QD = 1)');ax.grid(True,alpha=.2);ax.legend(fontsize=7)
 fig.suptitle('Frozen protocol v2: 1024-request finite batches; all 192 simulator runs\nTwo-seed min/max, not confidence intervals. No fitted parameters or external measured curve.',fontsize=12)
 fig.tight_layout(rect=[0,0,1,.96]);fig.savefig(out/(metric+'.png'),dpi=150);fig.savefig(out/(metric+'.svg'));plt.close(fig)
 svg=out/(metric+'.svg');svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
checks=[]
for size in [256,4096]:
 for mocs in [4096,256]:
  for seed in [8301,2718]:
   rr=[r for r in rows if (int(r['size']),r['cache'],int(r['mocs']),int(r['seed']),int(r['qd']))==(size,'cold',mocs,seed,1024)]
   rates={r['pattern']:float(r['GBps']) for r in rr}
   assert rates['random']>rates['pointer_chasing']
   checks.append({'size':size,'mocs':mocs,'seed':seed,'independent_over_dependent':rates['random']/rates['pointer_chasing']})
(out/'mechanism-summary.json').write_text(json.dumps({'cold_qd1024_checks':checks,'claim':'qualitative mechanism consistency only; not external numeric calibration','fit_performed':False,'paper_curve_reproduced':False,'performance_ready':False},indent=2))
