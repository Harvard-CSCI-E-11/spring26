#!/usr/bin/env python3

import sys
import os
import glob
from os.path import dirname,join,basename
from subprocess import call,Popen, PIPE

sys.path.append( join(dirname(dirname(__file__))))

from s3watch.event_consumer.app import extract
OUTDIR = join(dirname(__file__),'out')

def collect():
    print(OUTDIR)
    for fn in glob.glob(f"{OUTDIR}/*.org"):
        os.unlink(fn)

    students = {}
    fnames = glob.glob(join(dirname(__file__),"students/*"))
    for fname in fnames:
        try:
            with open(fname,"r") as f:
                hostname, ip_address, email, name = extract(f.read())
                students[hostname] = (name,email)
        except ValueError as e:
            pass
    print("student count:",len(students))
    lines = []
    for st in students:
        domain = st+".csci-e-11.org"
        call(['curl','--connect-timeout','5','-o',f'{OUTDIR}/{domain}',f'https://{domain}/'])

if __name__=="__main__":
    if len(sys.argv)==2:
        fn = sys.argv[1]
        print(f"extract {fn} = ")
        with open(fn,"r") as f:
            print(extract(f.read()))
        exit(0)
    collect()
    count = 0
    for fn in sorted(glob.glob(f"{OUTDIR}/*.org")):
        pfn = basename(fn).replace(".csci-e-11.org","")[0:3]+"*****" + ".csci-e-11.org"
        print(pfn,os.path.getsize(fn))
        count +=1

    print("")
    print("Total responses:",count)

    print("And here are the outputs that do not have 'Search Student Database' in them:")
    invalid = 0
    for fn in sorted(glob.glob(f"{OUTDIR}/*.org")):
        pfn = basename(fn).replace(".csci-e-11.org","")[0:3]+"*****" + ".csci-e-11.org"
        length = os.path.getsize(fn)
        with open(fn) as f:
            data = f.read()
        if 'Search Student Database' not in data:
            print(f"host: {pfn}  length: {length}")
            print(data)
            print("")
            invalid += 1
    print("")
    print("Invalid responses:",invalid)
