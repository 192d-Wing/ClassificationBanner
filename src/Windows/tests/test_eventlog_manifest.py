# tests/test_eventlog_manifest.py
#
# The ETW event descriptors are defined in two places that MUST agree:
#   - EventManifest/ClassificationBanner.man (compiled into the resource DLL
#     that Event Viewer uses to render events), and
#   - classification_banner/eventlog.py (the Python constants EventWrite sends).
#
# If they drift, EventWrite still returns success but events misroute or render
# wrong — silently, exactly when a crash needs them. These tests parse the
# manifest and assert the Python side matches, turning drift into a CI failure.

import os
import sys
import uuid
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from classification_banner import eventlog


MANIFEST = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "EventManifest", "ClassificationBanner.man",
    )
)

# win: level names -> numeric values (winmeta.xml standard levels).
WIN_LEVELS = {
    "win:Critical": 1,
    "win:Error": 2,
    "win:Warning": 3,
    "win:Informational": 4,
    "win:Verbose": 5,
}


def _by_local_name(element, local_name):
    """All descendants whose tag local-name matches (namespace-agnostic);
    Element.iter() doesn't support the {*} wildcard, so strip namespaces."""
    return [
        e for e in element.iter() if e.tag.rsplit("}", 1)[-1] == local_name
    ]


def _provider():
    """Return the <provider> element (namespace-agnostic)."""
    root = ET.parse(MANIFEST).getroot()
    return _by_local_name(root, "provider")[0]


def test_provider_guid_matches_manifest():
    guid = _provider().get("guid").strip("{}")
    assert uuid.UUID(guid) == eventlog._PROVIDER_GUID


def test_channel_value_matches_manifest():
    channel = _by_local_name(_provider(), "channel")[0]
    assert int(channel.get("value")) == eventlog._CHANNEL_OPERATIONAL


def test_event_descriptors_match_manifest():
    # Map event id -> numeric level as declared in the manifest.
    manifest_map = {
        int(ev.get("value")): WIN_LEVELS[ev.get("level")]
        for ev in _by_local_name(_provider(), "event")
    }
    # Map event id -> numeric level as emitted by eventlog's log_* functions.
    expected = {
        eventlog._EVENT_STARTED: eventlog._LEVEL_INFORMATIONAL,
        eventlog._EVENT_RECOVERED: eventlog._LEVEL_WARNING,
        eventlog._EVENT_CRASHED: eventlog._LEVEL_ERROR,
    }
    assert manifest_map == expected
