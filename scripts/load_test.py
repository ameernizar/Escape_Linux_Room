#!/usr/bin/env python3
"""Safe control-plane smoke load: concurrent leaderboard reads only by default."""
import argparse, concurrent.futures, statistics, time, urllib.request
def one(url):
    started=time.perf_counter()
    with urllib.request.urlopen(url+"/api/v1/leaderboard",timeout=5) as response: response.read()
    return (time.perf_counter()-started)*1000
if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--url",default="http://localhost:8000"); p.add_argument("--requests",type=int,default=100); p.add_argument("--workers",type=int,default=40); a=p.parse_args()
    with concurrent.futures.ThreadPoolExecutor(a.workers) as ex: values=list(ex.map(lambda _:one(a.url),range(a.requests)))
    print(f"requests={len(values)} p50={statistics.median(values):.1f}ms p95={sorted(values)[int(.95*len(values))-1]:.1f}ms")
