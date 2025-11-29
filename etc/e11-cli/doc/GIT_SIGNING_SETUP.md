# Git Commit Signing Setup for Cursor AI

This document explains how to set up a separate GPG key for commits made by Cursor AI assistant.

## Current Configuration

- Current signing key: `AAC8DAA47F66CC43`
- Commit signing: Enabled globally
- GPG program: `/opt/homebrew/bin/gpg`

## Option 1: Create a New GPG Key for AI Commits

### Step 1: Generate a New GPG Key

Run this command to create a new Ed25519 key for AI commits:

```bash
gpg --full-generate-key
```

When prompted:
- Select option `(11) ECC (sign only)`
- Select `Ed25519`
- Key size: `256` (default)
- Key valid for: `0` (does not expire) or your preferred duration
- Real name: `Cursor AI Assistant`
- Email address: `simsong+cursor@acm.org` (or your preferred email)
- Comment: (optional) `For AI-generated commits`

### Step 2: List Your Keys to Get the New Key ID

```bash
gpg --list-secret-keys --keyid-format=long
```

Look for the new key and copy its key ID (the part after the key type, e.g., `ABCD1234EFGH5678`).

### Step 3: Configure Git to Use the New Key

You can configure Git to use the AI key in one of these ways:

#### A. Via Environment Variable (Recommended for AI commits)

Set an environment variable before running Cursor/AI commands:

```bash
export GIT_COMMITTER_SIGNINGKEY="<NEW_KEY_ID>"
export GIT_AUTHOR_SIGNINGKEY="<NEW_KEY_ID>"
```

Or create a script that sets these:

```bash
#!/bin/bash
# ~/bin/git-with-ai-key.sh
export GIT_COMMITTER_SIGNINGKEY="<NEW_KEY_ID>"
export GIT_AUTHOR_SIGNINGKEY="<NEW_KEY_ID>"
git "$@"
```

#### B. Via Git Config Per-Repository

In the repository, set:

```bash
git config user.signingkey "<NEW_KEY_ID>"
```

#### C. Via Git Config with Conditional Include (Git 2.13+)

Create a conditional config that applies only in this directory:

```bash
# In .git/config or ~/.gitconfig
[includeIf "gitdir:~/gits/spring26/etc/e11-cli/"]
    path = ~/.gitconfig-ai
```

Then create `~/.gitconfig-ai`:

```
[user]
    signingkey = <NEW_KEY_ID>
```

## Option 2: Use Existing Key but Configure Conditionally

If you prefer to create a key later, you can set up Git to use environment variables:

1. Set up environment variables in your shell profile:

```bash
# Add to ~/.zshrc or ~/.bashrc
export GIT_COMMITTER_SIGNINGKEY="${GIT_COMMITTER_SIGNINGKEY:-AAC8DAA47F66CC43}"
export GIT_AUTHOR_SIGNINGKEY="${GIT_AUTHOR_SIGNINGKEY:-AAC8DAA47F66CC43}"
```

2. When you want Cursor to use a different key, set:

```bash
export GIT_COMMITTER_SIGNINGKEY="<AI_KEY_ID>"
export GIT_AUTHOR_SIGNINGKEY="<AI_KEY_ID>"
```

3. Cursor can then use these environment variables automatically.

## Option 3: Use a Separate Git Wrapper Script

Create a wrapper script that Cursor can use:

```bash
#!/bin/bash
# ~/bin/git-ai

# Set AI-specific signing key
export GIT_COMMITTER_SIGNINGKEY="<AI_KEY_ID>"
export GIT_AUTHOR_SIGNINGKEY="<AI_KEY_ID>"

# Use your existing user info or set AI-specific info
export GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-Simson L. Garfinkel}"
export GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-simsong+cursor@acm.org}"
export GIT_COMMITTER_NAME="${GIT_COMMITTER_NAME:-Simson L. Garfinkel}"
export GIT_COMMITTER_EMAIL="${GIT_COMMITTER_EMAIL:-simsong+cursor@acm.org}"

# Execute git with all arguments
exec /usr/bin/git "$@"
```

Then configure Cursor to use this script, or create an alias.

## Recommended Approach

For simplicity, I recommend:

1. **Create a new GPG key** for AI commits with email `simsong+cursor@acm.org`
2. **Use repository-local Git config** to set the signing key for this specific repository
3. This way, commits in this repo use the AI key, while other repos use your default key

Commands:

```bash
# 1. Create the key (interactive)
gpg --full-generate-key

# 2. Get the new key ID
gpg --list-secret-keys --keyid-format=long

# 3. Configure this repository to use it
cd /Users/simsong/gits/spring26/etc/e11-cli
git config user.signingkey "<NEW_KEY_ID>"
```

## Verifying the Setup

After configuration, verify:

```bash
# Check current signing key
git config --get user.signingkey

# Test signing (dry-run)
echo "test" | git commit --allow-empty -F - -S

# Check signature
git log --show-signature -1
```

## Exporting the Public Key

If you need to share or backup the public key:

```bash
# Export public key
gpg --armor --export <KEY_ID> > ai-signing-key.pub

# Or to clipboard (macOS)
gpg --armor --export <KEY_ID> | pbcopy
```

## Troubleshooting

- **Key not found**: Make sure the key ID is correct and the key is in your GPG keyring
- **Passphrase prompts**: Set up `gpg-agent` with pinentry or use a key without passphrase for automation
- **Git not signing**: Verify `git config commit.gpgsign` is `true`

