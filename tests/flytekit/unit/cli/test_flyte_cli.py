import mock as _mock
import pytest
import responses as _responses
from click.testing import CliRunner as _CliRunner

from flytekit.clis.flyte_cli import main as _main
from flytekit.exceptions.user import FlyteAssertion
from flytekit.models import filters as _filters
from flytekit.models.admin import common as _admin_common
from flytekit.models.core import identifier as _core_identifier
from flytekit.models.project import Project as _Project

mm = _mock.MagicMock()
mm.return_value = 100


@_mock.patch("flytekit.clis.flyte_cli.main.utils")
def test__extract_files_with_unspecified_resource_type(load_mock):
    id = _core_identifier.Identifier(
        _core_identifier.ResourceType.UNSPECIFIED,
        "myproject",
        "development",
        "name",
        "v",
    )

    load_mock.load_proto_from_file.return_value = id.to_flyte_idl()
    with pytest.raises(FlyteAssertion):
        _main._extract_pair("a", "b", "myflyteproject", "development", "v", {})


def _identity_dummy(a, b, project, domain, version, patches):
    return (a, b)


@_mock.patch("flytekit.clis.flyte_cli.main._extract_pair", new=_identity_dummy)
def test__extract_files_pair_iterator():
    results = _main._extract_files("myflyteproject", "development", "v", ["1.pb", "2.pb"], None)
    assert [("1.pb", 1), ("2.pb", 2)] == results


@_mock.patch("flytekit.clis.flyte_cli.main._friendly_client.SynchronousFlyteClient")
def test_list_projects(mock_client):
    mock_client().list_projects_paginated.return_value = ([], "")
    runner = _CliRunner()
    result = runner.invoke(
        _main._flyte_cli, ["list-projects", "-h", "a.b.com", "-i", "--filter", "ne(state,-1)", "--sort-by", "asc(name)"]
    )
    assert result.exit_code == 0
    mock_client().list_projects_paginated.assert_called_with(
        limit=100,
        token="",
        filters=[_filters.Filter.from_python_std("ne(state,-1)")],
        sort_by=_admin_common.Sort.from_python_std("asc(name)"),
    )


@_mock.patch("flytekit.clis.flyte_cli.main._friendly_client.SynchronousFlyteClient")
def test_archive_project(mock_client):
    runner = _CliRunner()
    result = runner.invoke(_main._flyte_cli, ["archive-project", "-p", "foo", "-h", "a.b.com", "-i"])
    assert result.exit_code == 0
    mock_client().update_project.assert_called_with(_Project.archived_project("foo"))


@_mock.patch("flytekit.clis.flyte_cli.main._friendly_client.SynchronousFlyteClient")
def test_activate_project(mock_client):
    runner = _CliRunner()
    result = runner.invoke(_main._flyte_cli, ["activate-project", "-p", "foo", "-h", "a.b.com", "-i"])
    assert result.exit_code == 0
    mock_client().update_project.assert_called_with(_Project.active_project("foo"))


@_responses.activate
def test_setup_config_secure_mode():
    runner = _CliRunner()
    data = {
        "client_id": "123abc123",
        "redirect_uri": "http://localhost:53593/callback",
        "scopes": ["scope_1", "scope_2"],
        "authorization_metadata_key": "fake_key",
    }
    _responses.add(_responses.GET, "https://flyte.company.com/config/v1/flyte_client", json=data, status=200)
    with _mock.patch("configparser.ConfigParser.write"):
        result = runner.invoke(_main._flyte_cli, ["setup-config", "-h", "flyte.company.com"])
    assert result.exit_code == 0


@_responses.activate
def test_setup_config_insecure_mode():
    runner = _CliRunner()

    _responses.add(_responses.GET, "http://flyte.company.com/config/v1/flyte_client", json={}, status=200)
    with _mock.patch("configparser.ConfigParser.write"):
        result = runner.invoke(_main._flyte_cli, ["setup-config", "-h", "flyte.company.com", "-i"])
    assert result.exit_code == 0


def test_flyte_cli():
    runner = _CliRunner()
    result = runner.invoke(_main._flyte_cli, ["-c", "~/.flyte/config", "activate-project", "-i"])
    assert "Config file not found at ~/.flyte/config" in result.output
    with _mock.patch("os.path.exists") as mock_exists:
        result = runner.invoke(_main._flyte_cli, ["activate-project", "-p", "foo", "-i"])
        assert "Using default config file at" in result.output
        mock_exists.return_value = True
        result = runner.invoke(_main._flyte_cli, ["-c", "~/.flyte/config", "activate-project", "-i"])
        assert "Using config file at ~/.flyte/config" in result.output
