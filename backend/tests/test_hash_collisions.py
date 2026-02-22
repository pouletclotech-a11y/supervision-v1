import hashlib
from datetime import datetime, timedelta
import collections

def generate_strict_hash(tenant, site, time_bucket, code, action):
    # Format STRICT: tenant|site|time|code|action
    raw_str = f"{tenant}|{site}|{time_bucket}|{code}|{action}"
    return hashlib.sha256(raw_str.encode('utf-8')).hexdigest()

def run_collision_test():
    print("--- STARTING HASH COLLISION TEST ---")
    print("Parameters: 10 Tenants, 10 Sites, 10 Time Buckets, 5 Codes, 3 Actions")
    
    hashes = collections.defaultdict(list)
    total = 0
    
    tenants = [f"tenant_{i}" for i in range(10)]
    sites = [f"site_{i}" for i in range(10)]
    buckets = [i for i in range(10)]
    codes = ["BURGLARY", "FIRE", "AC_LOSS", "TAMPER", "MEDICAL"]
    actions = ["ALARM", "RESTORE", "INFO"]
    
    for t in tenants:
        for s in sites:
            for b in buckets:
                for c in codes:
                    for a in actions:
                        h = generate_strict_hash(t, s, b, c, a)
                        hashes[h].append((t, s, b, c, a))
                        total += 1
    
    collisions = {h: vals for h, vals in hashes.items() if len(vals) > 1}
    
    print(f"Total Events Simulated: {total}")
    print(f"Unique Hashes Generated: {len(hashes)}")
    print(f"Number of Collisions: {len(collisions)}")
    
    if len(collisions) == 0:
        print("RESULT: SUCCESS - 0 COLLISIONS DETECTED")
    else:
        print("RESULT: FAILURE - COLLISIONS FOUND!")
        for h, v in collisions.items():
            print(f"Hash {h}: {v}")

if __name__ == "__main__":
    run_collision_test()
