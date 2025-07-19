"""
unsmash.py -

INPUTS - files on the command line
         $HOME/spring26/csci-e-11-config.toml

ACTION - searches for smashedemail and replaces with email smashed using the CSCI-E-11 email smashing algorithm
"""

import shutil
import os
import tomllib

REPO_NAME = 'spring26'
CONF_FILENAME = 'csci-e-11-config.toml'
DESCRIPTION="Replace 'smashedemail' with the user's actual smashed email."

def make_smashed_email(email):
    return "".join(email.replace("@",".").split(".")[0:2])

def transform_file(fname, smashed_email):

    # Make a copy of the original if there isn't yet a copy
    original_copy = fname + "-original"
    if not os.path.exists(original_copy):
        shutil.copyfile( fname, original_copy)
        print(f"copied {fname} → {original_copy}")

    with open(original_copy,"r") as f:
        buf = f.read().replace("smashedemail", smashed_email)
    with open(fname, "w") as f:
        f.write(buf)
        print(f"transformed {original_copy} → {fname}")

if __name__=="__main__":
    import argparse
    parser = argparse.ArgumentParser(description=DESCRIPTION,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("filenames", nargs="+", help="Files to transform")
    args = parser.parse_args()

    conf_file = os.path.join( os.getenv("HOME"), "spring26", CONF_FILENAME)
    try:
        with open(conf_file,'rb') as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        print(f"Please create the file {conf_file}",file=sys.stderr)
        exit(1)

    try:
        email = data['general']['email']
    except KeyError:
        print(f"Config file {conf_file} lacks a [general] section or an email= property")
        exit(1)

    smashed_email = make_smashed_email(email)

    for fname in args.filenames:
        transform_file(fname, smashed_email)
