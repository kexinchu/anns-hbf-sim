import pathlib,subprocess,sys,uuid
out=pathlib.Path(sys.argv[2])/uuid.uuid4().hex
raise SystemExit(subprocess.call([sys.executable,str(pathlib.Path(__file__).with_name('recovery_diff.py')),sys.argv[1],str(out)]))
