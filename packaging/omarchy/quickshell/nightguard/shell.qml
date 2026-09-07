//! Nightguard desktop panel — a window, never a lever.
//!
//! A SEPARATE quickshell process, not an omarchy-shell plugin. Upstream is
//! explicit that plugins run as unsandboxed code inside the long-lived shell
//! process for the life of the session; a crash here would take the bar and the
//! notifications with it.
//!
//! Being separate means it cannot `import qs.Commons` and reuse Omarchy's Style
//! and Color singletons — that module URI resolves relative to whichever config
//! root is running, so it would resolve to this directory. The tokens are
//! therefore re-derived from the same sources Omarchy reads:
//!
//!   * colours and the structural style tokens come from the live theme's
//!     colors.toml and shell.toml, resolved by `ngtui panel` and shipped in its
//!     payload — so a theme change repaints this too;
//!   * corner radius and the screen-edge gap come from hyprctl, exactly as
//!     shell/Commons/Style.qml does, because both are live compositor values
//!     rather than theme files. On a box with `decoration:rounding = 0` that
//!     means square corners, which is the whole point.
//!
//! The spacing and type scales mirror Style.qml: one base font size is the rem
//! root, every size derives from it, and the spacing scale tracks it. Surfaces
//! follow the Omarchy idiom of a translucent fill over the shared background
//! plus a hairline border, NOT a lighter solid card.
//!
//! It reads and never writes. Only the signer may change state, so there is no
//! control here that spends a token, grants grace or edits anything; everything
//! actionable points at the terminal UI.
//!
//! Run:  quickshell -p packaging/omarchy/quickshell/nightguard

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io

ShellRoot {
    id: root

    // --- payload -------------------------------------------------------------

    property var data: ({
        verdict: "unavailable",
        word: "UNAVAILABLE",
        glyph: "○",
        tokens_left: 0,
        tokens_total: 0,
        week_anchor: "",
        edit_window: { configured: false, open: false, detail: "reading…" },
        blocking: { apps_enabled: false, mode: "blocklist", games: false, apps: 0,
                    sites_enabled: false, sites: 0 },
        warnings: [],
        theme: {
            background: "#2d353b", surface: "#343f44", foreground: "#d3c6aa",
            muted: "#859289", accent: "#7fbbb3", ok: "#a7c080",
            warn: "#dbbc7f", alert: "#e67e80"
        },
        style: {
            popup_background: "#2d353b", popup_text: "#d3c6aa",
            popup_border: "#7fbbb3", popup_background_alpha: 1.0,
            control_border: "#d3c6aa", control_fill_alpha: 0.04,
            control_border_alpha: 0.4, control_border_width: 1,
            font_base: 12, spacing_scale: 1.0, spacing_scale_with_font: true
        }
    })

    readonly property var palette: data.theme
    readonly property var style: data.style

    // --- the scales, mirrored from shell/Commons/Style.qml -------------------

    readonly property real fontScale: Math.max(1 / 12, style.font_base / 12)
    readonly property real spacingScale:
        style.spacing_scale * (style.spacing_scale_with_font ? fontScale : 1)

    function space(px) {
        var n = px * root.spacingScale;
        return n <= 0 ? 0 : Math.max(1, Math.round(n));
    }
    function fontPx(mult) {
        return Math.max(1, Math.round(style.font_base * mult));
    }

    readonly property int fCaption:   fontPx(0.833)   // 10 at base 12
    readonly property int fBodySmall: fontPx(0.917)   // 11
    readonly property int fBody:      fontPx(1.0)     // 12
    readonly property int fTitle:     fontPx(1.167)   // 14

    readonly property int popupPadding: space(14)
    readonly property int panelGap:     space(14)
    readonly property int rowGap:       space(8)
    readonly property int labelGap:     space(4)
    readonly property int pad:          space(8)

    // Live compositor values. Both are re-read on the same cadence as the
    // payload so a rounding or gaps change is picked up without a restart.
    property int cornerRadius: 0
    property int gapsOut: 5
    readonly property int popupBorderWidth: Math.max(1, space(2))

    // --- colours -------------------------------------------------------------

    readonly property color stateColor: {
        switch (data.verdict) {
        case "locked":          return palette.alert;
        case "grace_active":    return palette.warn;
        case "outside_curfew":  return palette.ok;
        case "clock_tamper":    return palette.alert;
        case "offline_blocked": return palette.warn;
        default:                return palette.muted;
        }
    }

    // The Omarchy control idiom: a 4% fill of the foreground over the shared
    // background, with a 40% hairline border. Not a lighter solid card.
    readonly property color controlFill:
        Qt.alpha(style.control_border, style.control_fill_alpha)
    readonly property color controlBorder:
        Qt.alpha(style.control_border, style.control_border_alpha)

    // --- data ----------------------------------------------------------------
    // `ngtui panel` is head-less, key-less and contractually always exits 0, so a
    // failure shows a fail-closed payload rather than a blank rectangle.
    //
    // waitForEnd matters: without it the collector's `text` can still be empty
    // when the signal arrives, and the panel renders its placeholder forever.

    Process {
        id: poll
        command: ["ngtui", "panel"]
        running: true
        stdout: StdioCollector {
            waitForEnd: true
            onStreamFinished: {
                try {
                    var parsed = JSON.parse(this.text);
                    if (parsed && parsed.verdict !== undefined) root.data = parsed;
                } catch (e) {
                    // Keep the last good payload rather than blanking the panel.
                }
            }
        }
    }

    Process {
        id: roundingProc
        command: ["hyprctl", "-j", "getoption", "decoration:rounding"]
        running: true
        stdout: StdioCollector {
            waitForEnd: true
            onStreamFinished: {
                try {
                    var n = Number(JSON.parse(this.text || "{}").int);
                    if (isFinite(n) && n >= 0) root.cornerRadius = n;
                } catch (e) {}
            }
        }
    }

    Process {
        id: gapsProc
        command: ["hyprctl", "-j", "getoption", "general:gaps_out"]
        running: true
        stdout: StdioCollector {
            waitForEnd: true
            onStreamFinished: {
                try {
                    var json = JSON.parse(this.text || "{}");
                    var parts = String(json.css || "").match(/-?\d+(?:\.\d+)?/g) || [];
                    var n = parts.length > 0 ? Number(parts[0]) : Number(json.int);
                    // Hyprland's gap is a window-to-window distance; as a
                    // screen-edge inset it reads as too much, so the shell halves
                    // it. Matched here so the panel sits where its siblings do.
                    if (isFinite(n) && n >= 0) root.gapsOut = Math.max(0, Math.round(n / 2));
                } catch (e) {}
            }
        }
    }

    function refresh() {
        poll.running = true;
        roundingProc.running = true;
        gapsProc.running = true;
    }

    // Theme changes repaint immediately rather than on the next poll.
    //
    // The watched file is `current/theme.name`, NOT anything inside
    // `current/theme`: omarchy replaces that directory wholesale on every theme
    // change, which silently drops a watch on any file within it. theme.name is
    // a sibling of the directory and is rewritten on each switch, so it is the
    // one signal that survives. `omarchy-theme-set` writes it just before it
    // pushes the new palette to its own shell over IPC.
    FileView {
        path: Quickshell.env("HOME") + "/.local/state/omarchy/current/theme.name"
        watchChanges: true
        printErrors: false
        onFileChanged: themeSettle.restart()
        onLoaded: themeSettle.restart()
    }

    // The name lands before the rest of the directory has finished staging, so
    // a beat of settle time avoids reading a half-written palette. Same reason
    // the shell's own Style.qml delays its hyprctl re-poll.
    Timer {
        id: themeSettle
        interval: 200
        repeat: false
        onTriggered: root.refresh()
    }

    Timer {
        interval: 5000
        running: true
        repeat: true
        onTriggered: root.refresh()
    }

    // --- the panel -----------------------------------------------------------

    PanelWindow {
        id: panel

        anchors { top: true; right: true }
        margins { top: root.gapsOut; right: root.gapsOut }

        // Responsive: the card wants a comfortable measure derived from the type
        // scale, but never more than the screen can hold. Height always follows
        // its content, so a warning appearing does not clip.
        readonly property int desiredWidth: root.space(300)
        readonly property int maxWidth:
            screen ? Math.max(root.space(160), screen.width - root.gapsOut * 2) : desiredWidth
        readonly property int maxHeight:
            screen ? Math.max(root.space(120), screen.height - root.gapsOut * 2) : 100000

        implicitWidth: Math.min(desiredWidth, maxWidth)
        implicitHeight: Math.min(
            card.implicitHeight, maxHeight)
        color: "transparent"

        Rectangle {
            id: card
            anchors.fill: parent
            radius: root.cornerRadius
            color: Qt.alpha(root.style.popup_background, root.style.popup_background_alpha)
            border.width: root.popupBorderWidth
            border.color: root.style.popup_border

            implicitHeight: column.implicitHeight
                            + root.popupPadding * 2
                            + root.popupBorderWidth * 2

            ColumnLayout {
                id: column
                anchors.fill: parent
                anchors.margins: root.popupPadding + root.popupBorderWidth
                spacing: root.rowGap

                // --- headline -------------------------------------------------

                RowLayout {
                    Layout.fillWidth: true
                    spacing: root.space(8)

                    Rectangle {
                        implicitWidth: root.space(8)
                        implicitHeight: root.space(8)
                        radius: root.cornerRadius > 0 ? width / 2 : 0
                        color: root.stateColor
                        Layout.alignment: Qt.AlignVCenter
                    }

                    Text {
                        text: root.data.word
                        color: root.style.popup_text
                        font.family: "monospace"   // the fontconfig alias, never a family
                        font.pixelSize: root.fTitle
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    Text {
                        text: "nightguard"
                        color: Qt.alpha(root.palette.muted, 0.9)
                        font.family: "monospace"
                        font.pixelSize: root.fCaption
                    }
                }

                // --- weekly tokens --------------------------------------------

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: root.labelGap

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "weekly tokens"
                            color: Qt.alpha(root.palette.muted, 0.9)
                            font.family: "monospace"
                            font.pixelSize: root.fCaption
                            Layout.fillWidth: true
                        }
                        Text {
                            text: root.data.tokens_left + " / " + root.data.tokens_total
                            color: root.style.popup_text
                            font.family: "monospace"
                            font.pixelSize: root.fCaption
                        }
                    }

                    // One pip per token. A meter rather than a number, because the
                    // point of the quota is that it is visibly finite.
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: root.space(3)
                        Repeater {
                            model: root.data.tokens_total
                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: root.space(3)
                                radius: root.cornerRadius > 0 ? height / 2 : 0
                                color: index < root.data.tokens_left
                                       ? root.palette.accent
                                       : Qt.alpha(root.style.control_border, 0.18)
                            }
                        }
                    }
                }

                // --- the edit window ------------------------------------------

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: editCol.implicitHeight + root.pad * 2
                    radius: root.cornerRadius
                    color: root.controlFill
                    border.width: root.style.control_border_width
                    border.color: root.controlBorder

                    ColumnLayout {
                        id: editCol
                        anchors.fill: parent
                        anchors.margins: root.pad
                        spacing: root.labelGap

                        RowLayout {
                            Layout.fillWidth: true
                            Text {
                                text: "weakening the curfew"
                                color: Qt.alpha(root.palette.muted, 0.9)
                                font.family: "monospace"
                                font.pixelSize: root.fCaption
                                Layout.fillWidth: true
                            }
                            Text {
                                text: root.data.edit_window.open ? "OPEN" : "CLOSED"
                                color: root.data.edit_window.open
                                       ? root.palette.ok : root.palette.alert
                                font.family: "monospace"
                                font.pixelSize: root.fCaption
                                font.weight: Font.DemiBold
                            }
                        }

                        Text {
                            text: root.data.edit_window.detail
                            color: root.style.popup_text
                            font.family: "monospace"
                            font.pixelSize: root.fBodySmall
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                }

                // --- what is blocked ------------------------------------------

                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: root.rowGap
                    rowSpacing: root.rowGap

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
                            implicitHeight: cellCol.implicitHeight + root.pad * 2
                            radius: root.cornerRadius
                            color: root.controlFill
                            border.width: root.style.control_border_width
                            border.color: root.controlBorder

                            ColumnLayout {
                                id: cellCol
                                anchors.fill: parent
                                anchors.margins: root.pad
                                spacing: root.space(2)

                                Text {
                                    text: modelData.label
                                    color: Qt.alpha(root.palette.muted, 0.9)
                                    font.family: "monospace"
                                    font.pixelSize: root.fCaption
                                }
                                Text {
                                    text: modelData.value
                                    color: modelData.on
                                           ? root.style.popup_text
                                           : Qt.alpha(root.style.popup_text, 0.45)
                                    font.family: "monospace"
                                    font.pixelSize: root.fBodySmall
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }

                // --- warnings --------------------------------------------------
                // Only ever present when something is genuinely wrong, so nothing
                // here is the good state.

                Repeater {
                    model: root.data.warnings

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: warnText.implicitHeight + root.pad * 2
                        radius: root.cornerRadius
                        color: Qt.alpha(root.palette.alert, 0.12)
                        border.width: root.style.control_border_width
                        border.color: Qt.alpha(root.palette.alert, 0.5)

                        Text {
                            id: warnText
                            anchors.fill: parent
                            anchors.margins: root.pad
                            text: "⚠ " + modelData
                            color: root.palette.alert
                            font.family: "monospace"
                            font.pixelSize: root.fBodySmall
                            wrapMode: Text.WordWrap
                        }
                    }
                }

                // --- footer ----------------------------------------------------

                Text {
                    text: "read-only · change it in ngtui"
                    color: Qt.alpha(root.palette.muted, 0.7)
                    font.family: "monospace"
                    font.pixelSize: root.fCaption
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignRight
                }
            }
        }
    }
}
