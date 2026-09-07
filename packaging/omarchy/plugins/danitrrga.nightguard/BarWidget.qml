import QtQuick
import Quickshell.Io
import qs.Commons
import qs.Ui

// Nightguard in the bar. Replaces the waybar "custom/nightguard" module that
// died with Omarchy 4, and is built from the shell's own kit — BarWidget,
// WidgetButton, PopupCard, PanelSectionHeader, Button — so it opens, closes,
// grabs focus and themes exactly like the Bluetooth and network panels beside
// it. Nothing here is styled by hand: every colour, size and margin comes from
// Style and Color, which is what makes a theme change repaint it for free.
//
// The binary path is absolute on purpose: the shell does not inherit the login
// PATH, and ~/.local/bin is not on its own.
//
// Two data sources, deliberately:
//
//   * `ngtui status --json` feeds the bar label. It is the contract that has
//     always existed, it is cheap, and it always exits 0 — so the label can be
//     polled every 30s without the panel being open.
//   * `ngtui panel` feeds the popup. It carries the full state (the edit
//     window, what is blocked, warnings) and is only fetched while the panel is
//     visible. An older deployed ngtui has no `panel` subcommand, so a failure
//     leaves the panel showing what `status` already gave and says so, rather
//     than blanking.
//
// It reads and never writes. The project's rule is that only the signer may
// change state, so there is no control here that spends a token, grants grace
// or edits anything — the buttons open the terminal UI, which is the one
// sanctioned editor.
BarWidget {
  id: root
  moduleName: "danitrrga.nightguard"

  readonly property string ngtuiPath: "/home/danitrrga/.local/bin/ngtui"

  // Last good reading. Kept when a poll fails so the bar does not blink to
  // empty over a single hiccup.
  property string label: ""
  property string tooltip: ""
  property string statusClass: ""
  property bool panelOpen: false

  // The rich payload. Null until the panel has been opened once.
  property var detail: null
  property bool detailStale: false

  readonly property var tooltipParts: tooltip.split("·")
  readonly property string headline: tooltipParts.length > 0 ? String(tooltipParts[0]).trim() : ""
  readonly property string subtitle: tooltipParts.length > 1 ? tooltipParts.slice(1).join("·").trim() : ""

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.4)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  // Highlight only when nightguard says something other than "outside_curfew".
  // The class name comes from ngtui, not from this widget.
  readonly property bool curfewActive: statusClass !== "" && statusClass.indexOf("outside") === -1

  // The verdict's colour. Read before the word is, so the state is legible at a
  // glance; the roles come from the palette so every theme keeps its own hues.
  readonly property color stateColor: {
    if (!root.detail) return root.curfewActive && root.bar ? root.bar.urgent : root.foreground
    switch (root.detail.verdict) {
    case "locked":          return Color.urgent
    case "clock_tamper":    return Color.urgent
    case "grace_active":    return Color.accent
    case "outside_curfew":  return root.foreground
    case "offline_blocked": return Color.accent
    default:                return root.dim
    }
  }

  function refresh() {
    if (!statusProc.running) statusProc.running = true
    if (root.panelOpen && !detailProc.running) detailProc.running = true
  }

  function openTui() {
    if (root.bar) root.bar.run("omarchy-launch-or-focus-tui ngtui")
  }

  function openMenu() {
    if (root.bar) root.bar.run("ngtui-menu")
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
          // Unreadable output: the previous reading stands.
          return
        }
        if (!parsed || typeof parsed !== "object") return
        root.label = String(parsed.text || "")
        root.tooltip = String(parsed.tooltip || "")
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
          // An ngtui too old to know `panel` prints nothing parseable here.
          // Say so in the panel rather than showing an empty one.
          root.detailStale = true
          return
        }
        if (!parsed || parsed.verdict === undefined) {
          root.detailStale = true
          return
        }
        root.detail = parsed
        root.detailStale = false
      }
    }
  }

  // A query that never returns would freeze the widget: a Process still running
  // cannot be relaunched. Cut off whichever one overruns.
  Timer {
    interval: 10000
    running: statusProc.running
    onTriggered: statusProc.running = false
  }

  Timer {
    interval: 10000
    running: detailProc.running
    onTriggered: detailProc.running = false
  }

  Timer {
    interval: 30000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  // While the panel is open the countdown and the edit window are worth
  // following closely; while it is shut, the 30s bar poll is plenty.
  Timer {
    interval: 5000
    running: root.panelOpen
    repeat: true
    onTriggered: if (!detailProc.running) detailProc.running = true
  }

  onPanelOpenChanged: if (panelOpen && !detailProc.running) detailProc.running = true

  visible: label !== ""
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.label
    fontSize: Style.font.caption
    horizontalMargin: 6
    // No tooltip: the panel is the detail view.
    tooltipText: ""

    onPressed: function(b) {
      if (b === Qt.RightButton) root.openMenu()
      else if (b === Qt.MiddleButton) root.refresh()
      else {
        root.refresh()
        root.panelOpen = !root.panelOpen
      }
    }
  }

  // A labelled meter: name on the left, value on the right, a bar under them and
  // an optional caption below. The recurring row of every Omarchy panel that
  // shows a quantity, so the shape is defined once and reused.
  component Meter: Column {
    id: meter

    property string title: ""
    property string value: ""
    property string caption: ""
    property real fraction: 0
    property color fillColor: Color.accent

    width: parent ? parent.width : implicitWidth
    spacing: Style.space(4)

    Item {
      width: parent.width
      implicitHeight: Math.max(meterTitle.implicitHeight, meterValue.implicitHeight)

      Text {
        id: meterTitle
        textFormat: Text.PlainText
        anchors.left: parent.left
        anchors.right: meterValue.left
        anchors.rightMargin: Style.space(8)
        anchors.verticalCenter: parent.verticalCenter
        text: meter.title
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        elide: Text.ElideRight
      }

      Text {
        id: meterValue
        textFormat: Text.PlainText
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        text: meter.value
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
      }
    }

    Rectangle {
      width: parent.width
      height: Style.space(4)
      radius: Style.cornerRadius > 0 ? height / 2 : 0
      color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.12)

      Rectangle {
        width: Math.max(0, Math.min(1, meter.fraction)) * parent.width
        height: parent.height
        radius: parent.radius
        color: meter.fillColor

        Behavior on width {
          NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
        }
      }
    }

    Text {
      textFormat: Text.PlainText
      visible: meter.caption !== ""
      width: parent.width
      text: meter.caption
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      elide: Text.ElideRight
    }
  }

  // A plain label/value row for facts that are not quantities.
  component InfoRow: Item {
    property string title: ""
    property string value: ""
    property bool muted: false

    width: parent ? parent.width : implicitWidth
    implicitHeight: Math.max(rowTitle.implicitHeight, rowValue.implicitHeight)

    Text {
      id: rowTitle
      textFormat: Text.PlainText
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      text: parent.title
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall
    }

    Text {
      id: rowValue
      textFormat: Text.PlainText
      anchors.right: parent.right
      anchors.left: rowTitle.right
      anchors.leftMargin: Style.space(8)
      anchors.verticalCenter: parent.verticalCenter
      horizontalAlignment: Text.AlignRight
      text: parent.value
      color: parent.muted ? root.dim : root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall
      elide: Text.ElideRight
    }
  }

  PopupCard {
    id: popup
    anchorItem: button
    bar: root.bar
    owner: root
    open: root.panelOpen
    contentWidth: popup.fittedContentWidth(Style.space(300))
    contentHeight: popup.fittedContentHeight(column.implicitHeight)

    onOpenChanged: if (!open) root.panelOpen = false

    Column {
      id: column
      anchors.fill: parent
      spacing: Style.space(12)

      // --- hero ---------------------------------------------------------

      PanelHero {
        title: "Nightguard"
        meta: root.detail ? root.detail.word : (root.headline !== "" ? root.headline : root.label)
        detail: root.detail && root.detail.style && root.detail.style.name
                ? root.detail.style.name : ""
        foreground: root.foreground
        fontFamily: root.fontFamily

        iconComponent: Rectangle {
          implicitWidth: Style.space(10)
          implicitHeight: Style.space(10)
          radius: Style.cornerRadius > 0 ? width / 2 : 0
          color: root.stateColor
        }
      }

      PanelSeparator { foreground: root.foreground }

      // --- weekly tokens -------------------------------------------------

      PanelSectionHeader {
        text: "FICHAS"
        foreground: root.foreground
        fontFamily: root.fontFamily
      }

      Meter {
        visible: root.detail !== null && root.detail.tokens_total > 0
        title: "Semanales"
        value: root.detail ? (root.detail.tokens_left + " / " + root.detail.tokens_total) : ""
        fraction: root.detail && root.detail.tokens_total > 0
                  ? root.detail.tokens_left / root.detail.tokens_total : 0
        fillColor: root.detail && root.detail.tokens_left === 0 ? Color.urgent : Color.accent
        caption: root.detail && root.detail.week_anchor
                 ? "Semana desde " + root.detail.week_anchor : ""
      }

      // --- the edit window ------------------------------------------------

      PanelSectionHeader {
        visible: root.detail !== null
        text: "VENTANA DE EDICIÓN"
        foreground: root.foreground
        fontFamily: root.fontFamily
      }

      InfoRow {
        visible: root.detail !== null
        title: "Debilitar el toque de queda"
        value: root.detail
               ? (root.detail.edit_window.open ? "ABIERTA" : "CERRADA") : ""
      }

      Text {
        textFormat: Text.PlainText
        visible: root.detail !== null
        width: column.width
        text: root.detail ? root.detail.edit_window.detail : ""
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }

      // --- what is blocked -------------------------------------------------

      PanelSectionHeader {
        visible: root.detail !== null
        text: "BLOQUEO"
        foreground: root.foreground
        fontFamily: root.fontFamily
      }

      InfoRow {
        visible: root.detail !== null
        title: "Aplicaciones"
        value: root.detail
               ? (root.detail.blocking.apps + " · " + root.detail.blocking.mode) : ""
        muted: root.detail ? !root.detail.blocking.apps_enabled : true
      }

      InfoRow {
        visible: root.detail !== null
        title: "Sitios"
        value: root.detail ? (root.detail.blocking.sites + " bloqueados") : ""
        muted: root.detail ? !root.detail.blocking.sites_enabled : true
      }

      InfoRow {
        visible: root.detail !== null
        title: "Juegos"
        value: root.detail
               ? (root.detail.blocking.games ? "detectados solos" : "sin bloquear") : ""
        muted: root.detail ? !root.detail.blocking.games : true
      }

      // --- warnings ---------------------------------------------------------
      // Only ever present when something is genuinely wrong, so nothing here is
      // the good state.

      Repeater {
        model: root.detail ? root.detail.warnings : []

        Text {
          textFormat: Text.PlainText
          width: column.width
          text: "⚠ " + modelData
          color: Color.urgent
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }
      }

      // Shown only when the deployed ngtui is older than this widget. Better a
      // named limitation than a panel that is quietly missing three sections.
      Text {
        textFormat: Text.PlainText
        visible: root.detailStale && root.detail === null
        width: column.width
        text: "Detalle no disponible: el ngtui instalado no conoce «panel». "
              + "Ejecuta el despliegue para actualizarlo."
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }

      PanelSeparator { foreground: root.foreground }

      // --- actions ----------------------------------------------------------
      // Every one of these opens something. None of them changes state: the
      // signer is the only thing that may, and it is reached through the TUI.

      Row {
        spacing: Style.space(8)

        Button {
          text: "Abrir"
          tooltipText: "Abrir la interfaz completa de nightguard"
          bordered: true
          foreground: root.foreground
          fontFamily: root.fontFamily
          fontSize: Style.font.caption
          onClicked: {
            root.panelOpen = false
            root.openTui()
          }
        }

        Button {
          text: "Menu"
          tooltipText: "Menu de nightguard"
          bordered: true
          foreground: root.foreground
          fontFamily: root.fontFamily
          fontSize: Style.font.caption
          onClicked: {
            root.panelOpen = false
            root.openMenu()
          }
        }

        Button {
          text: "Actualizar"
          tooltipText: "Volver a leer el estado"
          bordered: true
          foreground: root.foreground
          fontFamily: root.fontFamily
          fontSize: Style.font.caption
          onClicked: root.refresh()
        }
      }
    }
  }
}
