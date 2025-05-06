#!/usr/bin/env python3

import argparse
import glob
import logging
import matplotlib.pyplot as plt
import numpy as np
import os
import requests
import socket
import ssl
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from datetime import datetime
from os.path import dirname, join, basename
from subprocess import call
from threading import Lock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_CACHE_SECONDS = 60 * 60
MYDIR = dirname(__file__)

sys.path.append(join(dirname(dirname(__file__))))
from s3watch.event_consumer.app import extract

def test_https_cert(hostname):
    """Test HTTPS certificate and fetch root page content."""
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with socket.create_connection((hostname, 443), timeout=3) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                der_cert = ssock.getpeercert(binary_form=True)
        cert = x509.load_der_x509_certificate(der_cert, default_backend())
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        dns_names = san.value.get_values_for_type(x509.DNSName)
        ret = {'hostname':hostname,
               'expires':cert.not_valid_after,
               'tls_certificate_names': sorted(dns_names),
               'dns_lab_cert':hostname in dns_names}
        if ret['dns_lab_cert']:
            response = requests.get(f"https://{hostname}", timeout=5)
            response.raise_for_status()
            ret["root_page_content"] = response.text
        return ret

    except Exception as e:
        raise AssertionError(f"Failed to validate cert or get page: {e}")

def collect(outdir, lab):
    """Collect student website data and generate expiration CDF."""
    logger.info(f"Collecting {outdir} for lab {lab}")
    try:
        logger.info("Syncing students...")
        call(["aws", "--profile=fas", "s3", "sync", "s3://cscie-11/students/", "students/"])
        logger.info("Downloading from servers...")
        os.makedirs(outdir, exist_ok=True)
        os.makedirs(join(outdir, "html"), exist_ok=True)
        for fn in glob.glob(f"{outdir}/*.org*"):
            os.unlink(fn)
        for fn in glob.glob(f"{outdir}/html/*"):
            os.unlink(fn)

        students = {}
        fnames = glob.glob(join(dirname(__file__), "students/*"))
        for fname in fnames:
            try:
                with open(fname, "r") as f:
                    hostname, ip_address, email, name = extract(f.read())
                    students[hostname] = (name, email)
            except ValueError:
                pass
        logger.info(f"Student count: {len(students)}")

        append = '' if lab == 3 else f'-lab{lab}'
        current_date = datetime.now()
        valid_certs = 0
        invalid_certs = 0
        message_count = []

        def process_host(host_data):
            domain, outdir = host_data
            try:
                resp = test_https_cert(domain)
                if 'root_page_content' in resp:
                    for path in [f'{outdir}/{domain}.txt', f'{outdir}/html/{domain}.html']:
                        with open(path, "w") as f:
                            f.write(resp['root_page_content'])

                if lab in (4,5):
                    url = f'https://{domain}/api/get-messages'
                    try:
                        data = requests.get(url).json()
                        message_count.append(len(data))
                    except requests.exceptions.SSLError:
                        print("invalid SSL:",domain)
                    except requests.exceptions.JSONDecodeError:
                        print("Bad JSON:",url)

                return resp
            except AssertionError as e:
                logger.warning(f"{domain}: {e}")
                return None

        host_data = [(st + append + ".csci-e-11.org", outdir) for st in students]
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(process_host, host_data)
            results = [r for r in results if r is not None]
            expiration_times = [r['expires'] for r in results]
            dns_lab_certs    = [r['dns_lab_cert'] for r in results]
            for v in sorted([ (r['expires'],r['tls_certificate_names']) for r in results]):
                print(v)

        try:
            avg = math.fsum(message_count)/len(message_count)
            mx  = max(message_count)
        except ZeroDivisionError:
            avg = 'n/a'
            mx  = 'n/a'

        logger.info("expiration_times: %s",expiration_times)
        logger.info("dns_lab_certs: %s",dns_lab_certs)
        logger.info("Domains with operaitonal API: %s  with >0 messages: %s  average number of messages: %s  max: %s",
                    len(message_count),
                    len([m for m in message_count if m>0]),
                    avg, mx)

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
                logger.info("No valid expiration dates to plot (all certificates expired)")
    except Exception as e:
        logger.error(f"Collection failed: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter, description='Test the student VMs')
    parser.add_argument("--collect", action='store_true', help='Collect the sites. By default do this if we have not run in an hour')
    parser.add_argument("--lab", type=int, default=3, help='Specify which lab')
    args = parser.parse_args()

    outdir = os.path.abspath(f"{MYDIR}/out/lab{args.lab}")
    os.makedirs(outdir, exist_ok=True)

    if args.collect or (os.path.exists(outdir) and (time.time() - os.path.getmtime(outdir)) > MAX_CACHE_SECONDS):
        collect(outdir, args.lab)

    logging.info("outdir: %s",outdir)

    count = 0
    def pfname(fn):
        return basename(fn).replace(".csci-e-11.org.txt", "")[0:3] + "*****" + ".csci-e-11.org"

    for fn in sorted(glob.glob(f"{outdir}/*.org.txt")):
        logger.info(f"{fn} {os.path.getsize(fn)}")
        count += 1

    for fn in sorted(glob.glob(f"{outdir}/*.org.txt")):
        logger.info(f"{pfname(fn)} {os.path.getsize(fn)}")

    if args.lab==3:
        srch = 'Search Student Database'
    elif args.lab==5:
        srch = 'Message Board'
    else:
        srch = None

    logger.info(f"Total responses: {count}")
    invalid = 0
    if srch:
        logger.info(f"Outputs without '{srch}':")
        for fn in sorted(glob.glob(f"{outdir}/*.org.txt")):
            length = os.path.getsize(fn)
            with open(fn) as f:
                data = f.read()
            if srch not in data:
                logger.info(f"host: {pfname(fn)}  length: {length}")
                logger.info(data)
                logger.info("====================================================")
                invalid += 1
        logger.info(f"Invalid responses: {invalid}")
    return 0 if invalid == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
