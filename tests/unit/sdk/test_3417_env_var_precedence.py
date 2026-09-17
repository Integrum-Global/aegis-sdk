"""
Tier 1: SDK environment-variable naming -- AEGIS_* supersedes AGENTIC_OS_*.

The product's own environment uses the ``AEGIS_`` prefix; the SDK shipped
reading ``AGENTIC_OS_``. Architects set the documented product names and the
SDK did not read them.

Three invariants, one per axis, and a no-false-positive control:

1. ``AEGIS_*`` wins when both names are set.
2. ``AGENTIC_OS_*`` still resolves -- this is a published SDK with external
   consumers, so the old name is deprecated, not removed.
3. The old name emits a deprecation warning ONCE per variable per process,
   naming its replacement -- not once per read.
4. With neither name set, the pre-existing ConfigurationError is unchanged.

Each case is written to be discriminating: it fails if the precedence is
reversed, if either name stops resolving, or if the warning fires zero times
or once per read.
"""

import logging
from pathlib import Path

import pytest

from aegis_sdk import config as config_module
from aegis_sdk.client import AgenticOSClient
from aegis_sdk.config import ClientConfig
from aegis_sdk.exceptions import ConfigurationError

# Every setting from_env() reads.
SUFFIXES = ("BASE_URL", "API_KEY", "TIMEOUT", "MAX_RETRIES", "VERIFY_SSL", "DEBUG")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Both prefixes cleared, and the one-time warn ledger reset.

    Without the reset a test that runs second would see the warning already
    spent and pass vacuously.
    """
    for suffix in SUFFIXES:
        monkeypatch.delenv(f"AEGIS_{suffix}", raising=False)
        monkeypatch.delenv(f"AGENTIC_OS_{suffix}", raising=False)
    config_module._warned_legacy_env.clear()
    yield
    config_module._warned_legacy_env.clear()


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestEnvNamePrecedence:
    """AEGIS_* is authoritative; AGENTIC_OS_* is the deprecated fallback."""

    def test_aegis_name_alone_is_read(self, monkeypatch):
        """Case 1: only AEGIS_* set -- the product's documented names work."""
        monkeypatch.setenv("AEGIS_BASE_URL", "https://aegis-name.example.com")
        monkeypatch.setenv("AEGIS_API_KEY", "key_from_aegis_name")
        monkeypatch.setenv("AEGIS_TIMEOUT", "45.0")
        monkeypatch.setenv("AEGIS_MAX_RETRIES", "5")
        monkeypatch.setenv("AEGIS_VERIFY_SSL", "false")
        monkeypatch.setenv("AEGIS_DEBUG", "true")

        config = ClientConfig.from_env()

        assert config.base_url == "https://aegis-name.example.com"
        assert config.api_key == "key_from_aegis_name"
        assert config.timeout == 45.0
        assert config.max_retries == 5
        assert config.verify_ssl is False
        assert config.debug is True

    def test_aegis_name_alone_does_not_warn(self, monkeypatch, recwarn):
        """The supported name must be silent -- a warning on it would train
        every consumer to ignore the deprecation notice."""
        monkeypatch.setenv("AEGIS_BASE_URL", "https://aegis-name.example.com")

        ClientConfig.from_env()

        assert [w for w in recwarn if issubclass(w.category, DeprecationWarning)] == []

    def test_legacy_name_alone_is_still_read(self, monkeypatch):
        """Case 2: only AGENTIC_OS_* set -- external consumers keep working."""
        monkeypatch.setenv("AGENTIC_OS_BASE_URL", "https://legacy-name.example.com")
        monkeypatch.setenv("AGENTIC_OS_API_KEY", "key_from_legacy_name")
        monkeypatch.setenv("AGENTIC_OS_TIMEOUT", "45.0")
        monkeypatch.setenv("AGENTIC_OS_MAX_RETRIES", "5")
        monkeypatch.setenv("AGENTIC_OS_VERIFY_SSL", "false")
        monkeypatch.setenv("AGENTIC_OS_DEBUG", "true")

        config = ClientConfig.from_env()

        assert config.base_url == "https://legacy-name.example.com"
        assert config.api_key == "key_from_legacy_name"
        assert config.timeout == 45.0
        assert config.max_retries == 5
        assert config.verify_ssl is False
        assert config.debug is True

    def test_aegis_name_wins_when_both_are_set(self, monkeypatch):
        """Case 3: both set -- AEGIS_* wins. This is the case a naive
        implementation (checking the legacy name first, or passing the legacy
        value as the new name's default) gets backwards."""
        for suffix, aegis_value, legacy_value in (
            ("BASE_URL", "https://wins.example.com", "https://loses.example.com"),
            ("API_KEY", "key_wins", "key_loses"),
            ("TIMEOUT", "11.0", "99.0"),
            ("MAX_RETRIES", "7", "99"),
        ):
            monkeypatch.setenv(f"AEGIS_{suffix}", aegis_value)
            monkeypatch.setenv(f"AGENTIC_OS_{suffix}", legacy_value)
        # Booleans get opposite polarity on each name, so a reversed
        # precedence flips the assertion rather than coinciding with it.
        monkeypatch.setenv("AEGIS_VERIFY_SSL", "false")
        monkeypatch.setenv("AGENTIC_OS_VERIFY_SSL", "true")
        monkeypatch.setenv("AEGIS_DEBUG", "true")
        monkeypatch.setenv("AGENTIC_OS_DEBUG", "false")

        config = ClientConfig.from_env()

        assert config.base_url == "https://wins.example.com"
        assert config.api_key == "key_wins"
        assert config.timeout == 11.0
        assert config.max_retries == 7
        assert config.verify_ssl is False
        assert config.debug is True

    def test_neither_name_set_raises_unchanged_configuration_error(self):
        """Case 4, the no-false-positive control: with neither name set the
        pre-existing ConfigurationError still raises, and still names the
        legacy variable so existing consumer runbooks and error-matching
        stay valid."""
        with pytest.raises(ConfigurationError) as excinfo:
            ClientConfig.from_env()

        message = str(excinfo.value)
        assert "AEGIS_BASE_URL" in message
        assert "AGENTIC_OS_BASE_URL" in message


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestLegacyNameDeprecationWarning:
    """Invariant 3: one warning per legacy variable per process."""

    def test_legacy_name_warns_naming_its_replacement(self, monkeypatch):
        monkeypatch.setenv("AGENTIC_OS_BASE_URL", "https://legacy-name.example.com")

        with pytest.warns(DeprecationWarning) as records:
            ClientConfig.from_env()

        messages = [str(r.message) for r in records]
        assert len(messages) == 1, messages
        # The warning is useless unless it names BOTH the dead variable and
        # the one to set instead.
        assert "AGENTIC_OS_BASE_URL" in messages[0]
        assert "AEGIS_BASE_URL" in messages[0]

    def test_warning_fires_once_not_once_per_read(self, monkeypatch):
        """Three from_env() calls, one warning. A per-read warning would make
        a polling client emit thousands."""
        monkeypatch.setenv("AGENTIC_OS_BASE_URL", "https://legacy-name.example.com")

        with pytest.warns(DeprecationWarning) as records:
            ClientConfig.from_env()
            ClientConfig.from_env()
            ClientConfig.from_env()

        deprecations = [r for r in records if issubclass(r.category, DeprecationWarning)]
        assert len(deprecations) == 1, [str(r.message) for r in deprecations]

    def test_each_legacy_variable_warns_on_its_own_name(self, monkeypatch):
        """Once-per-variable, not once-per-process: a consumer setting three
        legacy names must be told about all three, not just the first."""
        monkeypatch.setenv("AGENTIC_OS_BASE_URL", "https://legacy-name.example.com")
        monkeypatch.setenv("AGENTIC_OS_API_KEY", "key_from_legacy_name")
        monkeypatch.setenv("AGENTIC_OS_TIMEOUT", "45.0")

        with pytest.warns(DeprecationWarning) as records:
            ClientConfig.from_env()

        named = {
            suffix
            for suffix in ("BASE_URL", "API_KEY", "TIMEOUT")
            if any(f"AGENTIC_OS_{suffix}" in str(r.message) for r in records)
        }
        assert named == {"BASE_URL", "API_KEY", "TIMEOUT"}
        assert len(records) == 3, [str(r.message) for r in records]

    def test_warning_is_also_logged_so_it_is_visible_by_default(
        self, monkeypatch, caplog
    ):
        """Python's default filters DROP a DeprecationWarning raised inside a
        library module, so the warnings-only form would be silent for exactly
        the audience it is written for. The log line is what they actually
        see; it must fire once too."""
        monkeypatch.setenv("AGENTIC_OS_BASE_URL", "https://legacy-name.example.com")

        with caplog.at_level(logging.WARNING, logger="aegis_sdk.config"):
            with pytest.warns(DeprecationWarning):
                ClientConfig.from_env()
                ClientConfig.from_env()

        hits = [r for r in caplog.records if "AGENTIC_OS_BASE_URL" in r.getMessage()]
        assert len(hits) == 1, [r.getMessage() for r in hits]
        assert "AEGIS_BASE_URL" in hits[0].getMessage()


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestDeclaredEnvironmentSurface:
    """The variable names must be literal in the source, not composed.

    Composing ``f"AEGIS_{suffix}"`` at call time works at runtime and makes
    every one of these variables invisible to grep and to the repository's
    documented-vs-read drift guard. That regression was introduced and
    caught once already; these tests keep the names searchable.
    """

    def test_every_setting_from_env_reads_is_declared(self):
        assert set(config_module.ENV_NAMES) == set(SUFFIXES)

    def test_declared_names_are_literal_strings_in_the_source(self):
        """Both spellings of every setting appear verbatim in config.py, so a
        reader or a scanner searching for the variable their runbook names
        actually finds it."""
        source = Path(config_module.__file__).read_text(encoding="utf-8")

        missing = [
            name
            for pair in config_module.ENV_NAMES.values()
            for name in pair
            if f'"{name}"' not in source
        ]
        assert missing == [], missing

    def test_unknown_suffix_raises_rather_than_composing_a_dead_name(self):
        """A typo must fail loudly. Composing a name for a variable nobody
        sets would read as 'unconfigured' forever."""
        with pytest.raises(KeyError, match="not a declared SDK environment"):
            config_module.env_names("NO_SUCH_SETTING")


@pytest.mark.unit
@pytest.mark.timeout(5)
class TestClientConstructorHonoursPrecedence:
    """client.py resolves base_url on its own path -- it must agree with
    config.py, or setting AEGIS_BASE_URL works via from_env() and fails via
    the constructor."""

    def test_constructor_reads_aegis_name(self, monkeypatch):
        monkeypatch.setenv("AEGIS_BASE_URL", "https://aegis-name.example.com")

        client = AgenticOSClient()

        assert client.base_url == "https://aegis-name.example.com"

    def test_constructor_still_reads_legacy_name(self, monkeypatch):
        monkeypatch.setenv("AGENTIC_OS_BASE_URL", "https://legacy-name.example.com")

        with pytest.warns(DeprecationWarning):
            client = AgenticOSClient()

        assert client.base_url == "https://legacy-name.example.com"

    def test_constructor_prefers_aegis_name_when_both_set(self, monkeypatch):
        monkeypatch.setenv("AEGIS_BASE_URL", "https://wins.example.com")
        monkeypatch.setenv("AGENTIC_OS_BASE_URL", "https://loses.example.com")

        client = AgenticOSClient()

        assert client.base_url == "https://wins.example.com"

    def test_explicit_base_url_still_beats_both_names(self, monkeypatch):
        """The argument outranks the environment -- unchanged behaviour."""
        monkeypatch.setenv("AEGIS_BASE_URL", "https://env.example.com")
        monkeypatch.setenv("AGENTIC_OS_BASE_URL", "https://legacy.example.com")

        client = AgenticOSClient(base_url="https://explicit.example.com")

        assert client.base_url == "https://explicit.example.com"

    def test_constructor_with_neither_name_raises_naming_both(self):
        with pytest.raises(ConfigurationError) as excinfo:
            AgenticOSClient()

        message = str(excinfo.value)
        assert "AEGIS_BASE_URL" in message
        assert "AGENTIC_OS_BASE_URL" in message
