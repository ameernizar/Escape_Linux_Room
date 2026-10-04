#!/usr/bin/env python3
"""Staged, disposable rootless-container capacity test; existing teams are untouched."""
import concurrent.futures as futures
import json, os, pathlib, secrets, statistics, subprocess, tempfile, threading, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
names = []
samples = []
api_samples = []
stop = threading.Event()
abort = threading.Event()
prefix = "escape-load-" + secrets.token_hex(4) + "-"
results = []

def run(args, **kwargs):
    kwargs.setdefault("timeout",60)
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)

def memory():
    fields = dict(line.split(":", 1) for line in pathlib.Path("/proc/meminfo").read_text().splitlines())
    total = int(fields["MemTotal"].split()[0])
    available = int(fields["MemAvailable"].split()[0])
    swap = int(fields["SwapTotal"].split()[0]) - int(fields["SwapFree"].split()[0])
    pressure = pathlib.Path("/proc/pressure/memory").read_text().splitlines()
    full = float(pressure[1].split()[1].split("=")[1])
    return {"available_mib":round(available/1024), "swap_used_mib":round(swap/1024), "memory_stall_pct":full, "load1":os.getloadavg()[0]}

baseline = memory()

def monitor():
    while not stop.is_set():
        sample = memory()
        samples.append(sample)
        if sample["available_mib"] < 600 or sample["swap_used_mib"] > baseline["swap_used_mib"] + 256 or sample["memory_stall_pct"] > 10:
            abort.set()
        started = time.perf_counter()
        try:
            with urllib.request.urlopen("http://localhost:8000/api/v1/leaderboard", timeout=3) as response:
                response.read()
            api_samples.append(round((time.perf_counter()-started)*1000,1))
        except Exception:
            api_samples.append(None)
        stop.wait(1)

def percentile(values, fraction):
    return round(sorted(values)[max(0, int(len(values)*fraction+0.999)-1)],1)

def workload(name):
    started = time.perf_counter()
    # Real challenge searches; output is counted, never printed (no answer leakage).
    command = "set -eu; pwd >/dev/null; ls -la /escape/room2 >/dev/null; find /escape -type f | sort | wc -l >/dev/null; grep -R NEXT /escape/room5 | sort | wc -l >/dev/null; find /escape/room6 -type f -mtime 0 | wc -l >/dev/null"
    try:
        run(["podman","exec","--user","player",name,"/bin/sh","-c",command], timeout=15)
        return round((time.perf_counter()-started)*1000,1), None
    except Exception as error:
        return round((time.perf_counter()-started)*1000,1), str(error)

thread = threading.Thread(target=monitor,daemon=True)
thread.start()
print(json.dumps({"baseline":baseline,"test_prefix":prefix}),flush=True)
try:
    with tempfile.TemporaryDirectory(prefix="escape-load-fixtures-") as temp:
        fixture = pathlib.Path(temp)/"escape"
        run(["python3","challenges/generate_instance.py",secrets.token_hex(32),"--root",str(fixture)],cwd=ROOT,env={**os.environ,"PYTHONPATH":str(ROOT)})
        run(["chmod","-R","u+rX",str(fixture)])
        archive = run(["tar","--owner=100","--group=101","--numeric-owner","-C",str(fixture),"-cf","-","."]).stdout
        for target in (10,20,30):
            if abort.is_set():
                break
            while len(names) < target and not abort.is_set():
                name = prefix + str(len(names)+1)
                names.append(name)
                run(["podman","run","-d","--name",name,"--network","none","--read-only","--user","player","--memory","256m","--cpus","0.5","--pids-limit","128","--cap-drop","all","--security-opt","no-new-privileges","--tmpfs","/tmp:rw,noexec,nosuid,size=32m","--tmpfs","/escape:rw,nosuid,nodev,size=64m,mode=0777","localhost/escape-player:locked","sleep","900"])
                run(["podman","exec","-i","--user","player",name,"tar","-C","/escape","-xf","-"],input=archive)
            if abort.is_set():
                break
            print("Testing "+str(target)+" concurrent team containers",flush=True)
            stage_start = len(samples)
            api_start = len(api_samples)
            timings, errors = [], []
            with futures.ThreadPoolExecutor(max_workers=target) as pool:
                for repeat in range(5):
                    if abort.is_set():
                        break
                    for elapsed, error in pool.map(workload,names):
                        timings.append(elapsed)
                        if error:
                            errors.append(error)
                    time.sleep(1)
            observed = samples[stage_start:] or [memory()]
            requests = api_samples[api_start:]
            success = [x for x in requests if x is not None]
            result = {"teams":target,"command_batches":len(timings),"errors":len(errors),"batch_p50_ms":round(statistics.median(timings),1) if timings else None,"batch_p95_ms":percentile(timings,.95) if timings else None,"batch_max_ms":max(timings) if timings else None,"min_available_mib":min(x["available_mib"] for x in observed),"max_swap_used_mib":max(x["swap_used_mib"] for x in observed),"max_memory_stall_pct":max(x["memory_stall_pct"] for x in observed),"api_p95_ms":percentile(success,.95) if success else None,"api_errors":requests.count(None),"safety_stop":abort.is_set()}
            results.append(result)
            print(json.dumps(result),flush=True)
            if errors or abort.is_set():
                break
finally:
    print("Removing only this run's test containers",flush=True)
    cleanup_errors = []
    for name in names:
        try:
            run(["podman","rm","-f","--time","0",name])
        except Exception:
            cleanup_errors.append(name)
    stop.set()
    thread.join(timeout=5)
    report={"baseline":baseline,"results":results,"safety_stop":abort.is_set(),"after":memory(),"cleanup_errors":cleanup_errors,"scope":"Five concurrent command batches per team; each includes Podman exec startup, file searches and sorting. No browser/WebSocket simulation or sustained soak test."}
    print(json.dumps(report,indent=2),flush=True)
    (ROOT/"scripts"/"capacity-results.json").write_text(json.dumps(report,indent=2)+"\n")
