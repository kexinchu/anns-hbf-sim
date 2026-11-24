import json,pathlib,sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=pathlib.Path(sys.argv[1]);s=json.loads((root/'summary.json').read_text())
fig,axs=plt.subplots(2,3,figsize=(12,6),layout='constrained')
for ax,(size,pattern) in zip(axs.flat,[(256,'sequential'),(4096,'sequential'),(256,'random'),(4096,'random'),(256,'dependent'),(4096,'dependent')]):
 rows=[r for r in s['runs'] if r['size']==size and r['pattern']==pattern]
 if not rows:ax.axis('off');ax.text(0,.7,'Model diagnostics only\nNo parameter fitting\nNo hardware calibration\nPerformance gate CLOSED',fontsize=12);continue
 for r in rows:
  ax.plot(range(1,5),r['window_GBps'],'o-',label=f"{r['mode']}, {r['pages']*4//1024} MiB"+(' [non-steady]' if not r['steady'] else ''))
 ax.set_title(f'{pattern}, {size} B, QD {rows[0]["qd"]}');ax.set_xlabel('Equal-count completion window');ax.set_ylabel('Useful payload GB/s');ax.set_xticks(range(1,5));ax.grid(alpha=.3);ax.legend(fontsize=7)
fig.suptitle('Continuous page turnover: all windows retained; first window excluded only from stability test')
fig.savefig(root/'window-curves.png',dpi=160)
