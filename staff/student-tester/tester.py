#!/usr/bin/env python3

import sys
import os
import glob
import argparse
from os.path import dirname,join,basename
from subprocess import call,Popen, PIPE
import shutil

MYDIR = dirname(__file__)

sys.path.append( join(dirname(dirname(__file__))))

from s3watch.event_consumer.app import extract

def collect(OUTDIR,lab):
    print(OUTDIR)
    # Clear the outdir
    os.makedirs(OUTDIR, exist_ok = True)
    os.makedirs(OUTDIR+"/html", exist_ok = True)
    for fn in glob.glob(f"{OUTDIR}/*.org*"):
        os.unlink(fn)
    for fn in glob.glob(f"{OUTDIR}/html/*"):
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
    if lab==3:
        append = ''
    else:
        append = f'-lab{lab}'
    for st in students:
        domain = st+append+".csci-e-11.org"
        fn = f'{OUTDIR}/{domain}.txt'
        call(['curl','--connect-timeout','5','-o',fn,f'https://{domain}/'])
        if os.path.exists(fn):
            shutil.copyfile(fn,f'{OUTDIR}/html/{domain}.html')

if __name__=="__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--nocollect",action='store_true',help='do not collect the sites, just do the analysis')
    parser.add_argument("--lab", type=int, default=3,help='specify which lab')
    args = parser.parse_args()

    OUTDIR = f"{MYDIR}/out/lab{args.lab}"
    if not args.nocollect:
        collect(OUTDIR,args.lab)
    count = 0

    def pfname(fn):
        return basename(fn).replace(".csci-e-11.org.txt","")[0:3]+"*****" + ".csci-e-11.org"

    for fn in sorted(glob.glob(f"{OUTDIR}/*.org.txt")):
        print(pfname(fn),os.path.getsize(fn))
        count +=1

    print("")
    print("Total responses:",count)

    print("And here are the outputs that do not have 'Search Student Database' in them:")
    invalid = 0
    for fn in sorted(glob.glob(f"{OUTDIR}/*.org.txt")):
        length = os.path.getsize(fn)
        with open(fn) as f:
            data = f.read()
        if 'Search Student Database' not in data:
            print(f"host: {pfname(fn)}  length: {length}")
            print(data)
            print("")
            invalid += 1
    print("")
    print("Invalid responses:",invalid)
