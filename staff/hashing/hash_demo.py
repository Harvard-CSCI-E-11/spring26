"""
find a number that, when hashed, produces as SHA256 hash with a specific number of leading zeros.
"""

import argparse
import hashlib

if __name__=="__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--verbose",action='store_true')
    parser.add_argument("zeros",type=int)
    args = parser.parse_args()
    zeros = "0" * args.zeros

    found = 0
    n     = 0
    while not found:
        hasher = hashlib.sha256()
        hasher.update(str(n).encode('utf-8'))
        hexdigest = hasher.hexdigest()
        found = hexdigest[0:args.zeros] == zeros
        if found or args.verbose:
            print(f"SHA256('{n}')={hexdigest}")
        n += 1
