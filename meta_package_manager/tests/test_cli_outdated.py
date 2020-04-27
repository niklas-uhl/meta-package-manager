# -*- coding: utf-8 -*-
#
# Copyright Kevin Deldycke <kevin@deldycke.com> and contributors.
# All Rights Reserved.
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

# pylint: disable=redefined-outer-name

import pytest
import simplejson as json

from .conftest import MANAGER_IDS, destructive, run_cmd, unless_macos
from .test_cli import CLISubCommandTests


@pytest.fixture
def subcmd():
    return 'outdated'


@pytest.fixture
def install_formula():

    urls = []

    def _install_formula(url):
        urls.append(url)
        code, output, error = run_cmd('brew', 'cask', 'install', url)
        assert code == 0
        assert error == (
            "Warning: macOS's Gatekeeper has been disabled for this "
            "Cask\n")
        return output

    yield _install_formula

    # Remove all installed packages.
    for url in urls:
        package_id = url.split('/')[-1].split('.rb')[0]
        code, output, error = run_cmd(
            'brew', 'cask', 'uninstall', package_id)
        assert code == 0
        assert not error
        assert package_id in output


class TestOutdated(CLISubCommandTests):

    def test_default_all_manager(self, invoke, subcmd):
        result = invoke(subcmd)
        assert result.exit_code == 0
        self.check_manager_selection(result.output)

    @pytest.mark.parametrize('mid', MANAGER_IDS)
    def test_single_manager(self, invoke, mid, subcmd):
        result = invoke('--manager', mid, subcmd)
        assert result.exit_code == 0
        self.check_manager_selection(result.output, {mid})

    def test_json_parsing(self, invoke, subcmd):
        result = invoke('--output-format', 'json', subcmd)
        assert result.exit_code == 0
        data = json.loads(result.output)

        assert data
        assert isinstance(data, dict)
        assert set(data).issubset(MANAGER_IDS)

        for manager_id, info in data.items():
            assert isinstance(manager_id, str)
            assert isinstance(info, dict)

            assert isinstance(info['id'], str)
            assert isinstance(info['name'], str)

            keys = {'errors', 'id', 'name', 'packages'}
            if 'upgrade_all_cli' in info:
                assert isinstance(info['upgrade_all_cli'], str)
                keys.add('upgrade_all_cli')
            assert set(info) == keys

            assert isinstance(info['errors'], list)
            if info['errors']:
                assert set(map(type, info['errors'])) == {str}

            assert info['id'] == manager_id

            assert isinstance(info['packages'], list)
            for pkg in info['packages']:
                assert isinstance(pkg, dict)

                assert set(pkg) == {
                    'id', 'installed_version', 'latest_version', 'name',
                    'upgrade_cli'}

                assert isinstance(pkg['id'], str)
                assert isinstance(pkg['installed_version'], str)
                assert isinstance(pkg['latest_version'], str)
                assert isinstance(pkg['name'], str)
                assert isinstance(pkg['upgrade_cli'], str)

    def test_cli_format_plain(self, invoke, subcmd):
        result = invoke(
            '--output-format', 'json', subcmd, '--cli-format', 'plain')
        for outdated in json.loads(result.output).values():
            for infos in outdated['packages']:
                assert isinstance(infos['upgrade_cli'], str)

    def test_cli_format_fragments(self, invoke, subcmd):
        result = invoke(
            '--output-format', 'json', subcmd, '--cli-format', 'fragments')
        for outdated in json.loads(result.output).values():
            for infos in outdated['packages']:
                assert isinstance(infos['upgrade_cli'], list)
                assert set(map(type, infos['upgrade_cli'])) == {str}

    def test_cli_format_bitbar(self, invoke, subcmd):
        result = invoke(
            '--output-format', 'json', subcmd, '--cli-format', 'bitbar')
        for outdated in json.loads(result.output).values():
            for infos in outdated['packages']:
                assert isinstance(infos['upgrade_cli'], str)
                assert 'param1=' in infos['upgrade_cli']

    @destructive
    @unless_macos
    def test_unicode_name(self, invoke, subcmd, install_formula):
        """ See #16. """
        # Install an old version of a package with a unicode name.
        # Old Cask formula for ubersicht 1.4.60.
        output = install_formula(
            "https://raw.githubusercontent.com/Homebrew/homebrew-cask"
            "/bb72da6c085c017f6bccebbfee5e3bc4837f3165/Casks/ubersicht.rb")
        assert 'Uebersicht-1.4.60.app.zip' in output
        assert 'Übersicht.app' in output

        # Look for reported available upgrade.
        result = invoke('--manager', 'cask', subcmd)
        assert result.exit_code == 0
        assert "ubersicht" in result.output
        assert "Übersicht" in result.output

    @destructive
    @unless_macos
    def test_multiple_names(self, invoke, subcmd, install_formula):
        """ See #26. """
        # Install an old version of a package with multiple names.
        # Old Cask formula for xld 2018.10.19.
        output = install_formula(
            "https://raw.githubusercontent.com/Homebrew/homebrew-cask"
            "/89536da7075aa3ac9683a67189fddbed4a7d818c/Casks/xld.rb")
        assert 'xld-20181019.dmg' in output
        assert 'XLD.app' in output

        # Look for reported available upgrade.
        result = invoke('--manager', 'cask', subcmd)
        assert result.exit_code == 0
        assert "xld" in result.output
        assert "X Lossless Decoder" in result.output