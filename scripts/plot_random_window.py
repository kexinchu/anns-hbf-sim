"""Plot every original window; diagnostic only, no fit or acceptance reclassification."""
import json,pathlib,sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
source=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2]);data=json.loads(source.read_text())
fig,axes=plt.subplots(2,2,figsize=(10,7),layout='constrained')
for ax,c in zip(axes.flat,data['cases']):
 for key,label in [('baseline','Original finite stream'),('guard','Append 128 requests')]:
  ax.plot(range(1,5),[w['GBps'] for w in c[key]['windows']],marker='o',label=label)
 ax.set_title(f"{c['mode']} / {c['size']} B\nlast-three max/min: {c['baseline']['ratio_last_three']:.4f} -> {c['guard']['ratio_last_three']:.4f}")
 ax.set_xticks(range(1,5));ax.set_xlabel('3072-completion window (all shown)');ax.set_ylabel('Useful GB/s (simulated)');ax.grid(alpha=.25);ax.legend(fontsize=8)
fig.suptitle('Finite-window diagnostic; original four failures retained; NOT calibrated',fontsize=12)
fig.savefig(out,dpi=160)
