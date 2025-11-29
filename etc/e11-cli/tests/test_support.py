"""Tests for e11.support module."""
import configparser
from pathlib import Path

import pytest

from e11 import support


@pytest.fixture
def temp_home(tmp_path, monkeypatch, _isolate_env):
    """Create a temporary home directory and set HOME environment variable."""
    # _isolate_env already sets HOME, but we need a fresh one for these tests
    home_dir = tmp_path / "home"
    home_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home_dir))
    return home_dir


@pytest.fixture
def config_file(temp_home):
    """Create a test config file."""
    config_path = temp_home / "e11-config.ini"
    config_path.write_text(
        "[student]\n"
        "email = test@example.org\n"
        "preferred_name = Test User\n"
        "public_ip = 1.2.3.4\n"
        "course_key = key1234\n"
    )
    return config_path


@pytest.fixture
def repo_dir(temp_home):
    """Create a repo directory structure."""
    repo = temp_home / "spring26" / "etc"
    repo.mkdir(parents=True)
    return repo


@pytest.fixture
def bot_key_file(repo_dir):
    """Create a bot public key file."""
    key_file = repo_dir / "csci-e-11-bot.pub"
    key_content = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEK/6zvwwWOO+ui4zbUYN558g+LKh5N8f3KpoyKKrmoR auto-grader-do-not-delete\n"
    key_file.write_text(key_content)
    return key_file


class TestHome:
    """Test cases for home() function."""

    def test_home_returns_path_from_env(self, temp_home, monkeypatch):
        """Test that home() returns HOME from environment."""
        result = support.home()
        assert result == temp_home
        assert isinstance(result, Path)

    def test_home_returns_empty_path_when_not_set(self, monkeypatch):
        """Test that home() returns empty Path when HOME not set."""
        monkeypatch.delenv("HOME", raising=False)
        result = support.home()
        assert result == Path("")
        assert isinstance(result, Path)


class TestConfigPath:
    """Test cases for config_path() function."""

    def test_config_path_from_env_var(self, tmp_path, monkeypatch):
        """Test config_path returns path from E11_CONFIG env var."""
        custom_config = tmp_path / "custom-config.ini"
        monkeypatch.setenv("E11_CONFIG", str(custom_config))
        result = support.config_path()
        assert result == custom_config

    def test_config_path_default_location(self, temp_home):
        """Test config_path returns default location when env var not set."""
        expected = temp_home / "e11-config.ini"
        result = support.config_path()
        assert result == expected


class TestAuthorizedKeysPath:
    """Test cases for authorized_keys_path() function."""

    def test_authorized_keys_path(self, temp_home):
        """Test authorized_keys_path returns correct path."""
        expected = temp_home / ".ssh" / "authorized_keys"
        result = support.authorized_keys_path()
        assert result == expected


class TestBotPubkeyPath:
    """Test cases for bot_pubkey_path() function."""

    def test_bot_pubkey_path_finds_in_spring26(self, repo_dir, bot_key_file):
        """Test bot_pubkey_path finds key in spring26/etc directory."""
        result = support.bot_pubkey_path()
        assert result == bot_key_file
        assert result.exists()

    def test_bot_pubkey_path_finds_in_gits(self, temp_home):
        """Test bot_pubkey_path finds key in gits directory."""
        gits_path = temp_home / "gits" / "csci-e-11" / "etc"
        gits_path.mkdir(parents=True)
        key_file = gits_path / "csci-e-11-bot.pub"
        key_content = "ssh-ed25519 test-key\n"
        key_file.write_text(key_content)

        result = support.bot_pubkey_path()
        assert result == key_file
        assert result.exists()

    def test_bot_pubkey_path_prioritizes_spring26_over_gits(self, repo_dir, temp_home, bot_key_file):
        """Test bot_pubkey_path prefers spring26 location over gits."""
        # Create key in both locations
        gits_path = temp_home / "gits" / "csci-e-11" / "etc"
        gits_path.mkdir(parents=True)
        gits_key = gits_path / "csci-e-11-bot.pub"
        gits_key.write_text("ssh-ed25519 gits-key\n")

        result = support.bot_pubkey_path()
        # Should prefer spring26 location
        assert result == bot_key_file

    def test_bot_pubkey_path_raises_when_not_found(self, temp_home):
        """Test bot_pubkey_path raises FileNotFoundError when key doesn't exist."""
        with pytest.raises(FileNotFoundError, match="csci-e-11-bot.pub"):
            support.bot_pubkey_path()


class TestBotPubkey:
    """Test cases for bot_pubkey() function."""

    def test_bot_pubkey_returns_key_content(self, bot_key_file):
        """Test bot_pubkey returns the key file content."""
        result = support.bot_pubkey()
        assert isinstance(result, str)
        assert result.endswith("\n")
        assert result.count("\n") == 1
        assert "ssh-ed25519" in result

    def test_bot_pubkey_validates_format(self, repo_dir):
        """Test bot_pubkey validates that key has exactly one newline."""
        key_file = repo_dir / "csci-e-11-bot.pub"
        key_file.write_text("ssh-ed25519 test-key\n")  # Valid format

        result = support.bot_pubkey()
        assert result == "ssh-ed25519 test-key\n"

    def test_bot_pubkey_raises_on_invalid_format(self, repo_dir):
        """Test bot_pubkey raises AssertionError on invalid format."""
        key_file = repo_dir / "csci-e-11-bot.pub"
        key_file.write_text("ssh-ed25519 test-key\n\n")  # Two newlines - invalid

        with pytest.raises(AssertionError):
            support.bot_pubkey()


class TestBotAccessCheck:
    """Test cases for bot_access_check() function."""

    def test_bot_access_check_returns_true_when_present(self, temp_home, bot_key_file):
        """Test bot_access_check returns True when key is in authorized_keys."""
        authorized_keys = temp_home / ".ssh" / "authorized_keys"
        authorized_keys.parent.mkdir(parents=True)
        key_content = support.bot_pubkey()
        authorized_keys.write_text(key_content)

        result = support.bot_access_check()
        assert result is True

    def test_bot_access_check_returns_false_when_absent(self, temp_home, bot_key_file):
        """Test bot_access_check returns False when key is not in authorized_keys."""
        authorized_keys = temp_home / ".ssh" / "authorized_keys"
        authorized_keys.parent.mkdir(parents=True)
        authorized_keys.write_text("ssh-rsa some-other-key\n")

        result = support.bot_access_check()
        assert result is False

    def test_bot_access_check_handles_empty_file(self, temp_home, bot_key_file):
        """Test bot_access_check handles empty authorized_keys file."""
        authorized_keys = temp_home / ".ssh" / "authorized_keys"
        authorized_keys.parent.mkdir(parents=True)
        authorized_keys.write_text("")

        result = support.bot_access_check()
        assert result is False

    def test_bot_access_check_handles_multiple_keys(self, temp_home, bot_key_file):
        """Test bot_access_check finds key among multiple keys."""
        authorized_keys = temp_home / ".ssh" / "authorized_keys"
        authorized_keys.parent.mkdir(parents=True)
        key_content = support.bot_pubkey()
        authorized_keys.write_text(
            "ssh-rsa key1\n"
            f"{key_content}"
            "ssh-rsa key2\n"
        )

        result = support.bot_access_check()
        assert result is True


class TestGetConfig:
    """Test cases for get_config() function."""

    def test_get_config_reads_existing_file(self, config_file):
        """Test get_config reads and parses existing config file."""
        result = support.get_config()
        assert isinstance(result, configparser.ConfigParser)
        assert "student" in result
        assert result["student"]["email"] == "test@example.org"
        assert result["student"]["preferred_name"] == "Test User"

    def test_get_config_creates_section_if_missing(self, temp_home):
        """Test get_config creates student section if file exists but section missing."""
        config_path = temp_home / "e11-config.ini"
        config_path.write_text("[other]\nkey = value\n")

        result = support.get_config()
        assert "student" in result
        assert "other" in result

    def test_get_config_handles_missing_file(self, temp_home):
        """Test get_config handles missing config file gracefully."""
        # Ensure file doesn't exist (remove if _isolate_env created it)
        config_path = temp_home / "e11-config.ini"
        if config_path.exists():
            config_path.unlink()

        result = support.get_config()
        assert isinstance(result, configparser.ConfigParser)
        assert "student" in result

    def test_get_config_with_custom_location(self, tmp_path, monkeypatch):
        """Test get_config reads from custom E11_CONFIG location."""
        custom_config = tmp_path / "custom.ini"
        custom_config.write_text("[student]\nemail = custom@example.org\n")
        monkeypatch.setenv("E11_CONFIG", str(custom_config))

        result = support.get_config()
        assert result["student"]["email"] == "custom@example.org"

