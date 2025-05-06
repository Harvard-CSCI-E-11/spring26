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
import io
import mimetypes
from urllib.parse import urlparse

LABS = [4, 5, 7]
RETRIES = 3
RETRY_DELAY = 2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_CACHE_SECONDS = 60 * 60
MYDIR = dirname(__file__)

sys.path.append(join(dirname(dirname(__file__))))
from s3watch.event_consumer.app import extract

report = io.StringIO()

def download_image(image_url, save_path):
    r = requests.get(image_url, stream=True)
    if r.status_code == 200:
        with open(save_path, 'wb') as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)
        return True
    return False

def test_https_cert(hostname):
    """Test HTTPS certificate and fetch root page content."""
    for attempt in range(RETRIES):
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
        except (requests.exceptions.ConnectionError, socket.gaierror) as e:
            logger.warning(f"Connection error for {hostname} (attempt {attempt+1}/{RETRIES}): {e}")
            if attempt < RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise AssertionError(f"Failed to validate cert or get page for {hostname} after {RETRIES} attempts: {e}")
        except Exception as e:
            raise AssertionError(f"Failed to validate cert or get page: {e}")

def collect(*,outdir, lab, limit=None, livecdf=False, hostnames_for_cdf=None):
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

                images_found = 0
                images_downloaded = 0
                if lab in LABS:
                    url = f'https://{domain}/api/get-messages'
                    for attempt in range(RETRIES):
                        try:
                            logger.debug("** url: %s", url)
                            data = requests.get(url).json()
                            message_count.append(len(data))
                            if lab in [5, 7]:
                                images_dir = os.path.join(outdir, "images")
                                os.makedirs(images_dir, exist_ok=True)
                                for msg in data:
                                    msg_id = msg.get("message_id")
                                    if msg_id is not None:
                                        img_api_url = f"https://{domain}/api/get-image?image_id={msg_id}"
                                        img_resp = requests.get(img_api_url, allow_redirects=False)
                                        if img_resp.status_code == 302:
                                            s3_url = img_resp.headers.get("Location")
                                            if s3_url and "amazonaws.com" in s3_url:
                                                images_found += 1
                                                ext = os.path.splitext(urlparse(s3_url).path)[1]
                                                if not ext:
                                                    head = requests.head(s3_url)
                                                    ext = mimetypes.guess_extension(head.headers.get("Content-Type", ""))
                                                    if not ext:
                                                        ext = ".img"
                                                save_path = os.path.join(images_dir, f"{domain}.{msg_id}{ext}")
                                                if download_image(s3_url, save_path):
                                                    images_downloaded += 1
                            break  # Success, exit retry loop
                        except requests.exceptions.SSLError:
                            logger.info("** invalid SSL: %s", domain)
                            break
                        except requests.exceptions.JSONDecodeError:
                            logger.info("** Bad JSON: %s", url)
                            break
                        except requests.exceptions.ConnectionError as e:
                            logger.warning(f"Connection error for {domain} (attempt {attempt+1}/{RETRIES}): {e}")
                            if attempt < RETRIES - 1:
                                time.sleep(RETRY_DELAY)
                            else:
                                logger.error(f"Failed to connect to {domain} after {RETRIES} attempts.")
                if lab in [5, 7]:
                    resp['images_found'] = images_found
                    resp['images_downloaded'] = images_downloaded
                return resp
            except AssertionError as e:
                logger.warning(f"{domain}: {e}")
                return None

        host_data = [(st + append + ".csci-e-11.org", outdir) for st in students]
        if limit is not None:
            host_data = host_data[:limit]
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(process_host, host_data)
        results = [r for r in results if r is not None]
        expiration_times = [r['expires'] for r in results]
        dns_lab_certs    = [r['dns_lab_cert'] for r in results]
        for v in sorted([ (r['expires'],r['tls_certificate_names']) for r in results]):
            logger.info(v)

        try:
            avg = math.fsum(message_count)/len(message_count)
            mx  = max(message_count)
        except ZeroDivisionError:
            avg = 'n/a'
            mx  = 'n/a'

        logger.debug("dns_lab_certs: %s",dns_lab_certs)
        logger.debug("expiration_times: %s",expiration_times)
        line = ("Domains with operational API: %s  with >0 messages: %s  average number of messages: %s  max: %s" %
                (len(message_count), len([m for m in message_count if m>0]), avg, mx))
        logger.info(line)
        report.write(line + "\n")

        # Count unique certificate names containing each lab
        lab_counts = {f'lab{lab}': set() for lab in LABS}
        exclusive_counts = {f'lab{lab}': set() for lab in LABS}
        for r in results:
            names = r['tls_certificate_names']
            labs_in_names = set()
            for name in names:
                for lab in lab_counts:
                    if lab in name:
                        lab_counts[lab].add(name)
                        labs_in_names.add(lab)
            # Check for exclusivity: only one lab present, and all names are for that lab
            if len(labs_in_names) == 1:
                only_lab = next(iter(labs_in_names))
                if all(only_lab in name for name in names):
                    exclusive_counts[only_lab].update(names)
        for lab, names in lab_counts.items():
            line = f"{lab}: {len(names)} hosts, exclusive hosts: {len(exclusive_counts[lab])}"
            logger.info(line)
            report.write(line + "\n")

        if lab in [5, 7]:
            total_images_found = sum(r.get('images_found', 0) for r in results)
            total_images_downloaded = sum(r.get('images_downloaded', 0) for r in results)
            line = f"Lab {lab}: {total_images_found} messages with images in S3, {total_images_downloaded} images downloaded."
            logger.info(line)
            report.write(line + "\n")

        if expiration_times:
            host_exp_pairs = [(r['expires'], r['hostname']) for r in results]
            days_until_expiration = [(exp - current_date).days for exp, hn in host_exp_pairs]
            days_until_expiration = [d for d in days_until_expiration if d >= 0]
            if days_until_expiration:
                # Sort both expiration days and hostnames together
                sorted_pairs = sorted([(exp, hn) for exp, hn in host_exp_pairs if (exp - current_date).days >= 0])
                sorted_days = np.array([(exp - current_date).days for exp, hn in sorted_pairs])
                sorted_hostnames = [hn for exp, hn in sorted_pairs]
                cdf = np.arange(1, len(sorted_days) + 1) / len(sorted_days)
                plt.figure(figsize=(12, 8))
                scatter = plt.scatter(sorted_days, cdf, marker='.', color='b')
                plt.grid(True)
                plt.xlabel('Days Until Certificate Expiration')
                plt.ylabel('Cumulative Probability')
                plt.title(f'CDF of Certificate Expiration Dates - Lab {lab}')
                plt.axvline(x=90, color='r', linestyle='--', label='90 days')
                plt.legend()
                plot_path = join(outdir, 'certificate_expiration_cdf.png')
                plt.savefig(plot_path, dpi=300, bbox_inches='tight')
                logger.info(f"CDF plot saved as {plot_path}")

                if livecdf:
                    # Interactive mouse-over for hostnames
                    annot = plt.gca().annotate("", xy=(0,0), xytext=(20,20),
                                               textcoords="offset points",
                                               bbox=dict(boxstyle="round", fc="w"),
                                               arrowprops=dict(arrowstyle="->"))
                    annot.set_visible(False)
                    def update_annot(ind):
                        pos = scatter.get_offsets()[ind["ind"][0]]
                        annot.xy = pos
                        text = f"{sorted_hostnames[ind['ind'][0]]}"
                        annot.set_text(text)
                        annot.get_bbox_patch().set_alpha(0.8)
                    def hover(event):
                        vis = annot.get_visible()
                        if event.inaxes == plt.gca():
                            cont, ind = scatter.contains(event)
                            if cont:
                                update_annot(ind)
                                annot.set_visible(True)
                                plt.gcf().canvas.draw_idle()
                            else:
                                if vis:
                                    annot.set_visible(False)
                                    plt.gcf().canvas.draw_idle()
                    plt.gcf().canvas.mpl_connect("motion_notify_event", hover)
                    print("Showing interactive CDF plot...")
                    plt.show()
                else:
                    plt.close()
                logger.info(f"Certificates analyzed: {len(sorted_days)}")
                logger.info(f"Median days until expiration: {np.median(sorted_days):.0f}")
            else:
                logger.info("No valid expiration dates to plot (all certificates expired)")
    except Exception as e:
        logger.error(f"Collection failed: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter, description='Test the student VMs')
    parser.add_argument("--collect", action='store_true', help='Collect the sites. By default do this if we have not run in an hour')
    parser.add_argument("--lab", type=int, default=3, help='Specify which lab')
    parser.add_argument("--debug", action='store_true', help='Enable debug logging')
    parser.add_argument("--limit", type=int, default=None, help='Limit the number of hosts to examine')
    parser.add_argument("--livecdf", action='store_true', help='Show CDF plot in a window with interactive hostnames')
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    outdir = os.path.abspath(f"{MYDIR}/out/lab{args.lab}")
    os.makedirs(outdir, exist_ok=True)

    if args.collect or (os.path.exists(outdir) and (time.time() - os.path.getmtime(outdir)) > MAX_CACHE_SECONDS):
        # Prepare hostnames for CDF if livecdf is requested
        hostnames_for_cdf = None
        if args.livecdf:
            # You need to pass the hostnames in the same order as expiration_times
            # This requires a small change in collect() to accept and use this list
            # For now, just pass None and let collect() handle it
            pass
        collect(outdir=outdir, lab=args.lab, limit=args.limit, livecdf=args.livecdf, hostnames_for_cdf=hostnames_for_cdf)

    logger.info("outdir: %s",outdir)

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
    return report.getvalue(), (0 if invalid == 0 else 1)

if __name__ == "__main__":
    rep, rc = main()
    print(rep)
    sys.exit(rc)
