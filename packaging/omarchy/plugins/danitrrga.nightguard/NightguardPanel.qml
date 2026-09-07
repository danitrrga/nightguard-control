import QtQuick
import QtQuick.Controls
import Quickshell
import qs.Commons
import qs.Ui

// The Nightguard panel: what the bar icon opens.
//
// A separate file from the widget on purpose — that is the shape a third-party
// plugin with a popup has. The widget loads this with Qt.resolvedUrl and injects
// `bar`, `settings`, `anchorItem` and `hostWidget`; extending Ui/Panel brings
// the open/close lifecycle, the popout coordinator and the focus handling with
// it, so this behaves like the network and bluetooth panels beside it.
//
// Data comes from the host widget rather than being polled again here: two
// readers of the same command disagree for up to a tick, and a panel that
// disagrees with its own bar icon is worse than either being slightly stale.
//
// It reads and never writes. Nothing here spends a token, grants grace or edits
// anything; both actions open the terminal UI, which is the one sanctioned
// editor.
Panel {
  id: root
  moduleName: "danitrrga.nightguard"
  ipcTarget: ""
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null

  readonly property var detail: hostWidget ? hostWidget.detail : null
  readonly property bool detailFailed: hostWidget ? hostWidget.detailFailed === true : false
  readonly property string glyph: hostWidget ? hostWidget.glyph : "󰦝"
  readonly property string verdict: hostWidget ? hostWidget.verdict : ""
  readonly property int tokensLeft: hostWidget ? hostWidget.tokensLeft : -1
  readonly property int tokensTotal: hostWidget ? hostWidget.tokensTotal : 0

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color urgent: bar ? bar.urgent : Color.urgent
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property color track: Style.selectedFillFor(foreground, Color.accent)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  readonly property string stateWord: detail ? String(detail.word) : "…"
  readonly property bool windowOpen: !!detail && detail.edit_window
                                     && detail.edit_window.open === true

  readonly property color stateColor: {
    switch (root.verdict) {
    case "locked":          return root.urgent
    case "clock_tamper":    return root.urgent
    case "grace_active":    return Color.accent
    case "offline_blocked": return Color.accent
    case "outside_curfew":  return root.foreground
    default:                return root.dim
    }
  }

  function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }
  function refresh() { if (hostWidget) hostWidget.refresh() }
  function openTui() { if (hostWidget) hostWidget.openTui() }

  // A missing or non-numeric minute reads as "absent" rather than as undefined,
  // which QML complains about once per binding per repaint. An older ngtui has
  // no minute fields at all, and that must not fill the log.
  function minuteOr(value) {
    var n = Number(value)
    return isFinite(n) ? n : -1
  }

  // --- pieces ---------------------------------------------------------------

  // The one picture that answers "when am I locked, and when may I change it"
  // without reading a word: a whole day left to right, the curfew shaded, the
  // hours the pact may be weakened marked beneath it, and a line at now.
  component DayStrip: Item {
    id: strip

    property int curfewStart: -1
    property int curfewEnd: -1
    property int windowStart: -1
    property int windowEnd: -1
    property int nowMinutes: -1

    readonly property real minuteWidth: width / 1440

    implicitHeight: Style.space(44)

    // A window that wraps midnight is two bands, not one — drawing 21:30→05:30
    // as a single rectangle would shade the daytime instead of the night.
    function spans(from, to) {
      if (from < 0 || to < 0 || from === to) return []
      if (from < to) return [[from, to]]
      return [[from, 1440], [0, to]]
    }

    Item {
      id: curfewRow
      width: parent.width
      height: Style.space(14)

      Rectangle {
        anchors.fill: parent
        radius: Style.cornerRadius > 0 ? height / 2 : 0
        color: root.track
      }

      Repeater {
        model: strip.spans(strip.curfewStart, strip.curfewEnd)
        Rectangle {
          required property var modelData
          x: modelData[0] * strip.minuteWidth
          width: Math.max(1, (modelData[1] - modelData[0]) * strip.minuteWidth)
          height: parent.height
          radius: Style.cornerRadius > 0 ? height / 2 : 0
          color: root.alpha(root.urgent, 0.8)
        }
      }

      Rectangle {
        visible: strip.nowMinutes >= 0
        x: strip.nowMinutes * strip.minuteWidth - width / 2
        y: -Style.space(4)
        width: Math.max(2, Style.space(2))
        height: parent.height + Style.space(8)
        color: root.foreground
      }
    }

    Item {
      id: windowRow
      anchors.top: curfewRow.bottom
      anchors.topMargin: Style.space(4)
      width: parent.width
      height: Style.space(4)

      Repeater {
        model: strip.spans(strip.windowStart, strip.windowEnd)
        Rectangle {
          required property var modelData
          x: modelData[0] * strip.minuteWidth
          width: Math.max(1, (modelData[1] - modelData[0]) * strip.minuteWidth)
          height: parent.height
          radius: Style.cornerRadius > 0 ? height / 2 : 0
          color: Color.accent
        }
      }
    }

    Item {
      anchors.top: windowRow.bottom
      anchors.topMargin: Style.space(2)
      width: parent.width
      height: Style.space(12)

      Repeater {
        model: [0, 6, 12, 18]
        Text {
          required property int modelData
          textFormat: Text.PlainText
          x: modelData === 0
             ? 0
             : Math.min(parent.width - implicitWidth,
                        modelData * 60 * strip.minuteWidth - implicitWidth / 2)
          text: modelData < 10 ? "0" + modelData : String(modelData)
          color: root.dim
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
        }
      }
    }
  }

  // Label left, value right — the shell's own row shape.
  component InfoRow: Item {
    id: infoRow
    property string title: ""
    property string value: ""
    property bool muted: false

    implicitHeight: Math.max(rowTitle.implicitHeight, rowValue.implicitHeight)

    Text {
      id: rowTitle
      textFormat: Text.PlainText
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      text: infoRow.title
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall
    }

    Text {
      id: rowValue
      textFormat: Text.PlainText
      anchors.right: parent.right
      anchors.left: rowTitle.right
      anchors.leftMargin: Style.spacing.sm
      anchors.verticalCenter: parent.verticalCenter
      horizontalAlignment: Text.AlignRight
      text: infoRow.value
      color: infoRow.muted ? root.dim : root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall
      elide: Text.ElideRight
    }
  }

  // --- the popup ------------------------------------------------------------

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(340))
    contentHeight: panel.fittedContentHeight(column.implicitHeight, Style.space(620))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent

      onCloseRequested: root.close()
      onActivateRequested: root.refresh()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(t) { if (t === "r" || t === "R") root.refresh() }

      Flickable {
        id: panelFlick
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        interactive: contentHeight > height
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
          id: column
          // NOT anchors.fill. The popup's height comes from this column's
          // implicitHeight, so anchoring would make width depend on height and
          // height on width — the binding loop that froze the earlier version.
          width: panelFlick.width
          spacing: Style.space(12)

          PanelHero {
            width: parent.width
            title: "Nightguard"
            meta: root.stateWord
            foreground: root.foreground
            fontFamily: root.fontFamily

            iconComponent: Component {
              Text {
                textFormat: Text.PlainText
                text: root.glyph
                color: root.stateColor
                font.family: root.fontFamily
                font.pixelSize: Style.font.display
              }
            }
          }

          PanelSeparator { width: parent.width; foreground: root.foreground }

          // ---------- the day at a glance ----------
          PanelSectionHeader {
            width: parent.width
            text: "EL DÍA"
            foreground: root.foreground
            fontFamily: root.fontFamily
          }

          DayStrip {
            width: parent.width
            curfewStart: root.minuteOr(root.detail && root.detail.curfew
                                       ? root.detail.curfew.start_minutes : -1)
            curfewEnd: root.minuteOr(root.detail && root.detail.curfew
                                     ? root.detail.curfew.end_minutes : -1)
            windowStart: root.minuteOr(root.detail && root.detail.edit_window
                                       ? root.detail.edit_window.start_minutes : -1)
            windowEnd: root.minuteOr(root.detail && root.detail.edit_window
                                     ? root.detail.edit_window.end_minutes : -1)
            nowMinutes: root.minuteOr(root.detail ? root.detail.now_minutes : -1)
          }

          Row {
            width: parent.width
            spacing: Style.space(12)

            Row {
              spacing: Style.space(5)
              Rectangle {
                width: Style.space(8); height: Style.space(8)
                anchors.verticalCenter: parent.verticalCenter
                radius: Style.cornerRadius > 0 ? width / 2 : 0
                color: root.alpha(root.urgent, 0.8)
              }
              Text {
                textFormat: Text.PlainText
                anchors.verticalCenter: parent.verticalCenter
                text: root.detail && root.detail.curfew && root.detail.curfew.start
                      ? "cerrado " + root.detail.curfew.start + "–" + root.detail.curfew.end
                      : "cerrado"
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
              }
            }

            Row {
              spacing: Style.space(5)
              Rectangle {
                width: Style.space(8); height: Style.space(8)
                anchors.verticalCenter: parent.verticalCenter
                radius: Style.cornerRadius > 0 ? width / 2 : 0
                color: Color.accent
              }
              Text {
                textFormat: Text.PlainText
                anchors.verticalCenter: parent.verticalCenter
                text: root.detail && root.detail.edit_window && root.detail.edit_window.start
                      ? "editable " + root.detail.edit_window.start + "–" + root.detail.edit_window.end
                      : "editable"
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
              }
            }
          }

          // ---------- may the pact be weakened right now ----------
          Rectangle {
            width: parent.width
            implicitHeight: gateCol.implicitHeight + Style.space(16)
            radius: Style.cornerRadius
            color: root.windowOpen
                   ? Style.normalFillFor(root.foreground, Color.accent)
                   : root.alpha(root.urgent, 0.10)
            border.width: Style.normalBorderWidth
            border.color: root.windowOpen
                          ? Style.normalBorderFor(root.foreground, Color.accent)
                          : root.alpha(root.urgent, 0.45)

            Column {
              id: gateCol
              x: Style.space(8)
              y: Style.space(8)
              width: parent.width - Style.space(16)
              spacing: Style.space(3)

              Row {
                width: parent.width
                spacing: Style.space(6)

                Text {
                  textFormat: Text.PlainText
                  text: root.windowOpen ? "󰌿" : "󰌾"
                  color: root.windowOpen ? Color.accent : root.urgent
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.subtitle
                }
                Text {
                  textFormat: Text.PlainText
                  anchors.verticalCenter: parent.verticalCenter
                  text: root.windowOpen
                        ? "Puedes debilitar el curfew"
                        : "No puedes debilitar el curfew"
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                  font.bold: true
                }
              }

              Text {
                textFormat: Text.PlainText
                width: parent.width
                text: root.detail && root.detail.edit_window
                      ? String(root.detail.edit_window.detail) : "leyendo…"
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                wrapMode: Text.WordWrap
              }
            }
          }

          // ---------- weekly tokens ----------
          PanelSectionHeader {
            width: parent.width
            text: "FICHAS DE LA SEMANA"
            foreground: root.foreground
            fontFamily: root.fontFamily
          }

          Item {
            width: parent.width
            implicitHeight: Math.max(pipRow.implicitHeight, tokenCount.implicitHeight)

            Row {
              id: pipRow
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(4)

              Repeater {
                model: root.tokensTotal
                Rectangle {
                  required property int index
                  width: Style.space(26)
                  height: Style.space(6)
                  radius: Style.cornerRadius > 0 ? height / 2 : 0
                  color: index < root.tokensLeft ? Color.accent : root.track
                }
              }
            }

            Text {
              id: tokenCount
              textFormat: Text.PlainText
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              text: root.tokensTotal > 0 ? root.tokensLeft + " / " + root.tokensTotal : "—"
              color: root.tokensLeft === 0 ? root.urgent : root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
            }
          }

          Text {
            textFormat: Text.PlainText
            width: parent.width
            visible: !!root.detail && String(root.detail.week_anchor) !== ""
            text: root.detail ? "Semana desde " + root.detail.week_anchor : ""
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }

          // ---------- what is blocked ----------
          PanelSectionHeader {
            width: parent.width
            text: "BLOQUEADO EN CURFEW"
            foreground: root.foreground
            fontFamily: root.fontFamily
          }

          InfoRow {
            width: parent.width
            title: "Aplicaciones"
            value: root.detail && root.detail.blocking
                   ? (root.detail.blocking.apps + " · " + root.detail.blocking.mode) : "—"
            muted: !root.detail || !root.detail.blocking || !root.detail.blocking.apps_enabled
          }

          InfoRow {
            width: parent.width
            title: "Sitios web"
            value: root.detail && root.detail.blocking
                   ? (root.detail.blocking.sites + " bloqueados") : "—"
            muted: !root.detail || !root.detail.blocking || !root.detail.blocking.sites_enabled
          }

          InfoRow {
            width: parent.width
            title: "Juegos"
            value: root.detail && root.detail.blocking
                   ? (root.detail.blocking.games ? "detectados solos" : "sin bloquear") : "—"
            muted: !root.detail || !root.detail.blocking || !root.detail.blocking.games
          }

          // ---------- warnings ----------
          // Only ever present when something is genuinely wrong, so empty space
          // here is the good state.
          Repeater {
            model: root.detail && root.detail.warnings ? root.detail.warnings : []

            Rectangle {
              required property string modelData
              width: column.width
              implicitHeight: warnText.implicitHeight + Style.space(14)
              radius: Style.cornerRadius
              color: root.alpha(root.urgent, 0.12)
              border.width: Style.normalBorderWidth
              border.color: root.alpha(root.urgent, 0.5)

              Text {
                id: warnText
                textFormat: Text.PlainText
                x: Style.space(7)
                y: Style.space(7)
                width: parent.width - Style.space(14)
                text: "⚠ " + parent.modelData
                color: root.urgent
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                wrapMode: Text.WordWrap
              }
            }
          }

          Text {
            textFormat: Text.PlainText
            width: parent.width
            visible: root.detailFailed && !root.detail
            text: "Detalle no disponible: el ngtui instalado no conoce «panel». Ejecuta el despliegue."
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }

          PanelSeparator { width: parent.width; foreground: root.foreground }

          // ---------- actions ----------
          // Both open something. Neither changes state: the signer is the only
          // thing that may, and it is reached through the terminal UI.
          Row {
            spacing: Style.space(8)

            Button {
              text: "Abrir ngtui"
              tooltipText: "La interfaz completa — lo único que puede cambiar algo"
              bordered: true
              foreground: root.foreground
              fontFamily: root.fontFamily
              fontSize: Style.font.caption
              onClicked: root.openTui()
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
  }
}
