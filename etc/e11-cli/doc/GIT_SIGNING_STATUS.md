# Git Commit Signing Status

## ✅ Configured for AI Commits

This repository is now configured to use a separate GPG key for commits made by Cursor AI.

### Current Configuration

- **Signing Key ID**: `8DC054ABB5B6B662`
- **Key Fingerprint**: `2E0DE68E06B81054B78734928DC054ABB5B6B662`
- **Email**: `simsong+cursor@acm.org`
- **Name**: `Cursor AI Assistant`
- **Key Type**: Ed25519 (signing) + CV25519 (encryption)
- **Status**: ✅ Verified and working

### Repository Settings

```bash
user.signingkey = 8DC054ABB5B6B662
user.email = simsong+cursor@acm.org
commit.gpgsign = true
```

These settings are configured **locally for this repository only**, so:
- Commits in this repo will use the AI key
- Commits in other repos will use your default key (`AAC8DAA47F66CC43`)

### Verification

All commits made in this repository are automatically signed with the AI key. You can verify signatures with:

```bash
git log --show-signature
```

### Export Public Key

If you need to share the public key (e.g., for GitHub verification):

```bash
gpg --armor --export 8DC054ABB5B6B662
```

Or to copy to clipboard:
```bash
gpg --armor --export 8DC054ABB5B6B662 | pbcopy
```

### Key Management

- **List keys**: `gpg --list-secret-keys --keyid-format=long`
- **View key details**: `gpg --list-secret-keys 8DC054ABB5B6B662`
- **Export private key** (backup): `gpg --export-secret-keys --armor 8DC054ABB5B6B662`

### Notes

- The key was created without expiration (Expire-Date: 0)
- The key was created without passphrase protection for automation
- This is a repository-local configuration, so it won't affect other repositories

