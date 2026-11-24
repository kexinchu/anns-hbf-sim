"""Plot only measured simulator outputs; missing external curve stays missing."""
import csv,pathlib,sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=pathlib.Path(sys.argv[1]);rows=list(csv.DictReader((p/'curves.csv').open()))
fig,axes=plt.subplots(2,2,figsize=(11,8))
for ax,(size,cache) in zip(axes.flat,[(256,'cold'),(256,'hot'),(4096,'cold'),(4096,'hot')]):
 for access in ['sequential','permutation']:
  for dep in ['independent','chain']:
   r=[r for r in rows if r['case']==f'{size}-{cache}-{access}-{dep}']
   ax.plot([int(x['qd']) for x in r],[float(x['GBps']) if x['GBps'] else float('nan') for x in r],marker='o',linestyle='-' if dep=='independent' else '--',label=f'{access}, {dep}')
 missing=sorted({int(x['qd']) for x in rows if x['case'].startswith(f'{size}-{cache}-') and not x['GBps']})
 if missing:
  for q in missing: ax.axvline(q,color='grey',alpha=.25)
  ax.text(.45,.45,'Missing valid results at QD '+','.join(map(str,missing)),transform=ax.transAxes,fontsize=8,color='darkred')
 ax.set(xscale='log',yscale='log',xlabel='Parent QD (chain always 1 active)',ylabel='Modeled useful GB/s',title=f'{size} B, {cache}');ax.grid(True,alpha=.2);ax.legend(fontsize=7)
fig.suptitle('Frozen 1024-request finite-batch component sweep\nExternal numeric paper curve unavailable; NOT hardware calibration',fontsize=12)
fig.tight_layout();fig.savefig(p/'curves.png',dpi=160);fig.savefig(p/'curves.svg')
