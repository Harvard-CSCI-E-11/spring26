#!/usr/bin/env python3

import argparse
import glob
import matplotlib.pyplot as plt
import numpy as np
import os
import requests
import socket
import ssl
import sys
import time
import logging

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from datetime import datetime
from os.path import dirname,join,basename
from subprocess import call
from threading import Lock

from concurrent.futures import ThreadPoolExecutor


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_CACHE_SECONDS = 60*60
MYDIR = dirname(__file__)

sys.path.append( join(dirname(dirname(__file__))))

from s3watch.event_consumer.app import extract


def test_https_cert(hostname):
    """Test HTTPS certificate and fetch root page content.

    Args:
        hostname (str): The hostname to test

    Returns:
        dict: Contains certificate names, page content, and expiration date

    Raises:
        AssertionError: If certificate validation or page fetch fails
    """
    try:
        # First, check the TLS certificate
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with socket.create_connection((hostname, 443), timeout=3) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                der_cert = ssock.getpeercert(binary_form=True)

        cert = x509.load_der_x509_certificate(der_cert, default_backend())
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        dns_names = san.value.get_values_for_type(x509.DNSName)

        # Check if the provided hostname is in the certificate's SANs
        if hostname not in dns_names:
            raise AssertionError(f"Expected {hostname} in SANs: {dns_names}")

        # If hostname is found in SANs, perform HTTPS GET request
        response = requests.get(f"https://{hostname}", timeout=5)
        response.raise_for_status()  # Raise an exception for bad status codes

        return {
            "tls_certificate_names": sorted(dns_names),
            "root_page_content": response.text,
            "expires":cert.not_valid_after
        }

    except Exception as e:
        raise AssertionError(f"Failed to validate cert or get page: {e}")

def collect(outdir,lab):
    print(f"Collecting {outdir} for lab {lab}")

    print("Syncing students...")
    call("aws --profile=fas s3 sync s3://cscie-11/students/ students/")

    print("Downloading from servers...")

    # Clear the outdir
    os.makedirs(outdir, exist_ok = True)
    os.makedirs(outdir+"/html", exist_ok = True)
    for fn in glob.glob(f"{outdir}/*.org*"):
        os.unlink(fn)
    for fn in glob.glob(f"{outdir}/html/*"):
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
    if lab==3:
        append = ''
    else:
        append = f'-lab{lab}'

    expiration_times = []  # List to store expiration dates
    lock = Lock()
    current_date = datetime.now()

    def process_host(host_data):
        domain, outdir = host_data
        try:
            resp = test_https_cert(domain)
            with open(f'{outdir}/{domain}.txt', "w") as f:
                f.write(resp['root_page_content'])
            with open(f'{outdir}/html/{domain}.html', "w") as f:
                f.write(resp['root_page_content'])
            return resp['expires']
        except AssertionError as e:
            logger.warning(f"{domain}: {e}")
            return None

    host_data = [(st + append + ".csci-e-11.org", outdir) for st in students]
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(tqdm(executor.map(process_host, host_data), total=len(host_data)))
        expiration_times = [r for r in results if r is not None]

    if expiration_times:
        days_until_expiration = [(exp - current_date).days for exp in expiration_times]
        days_until_expiration = [d for d in days_until_expiration if d >= 0]

        if days_until_expiration:
            sorted_days = np.sort(days_until_expiration)
            cdf = np.arange(1, len(sorted_days) + 1) / len(sorted_days)

            plt.figure(figsize=(12, 8))
            plt.plot(sorted_days, cdf, marker='.', linestyle='none')
            plt.grid(True)
            plt.xlabel('Days Until Certificate Expiration')
            plt.ylabel('Cumulative Probability')
            plt.title(f'CDF of Certificate Expiration Dates - Lab {lab}')
            plt.axvline(x=90, color='r', linestyle='--', label='90 days')
            plt.legend()

            plot_path = join(outdir, 'certificate_expiration_cdf.png')
            plt.savefig(plot_path, dpi=300, bbox_inches='tight')
            plt.close()

            logger.info(f"CDF plot saved as {plot_path}")
            logger.info(f"Certificates analyzed: {len(days_until_expiration)}")
            logger.info(f"Median days until expiration: {np.median(days_until_expiration):.0f}")
        else:
            print("No valid expiration dates to plot (all certificates expired)")


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,help='Test the student VMs')
    parser.add_argument("--collect",action='store_true',help='Collect the sites. By default do this if we have not run in an hour')
    parser.add_argument("--lab", type=int, default=3,help='specify which lab')
    args = parser.parse_args()

    outdir = f"{MYDIR}/out/lab{args.lab}"
    os.makedirs(outdir,exist_ok=True)

    if args.collect or os.path.getmtime(outdir) - time.time() > MAX_CACHE_SECONDS:
        collect(outdir,args.lab)
    count = 0

    def pfname(fn):
        return basename(fn).replace(".csci-e-11.org.txt","")[0:3]+"*****" + ".csci-e-11.org"

    for fn in sorted(glob.glob(f"{outdir}/*.org.txt")):
        print(pfname(fn),os.path.getsize(fn))
        count +=1

    print("")
    print("Total responses:",count)

    print("And here are the outputs that do not have 'Search Student Database' in them:")
    invalid = 0
    for fn in sorted(glob.glob(f"{outdir}/*.org.txt")):
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

if __name__=="__main__":
    main()
