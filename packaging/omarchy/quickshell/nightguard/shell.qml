//! Nightguard desktop panel — a window, never a lever.
//!
//! Omarchy 4 replaced Waybar with quickshell, so the bar module this project used
//! to ship has no host any more. This is the replacement, and it is deliberately a
//! SEPARATE quickshell process rather than a plugin inside omarchy-shell: plugins
//! run as unsandboxed code inside the long-lived shell process, and curfew state is
//! not something to put there.
//!
//! It reads. It never writes. The project's standing rule is that only the signer
//! may change state and that any privileged exec or state-changing click handler
//! from a bar widget is rejected by design, so there is no button here that spends
//! a token, grants grace, or edits anything. Everything actionable points at the
//! terminal UI, which is the one sanctioned editor.
//!
//! Layout follows the Omarchy 4 grammar rather than the old one: a ~380px card
//! anchored to the top-right, not the 875x600 screen-centred window v3 used for
//! its system panels. Colours come from the live desktop theme at runtime -- the
//! payload carries them, resolved from the same colors.toml the desktop reads, so
//! a theme change repaints this too.
//!
//! Run:  quickshell -p packaging/omarchy/quickshell/nightguard

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io

ShellRoot {
    id: root

    // --- state ---------------------------------------------------------------

    property var data: ({
        verdict: "unavailable",
        word: "…",
        glyph: "○",
        tokens_left: 0,
        tokens_total: 0,
        edit_window: { configured: false, open: false, detail: "reading…" },
        blocking: { apps_enabled: false, mode: "blocklist", games: false, apps: 0,
                    sites_enabled: false, sites: 0 },
        warnings: [],
        theme: {
            background: "#2d353b", surface: "#343f44", foreground: "#d3c6aa",
            muted: "#859289", accent: "#7fbbb3", ok: "#a7c080",
            warn: "#dbbc7f", alert: "#e67e80"
        }
    })

    readonly property var palette: data.theme

    // The verdict decides the accent the whole card is keyed to, so the state is
    // legible from across the room without reading a word of it.
    readonly property color stateColor: {
        switch (data.verdict) {
        case "locked":         return palette.alert;
        case "grace_active":   return palette.warn;
        case "outside_curfew": return palette.ok;
        case "clock_tamper":   return palette.alert;
        case "offline_blocked":return palette.warn;
        default:               return palette.muted;
        }
    }

    // --- data source ---------------------------------------------------------
    // `ngtui panel` is head-less, key-less and contractually always exits 0, so a
    // failure here shows a fail-closed payload rather than an empty panel.

    Process {
        id: poll
        command: ["ngtui", "panel"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    root.data = JSON.parse(this.text);
                } catch (e) {
                    // Keep the last good payload rather than blanking the panel.
                }
            }
        }
    }

    Timer {
        interval: 5000
        running: true
        repeat: true
        triggeredOnStart: false
        onTriggered: poll.running = true
    }

    // --- the panel -----------------------------------------------------------

    PanelWindow {
        id: panel

        anchors { top: true; right: true }
        margins { top: 8; right: 8 }

        implicitWidth: 380
        implicitHeight: column.implicitHeight + 28
        color: "transparent"

        Rectangle {
            anchors.fill: parent
            radius: 12
            color: root.palette.background
            border.width: 1
            border.color: Qt.alpha(root.palette.muted, 0.35)

            ColumnLayout {
                id: column
                anchors.fill: parent
                anchors.margins: 14
                spacing: 12

                // --- headline: the verdict ---------------------------------

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Rectangle {
                        implicitWidth: 10
                        implicitHeight: 10
                        radius: 5
                        color: root.stateColor
                        Layout.alignment: Qt.AlignVCenter
                    }

                    Text {
                        text: root.data.word
                        color: root.palette.foreground
                        font.family: "monospace"   // never a hard family: the user overrides it
                        font.pixelSize: 15
                        font.weight: Font.DemiBold
                        Layout.fillWidth: true
                    }

                    Text {
                        text: "nightguard"
                        color: root.palette.muted
                        font.family: "monospace"
                        font.pixelSize: 11
                    }
                }

                // --- weekly tokens -----------------------------------------

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "weekly tokens"
                            color: root.palette.muted
                            font.family: "monospace"
                            font.pixelSize: 11
                            Layout.fillWidth: true
                        }
                        Text {
                            text: root.data.tokens_left + " / " + root.data.tokens_total
                            color: root.palette.foreground
                            font.family: "monospace"
                            font.pixelSize: 11
                        }
                    }

                    // One pip per token. A meter rather than a number, because the
                    // point of the quota is that it is visibly finite.
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 4
                        Repeater {
                            model: root.data.tokens_total
                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: 4
                                radius: 2
                                color: index < root.data.tokens_left
                                       ? root.palette.accent
                                       : Qt.alpha(root.palette.muted, 0.3)
                            }
                        }
                    }
                }

                // --- the edit window ---------------------------------------

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: editRow.implicitHeight + 16
                    radius: 8
                    color: root.palette.surface

                    ColumnLayout {
                        id: editRow
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 3

                        RowLayout {
                            Layout.fillWidth: true
                            Text {
                                text: "weakening the curfew"
                                color: root.palette.muted
                                font.family: "monospace"
                                font.pixelSize: 11
                                Layout.fillWidth: true
                            }
                            Text {
                                text: root.data.edit_window.open ? "OPEN" : "CLOSED"
                                color: root.data.edit_window.open
                                       ? root.palette.ok : root.palette.alert
                                font.family: "monospace"
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                            }
                        }

                        Text {
                            text: root.data.edit_window.detail
                            color: root.palette.foreground
                            font.family: "monospace"
                            font.pixelSize: 11
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                }

                // --- what is blocked ---------------------------------------

                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: 8
                    rowSpacing: 6

                    Repeater {
                        model: [
                            { label: "apps",  on: root.data.blocking.apps_enabled,
                              value: root.data.blocking.apps + " " + root.data.blocking.mode },
                            { label: "sites", on: root.data.blocking.sites_enabled,
                              value: root.data.blocking.sites + " blocked" },
                            { label: "games", on: root.data.blocking.games,
                              value: root.data.blocking.games ? "auto-detected" : "not blocked" },
                            { label: "week",  on: true,
                              value: root.data.week_anchor || "—" }
                        ]

                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 44
                            radius: 8
                            color: root.palette.surface

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 2

                                Text {
                                    text: modelData.label
                                    color: root.palette.muted
                                    font.family: "monospace"
                                    font.pixelSize: 10
                                }
                                Text {
                                    text: modelData.value
                                    color: modelData.on
                                           ? root.palette.foreground
                                           : Qt.alpha(root.palette.foreground, 0.45)
                                    font.family: "monospace"
                                    font.pixelSize: 11
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }

                // --- warnings ----------------------------------------------
                // Only ever present when something is genuinely wrong, so an
                // empty panel here is the good state.

                Repeater {
                    model: root.data.warnings

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: warnText.implicitHeight + 14
                        radius: 8
                        color: Qt.alpha(root.palette.alert, 0.15)
                        border.width: 1
                        border.color: Qt.alpha(root.palette.alert, 0.5)

                        Text {
                            id: warnText
                            anchors.fill: parent
                            anchors.margins: 7
                            text: "⚠ " + modelData
                            color: root.palette.alert
                            font.family: "monospace"
                            font.pixelSize: 11
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                // --- footer -------------------------------------------------

                Text {
                    text: "read-only · change it in ngtui"
                    color: Qt.alpha(root.palette.muted, 0.8)
                    font.family: "monospace"
                    font.pixelSize: 10
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignRight
                }
            }
        }
    }
}
