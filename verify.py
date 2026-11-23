"""Independent trace/functional checks; no performance qualification."""
import json, pathlib, subprocess, hashlib, os, argparse
if not __debug__: raise RuntimeError("Validation requires Python assertions; do not use -O")
ROOT = pathlib.Path(__file__).resolve().parent
EXE = ROOT / 'build-loop/anns_loop'
OUT = ROOT / 'results'
CONCURRENT = False

def validate(rows, slots):
    events = [r for r in rows if 'event' in r]
    assert [r['t_ps'] for r in events] == sorted(r['t_ps'] for r in events)
    resident, produced, complete, last_work = {}, {}, set(), {}
    resources = {'hbm': [], 'gpu': []}
    burst_bytes = 0
    total_read = total_write = total_hbf = 0
    for r in events:
        e, t, q, s, p = (r[k] for k in ('event','t_ps','q','slot','page'))
        if e == 'producer_done': produced[q] = t
        if e == 'hbf_submit':
            assert q in produced and t >= produced[q] and s not in resident
            resident[s] = dict(q=q, page=p, state='issued')
            assert len(resident) <= slots
            total_hbf += r['bytes']
        if s >= 0 and e != 'hbf_submit':
            a = resident[s]
            assert (a['q'], a['page']) == (q, p)
            if e == 'hbf_complete':
                assert a['state'] == 'issued'
                a.update(state='returned', returned=t)
            elif e == 'hbm_write':
                assert a['state'] == 'returned' and r['start_ps'] >= a['returned']
                a['write_end'] = r['end_ps']
            elif e == 'visible':
                assert t == a['write_end']
                a.update(state='visible', visible=t)
            elif e == 'hbm_read':
                assert a['state'] == 'visible' and r['start_ps'] >= a['visible']
                a['read_end'] = r['end_ps']
            elif e == 'compute':
                assert a['state'] == 'visible' and r['start_ps'] >= a['read_end']
                a['compute_end'] = r['end_ps']
            elif e == 'consume':
                assert a['state'] == 'visible' and t == a['compute_end']
                del resident[s]
        if e == 'hbm_burst':
            assert r['start_ps'] == t and r['end_ps'] >= t
            resources.setdefault('lane'+str(q), []).append((t,r['end_ps']))
            burst_bytes += r['bytes']
        if e in ('hbm_read','hbm_write','compute'):
            if CONCURRENT and e != 'compute':
                assert r['start_ps'] <= r['end_ps'] == t
            else:
                assert r['end_ps'] >= r['start_ps'] >= t
                resources['gpu' if e == 'compute' else 'hbm'].append((r['start_ps'],r['end_ps']))
            last_work[q] = max(last_work.get(q,0),r['end_ps'])
        if e == 'hbm_read': total_read += r['bytes']
        if e == 'hbm_write': total_write += r['bytes']
        if e == 'query_done':
            assert q not in complete and all(a['q'] != q for a in resident.values())
            assert t == last_work[q]
            complete.add(q)
    assert not resident and complete == {0,1}
    for intervals in resources.values():
        intervals.sort()
        assert all(a[1] <= b[0] for a,b in zip(intervals,intervals[1:]))
    if CONCURRENT: assert burst_bytes == total_read+total_write
    assert (total_hbf,total_read,total_write) == (32768,33792,33024)
    # Python native oracle independently regenerates vectors and IVF lists.
    db = [[i//64*100+(i*17+j*13)%23-11 for j in range(32)] for i in range(256)]
    assert sorted(r['result_q'] for r in rows if 'result_q' in r) == [0,1]
    for r in rows:
        if 'result_q' not in r: continue
        v = db[[27,172][r['result_q']]]
        lists = sorted(range(4), key=lambda l:(sum((l*100-x)**2 for x in v),l))[:2]
        expected = sorted((sum((a-b)**2 for a,b in zip(x,v)),i)
                          for i,x in enumerate(db) if i//64 in lists)[:10]
        assert r['ids'] == [i for _,i in expected]
    assert rows[-1]['status'] == 'PASS'
    return {'events':len(events),'queries':len(complete),'bytes_checked':total_hbf+total_read+total_write}

def main():
    global EXE, OUT, CONCURRENT
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrent", action="store_true")
    parser.add_argument("--binary", type=pathlib.Path, default=EXE)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()
    EXE, OUT = args.binary.resolve(), args.out.resolve()
    CONCURRENT = args.concurrent
    OUT.mkdir(parents=True, exist_ok=False)
    checks = []
    cases = {'default':[100000,10000,2,10000],
             'one_slot':[100000,10000,1,10000],
             'slow_media':[1000000,10000,2,10000],
             'slow_consumer':[100000,1000000,2,10000],
             'late_producer':[100000,10000,2,1000000]}
    results = {}
    for name,args in cases.items():
        p = subprocess.run([str(EXE),*map(str,args)],capture_output=True,text=True,timeout=30,
                           env={**os.environ,'ANNS_CONFIG_OUT':str(OUT/f'{name}.ini')})
        (OUT/f'{name}.jsonl').write_text(p.stdout)
        (OUT/f'{name}.stderr').write_text(p.stderr)
        assert p.returncode == 0,(name,p.stderr)
        rows = [json.loads(x) for x in p.stdout.splitlines()]
        checks.append({'case':name,**validate(rows,args[2])})
        results[name]=rows
    # Deterministic execution: exact event receipts, not just final top-k.
    repeated=subprocess.check_output([str(EXE)],text=True,timeout=30)
    assert repeated==(OUT/'default.jsonl').read_text()
    def completion(rows):return max(r['t_ps'] for r in rows if r.get('event')=='query_done')
    assert completion(results['slow_media'])>completion(results['default'])
    assert completion(results['slow_consumer'])>completion(results['default'])
    assert completion(results['late_producer'])>completion(results['default'])
    for mutation in ('early_consume','corrupt_payload','wrong_address'):
        p=subprocess.run([str(EXE),'100000','10000','2','10000',mutation],capture_output=True,text=True,timeout=30)
        (OUT/f'{mutation}.jsonl').write_text(p.stdout)
        (OUT/f'{mutation}.stderr').write_text(p.stderr)
        assert p.returncode != 0 and 'FAIL' in p.stderr
        checks.append({'mutation':mutation,'rejected':True,'error':p.stderr.strip()})
    # Independent checker must reject a deleted write and an early visible event.
    original=results['default']
    corruptions=[ [r for i,r in enumerate(original) if i!=next(j for j,x in enumerate(original)
                  if x.get('event')=='hbm_write' and x['slot']>=0)],
                  [dict(r,t_ps=0) if r.get('event')=='visible' else r for r in original] ]
    if CONCURRENT:
        j=next(i for i,r in enumerate(original) if r.get('event')=='hbm_burst')
        corruptions.append(original[:j]+original[j+1:])
        corruptions.append(original[:j]+[original[j]]+original[j:])
    for rows in corruptions:
        try:validate(rows,2)
        except (AssertionError,KeyError):pass
        else:raise AssertionError('trace corruption escaped validator')
    report={'status':'PASS','scope':'CPU_FUNCTIONAL_AND_CAUSAL_ONLY',
            'performance_ready':False,'checks':checks,'deterministic_replay':True,
            'trace_mutations_rejected':len(corruptions),'comparisons':{name:{'completion_ps':completion(rows),'relative_to_default':completion(rows)/completion(results['default'])} for name,rows in results.items()},
            'binary_sha256':hashlib.sha256(EXE.read_bytes()).hexdigest()}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
