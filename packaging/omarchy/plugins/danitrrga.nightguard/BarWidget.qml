import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Nightguard in the bar: one icon, one panel.
//
// Shaped after a first-party widget that owns a popup (read via
// `omarchy plugin clone omarchy.clock`), because the previous attempt invented
// its own shape and did not work at all. What a third-party bar widget has to
// be, and what the earlier version got wrong:
//
//   * The entry point extends BarWidget — that is what the bar host
//     instantiates into a slot. An earlier version extended Ui/Panel and the
//     shell refused it with "File name case mismatch", which is what a failed
//     root-type creation looks like from the loader.
//   * The popup lives in a SEPARATE file, pulled in with a Loader and
//     Qt.resolvedUrl; the host injects bar, settings and anchorItem into it.
//   * The widget must expose `opened`, `open()`, `close()` and
//     `closeForPopoutSwitch()`. Bar.findPanelWidget routes summon/hide/toggle
//     through exactly those names, and the popout coordinator uses them to hand
//     focus between bar panels. A private bool of one's own means nothing to
//     any of that — which is why clicking used to do nothing.
//
// It reads and never writes. Only the signer may change state, so nothing here
// spends a token, grants grace or edits anything.
BarWidget {
  id: root
  moduleName: "danitrrga.nightguard"

  // Absolute on purpose: the shell does not inherit the login PATH, and
  // ~/.local/bin is not on its own.
  readonly property string ngtuiPath: "/home/danitrrga/.local/bin/ngtui"

  // Last good readings, kept when a poll fails so the bar does not blink to
  // empty over one hiccup.
  property string statusClass: ""
  property string barLabel: ""
  property var detail: null
  property bool detailFailed: false

  readonly property string verdict: detail ? String(detail.verdict) : statusClass
  readonly property int tokensLeft: detail ? Number(detail.tokens_left) : -1
  readonly property int tokensTotal: detail ? Number(detail.tokens_total) : 0
  readonly property bool curfewActive: verdict !== "" && verdict.indexOf("outside") === -1

  // The icon carries the state; the pips under it carry what is left. A bar
  // entry is an icon on the shell's optical grid, not a line of text — the old
  // "○ 3" was neither. Nerd Font glyphs, resolved through the `monospace` alias
  // the shell binds to; Omarchy's private brand font is not borrowed.
  readonly property string glyph: {
    switch (root.verdict) {
    case "locked":          return "󰌾"   // closed padlock
    case "grace_active":    return "󰔟"   // running timer
    case "clock_tamper":    return "󰀪"   // alert
    case "offline_blocked": return "󰅛"   // cloud off
    case "outside_curfew":  return "󰌿"   // open padlock
    default:                return "󰦝"   // shield: state not known yet
    }
  }

  // --- the panel contract ---------------------------------------------------

  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
  readonly property bool popoutSwitchClosing: panelLoader.item
    ? panelLoader.item.popoutSwitchClosing === true : false

  function open() { if (panelLoader.item) panelLoader.item.open() }
  function close() { if (panelLoader.item) panelLoader.item.close() }
  function togglePanel() { if (panelLoader.item) panelLoader.item.toggle() }
  function closeForPopoutSwitch() {
    if (panelLoader.item) panelLoader.item.closeForPopoutSwitch()
  }

  function injectPanel() {
    var target = panelLoader.item
    if (!target) return
    if ("bar" in target) target.bar = root.bar
    if ("settings" in target) target.settings = root.settings
    if ("anchorItem" in target) target.anchorItem = button
    if ("hostWidget" in target) target.hostWidget = root
  }

  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()

  // --- data -----------------------------------------------------------------
  // Two sources on purpose. `status` is cheap, has always existed and always
  // exits 0, so the icon can poll it every 30s with the panel shut. `panel`
  // carries the whole state and is only fetched while the panel is open.

  function refresh() {
    if (!statusProc.running) statusProc.running = true
    // Fetched on every tick, not only while open. A popup positions itself as
    // it maps, so a panel whose data arrives afterwards maps at its collapsed
    // height and then grows out of place — which is what "opens with stale
    // content in the wrong spot" looked like.
    if (!detailProc.running) detailProc.running = true
  }

  function openTui() {
    if (root.bar) root.bar.run("omarchy-launch-or-focus-tui ngtui")
    root.close()
  }

  Process {
    id: statusProc
    command: [root.ngtuiPath, "status", "--json"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        let parsed
        try {
          parsed = JSON.parse(text || "")
        } catch (e) {
          return  // unreadable: the previous reading stands
        }
        if (!parsed || typeof parsed !== "object") return
        root.barLabel = String(parsed.text || "")
        root.statusClass = String(parsed.class || "")
      }
    }
  }

  Process {
    id: detailProc
    command: [root.ngtuiPath, "panel"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        let parsed
        try {
          parsed = JSON.parse(text || "")
        } catch (e) {
          root.detailFailed = true
          return
        }
        if (!parsed || parsed.verdict === undefined) {
          root.detailFailed = true
          return
        }
        root.detail = parsed
        root.detailFailed = false
      }
    }
  }

  // A query that never returns would freeze the widget: a Process still running
  // cannot be relaunched. Cut off whichever one overruns.
  Timer { interval: 10000; running: statusProc.running; onTriggered: statusProc.running = false }
  Timer { interval: 10000; running: detailProc.running; onTriggered: detailProc.running = false }

  Timer {
    interval: 30000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  // While the panel is open the hour matters, so follow it closely; while shut,
  // the 30s icon poll is plenty.
  Timer {
    interval: 5000
    running: root.opened
    repeat: true
    onTriggered: if (!detailProc.running) detailProc.running = true
  }

  onOpenedChanged: if (opened && !detailProc.running) detailProc.running = true

  // --- the widget slot ------------------------------------------------------

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("NightguardPanel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  // Lets the panel be opened without a mouse, which is also the only way to
  // exercise it from a test script.
  IpcHandler {
    target: "danitrrga.nightguard"

    function refresh(): void { root.broadcast("refresh") }
    function open(): void { root.open() }
    function close(): void { root.close() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
    function toggle(): void { root.togglePanel() }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.glyph
    active: root.curfewActive || root.tokensLeft === 0
    tooltipText: root.detail
      ? root.detail.word + " · " + root.tokensLeft + "/" + root.tokensTotal + " fichas"
      : "Nightguard"

    onPressed: function(b) {
      if (b === Qt.MiddleButton) root.refresh()
      else if (b === Qt.RightButton) root.openTui()
      else {
        root.refresh()
        root.togglePanel()
      }
    }

    // Remaining tokens as pips beneath the glyph. The quota's whole point is
    // that it is visibly finite, and a count you have to hover for is not.
    Row {
      anchors.horizontalCenter: parent.horizontalCenter
      anchors.bottom: parent.bottom
      anchors.bottomMargin: Math.max(1, Style.space(2))
      spacing: 1
      visible: root.tokensTotal > 0 && !root.vertical

      Repeater {
        model: root.tokensTotal
        Rectangle {
          required property int index
          width: 3
          height: 2
          color: index < root.tokensLeft
                 ? button.foreground
                 : Qt.rgba(button.foreground.r, button.foreground.g, button.foreground.b, 0.25)
        }
      }
    }
  }
}
