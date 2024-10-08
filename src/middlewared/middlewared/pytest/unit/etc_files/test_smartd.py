import subprocess
import textwrap
from unittest.mock import call, Mock, patch

import pytest

from middlewared.etc_files.smartd import (
    ensure_smart_enabled, get_smartd_schedule, get_smartd_config
)


@pytest.mark.asyncio
async def test__ensure_smart_enabled__smart_error():
    with patch("middlewared.etc_files.smartd.smartctl") as run:
        run.return_value = Mock(stdout='{"smart_support": {"enabled": false, "available": false}}')

        assert await ensure_smart_enabled(["/dev/ada0"]) is False

        run.assert_called_once()


@pytest.mark.asyncio
async def test__ensure_smart_enabled__smart_enabled():
    with patch("middlewared.etc_files.smartd.smartctl") as run:
        run.return_value = Mock(stdout='{"smart_support": {"enabled": true, "available": true}}')

        assert await ensure_smart_enabled(["/dev/ada0"])

        run.assert_called_once()


@pytest.mark.asyncio
async def test__ensure_smart_enabled__smart_was_disabled():
    with patch("middlewared.etc_files.smartd.smartctl") as run:
        run.return_value = Mock(stdout='{"smart_support": {"enabled": false, "available": true}}', returncode=0)

        assert await ensure_smart_enabled(["/dev/ada0"])

        assert run.call_args_list == [
            call(["/dev/ada0", "-i", "--json=c"], check=False, stderr=subprocess.STDOUT,
                 encoding="utf8", errors="ignore"),
            call(["/dev/ada0", "-s", "on"], check=False, stderr=subprocess.STDOUT),
        ]


@pytest.mark.asyncio
async def test__ensure_smart_enabled__enabling_smart_failed():
    with patch("middlewared.etc_files.smartd.smartctl") as run:
        run.return_value = Mock(stdout='{"smart_support": {"enabled": false, "available": false}}', returncode=1)

        assert await ensure_smart_enabled(["/dev/ada0"]) is False


@pytest.mark.asyncio
async def test__ensure_smart_enabled__handled_args_properly():
    with patch("middlewared.etc_files.smartd.smartctl") as run:
        run.return_value = Mock(stdout='{"smart_support": {"enabled": true, "available": true}}')

        assert await ensure_smart_enabled(["/dev/ada0", "-d", "sat"])

        run.assert_called_once_with(
            ["/dev/ada0", "-d", "sat", "-i", "--json=c"], check=False, stderr=subprocess.STDOUT,
            encoding="utf8", errors="ignore",
        )


def test__get_smartd_schedule__need_mapping():
    assert get_smartd_schedule({
        "smarttest_schedule": {
            "month": "jan,feb,mar,apr,may,jun,jul,aug,sep,oct,nov,dec",
            "dom": "1,hedgehog day,3",
            "dow": "tue,SUN",
            "hour": "*/1",
        }
    }) == "../(01|03)/(2|7)/.."


def test__get_smartd_schedule__0_is_sunday():
    assert get_smartd_schedule({
        "smarttest_schedule": {
            "month": "*",
            "dom": "*",
            "dow": "0",
            "hour": "0",
        }
    }) == "../../(7)/(00)"


def test__get_smartd_config():
    assert get_smartd_config({
        "smartctl_args": ["/dev/ada0", "-d", "sat"],
        "smart_powermode": "never",
        "smart_difference": 0,
        "smart_informational": 1,
        "smart_critical": 2,
        "smarttest_type": "S",
        "smarttest_schedule": {
            "month": "*/1",
            "dom": "*/1",
            "dow": "*/1",
            "hour": "*/1",
        },
        "disk_critical": None,
        "disk_difference": None,
        "disk_informational": None,
    }) == textwrap.dedent("""\
        /dev/ada0 -d sat -n never -W 0,1,2 -m root -M exec /usr/local/libexec/smart_alert.py\\
        -s S/../.././..\\
        """)


def test__get_smartd_config_without_schedule():
    assert get_smartd_config({
        "smartctl_args": ["/dev/ada0", "-d", "sat"],
        "smart_powermode": "never",
        "smart_difference": 0,
        "smart_informational": 1,
        "smart_critical": 2,
        "disk_critical": None,
        "disk_difference": None,
        "disk_informational": None,
    }) == textwrap.dedent("""\
        /dev/ada0 -d sat -n never -W 0,1,2 -m root -M exec /usr/local/libexec/smart_alert.py""")


def test__get_smartd_config_with_temp():
    assert get_smartd_config({
        "smartctl_args": ["/dev/ada0", "-d", "sat"],
        "smart_powermode": "never",
        "smart_difference": 0,
        "smart_informational": 1,
        "smart_critical": 2,
        "disk_critical": 50,
        "disk_difference": 10,
        "disk_informational": 40,
    }) == textwrap.dedent("""\
        /dev/ada0 -d sat -n never -W 10,40,50 -m root -M exec /usr/local/libexec/smart_alert.py""")
