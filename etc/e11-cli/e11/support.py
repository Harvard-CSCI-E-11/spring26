import subprocess
import configparser
import os
from os.path import join
from pathlib import Path

REPO_YEAR='spring26'
CONFIG_FILE_NAME =  'e11-config.ini'
CSCIE_BOT_KEYFILE = 'csci-e-11-bot.pub'
DEFAULT_TIMEOUT = 3
STUDENT='student'               # section

def home():
    """Returns home directory. Do not cache, because that breaks monkeypatching"""
    return Path(os.getenv('HOME',''))

def config_path():
    """Return e11 config file as specified by E11_CONFIG variable or $HOME/{CONFIG_FILE_NAME}"""
    try:
        return Path(os.environ['E11_CONFIG'])
    except KeyError:
        return home() / CONFIG_FILE_NAME

def authorized_keys_path():
    """Returns $HOME/.ssh/authorized_keys"""
    return home() / ".ssh" / "authorized_keys"

def bot_pubkey_path():
    """Find the bot public key"""
    for path in [ home() / REPO_YEAR / "etc" / CSCIE_BOT_KEYFILE,
                  home() / "gits" / "csci-e-11" / "etc" / CSCIE_BOT_KEYFILE]:
        if path.exists():
            return path
    raise FileNotFoundError(CSCIE_BOT_KEYFILE)

def bot_pubkey():
    key = bot_pubkey_path().read_text()
    assert key.count("\n")==1 and key.endswith("\n")
    return key

def bot_access_check():
    key = bot_pubkey()
    with authorized_keys_path().open() as f:
        for line in f:
            if line == key:
                return True
    return False


def get_config():
    """Return the config file"""
    cp = configparser.ConfigParser()
    try:
        cp.read_string( config_path().read_text() )
    except FileNotFoundError:
        pass

    if STUDENT not in cp:       # add the section if it doesn't exist
        cp.add_section(STUDENT)
    return cp

def get_ipaddr():
    r = requests.get('https://checkip.amazonaws.com',timeout=DEFAULT_TIMEOUT)
    return r.text.strip()

def on_ec2():
    """https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/identify_ec2_instances.html"""
    try:
        r = subprocess.run(['sudo','-n','dmidecode','--string','system-uuid'],
                           encoding='utf8',
                           capture_output=True,
                           check=True)
    except subprocess.CalledProcessError:
        return False
    return r.stdout.startswith('ec2')

def get_instanceId():           # pylint: disable=invalid-name
    token_url = "http://169.254.169.254/latest/api/token"
    headers = {"X-aws-ec2-metadata-token-ttl-seconds": "21600"}
    response = requests.put(token_url, headers=headers, timeout=1)
    response.raise_for_status()
    token = response.text
    metadata_url = "http://169.254.169.254/latest/meta-data/instance-id"
    headers = {"X-aws-ec2-metadata-token": token}
    response = requests.get(metadata_url, headers=headers, timeout=1)
    response.raise_for_status()
    return response.text
