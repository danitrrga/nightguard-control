import QtQuick
import QtQuick.Controls
import QtQuick.Shapes
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

  // Where the first action button sits on screen while the panel is open.
  // Published so a test can put a real pointer on it: driving the same function
  // over IPC proves the function works, not that the button is reachable, and
  // "the buttons do nothing" was a claim about reachability.
  function actionButtonRect() {
    if (!opened || !tuiButton) return null
    var p = tuiButton.mapToGlobal(0, 0)
    return { x: p.x, y: p.y, w: tuiButton.width, h: tuiButton.height }
  }
  function openTui() { if (hostWidget) hostWidget.openTui() }

  // A missing or non-numeric minute reads as "absent" rather than as undefined,
  // which QML complains about once per binding per repaint. An older ngtui has
  // no minute fields at all, and that must not fill the log.
  function minuteOr(value) {
    var n = Number(value)
    return isFinite(n) ? n : -1
  }

  readonly property int nowMinutes: minuteOr(detail ? detail.now_minutes : -1)
  readonly property int curfewStartMin: minuteOr(detail && detail.curfew ? detail.curfew.start_minutes : -1)
  readonly property int curfewEndMin: minuteOr(detail && detail.curfew ? detail.curfew.end_minutes : -1)
  readonly property int windowStartMin: minuteOr(detail && detail.edit_window ? detail.edit_window.start_minutes : -1)
  readonly property int windowEndMin: minuteOr(detail && detail.edit_window ? detail.edit_window.end_minutes : -1)

  function untilMinutes(target) {
    if (nowMinutes < 0 || target < 0) return -1
    var d = target - nowMinutes
    return d < 0 ? d + 1440 : d
  }

  function humanDuration(minutes) {
    if (minutes < 0) return "—"
    var h = Math.floor(minutes / 60)
    var m = minutes % 60
    if (h === 0) return m + " min"
    if (m === 0) return h + " h"
    return h + " h " + m
  }

  // The single number worth putting in the middle of the dial: how long until
  // the thing that is about to change, changes.
  readonly property int curfewLocked: verdict === "locked" ? 1 : 0
  readonly property string dialHeadline: {
    if (!detail || nowMinutes < 0) return "—"
    if (curfewLocked === 1) return humanDuration(untilMinutes(curfewEndMin))
    return humanDuration(untilMinutes(curfewStartMin))
  }
  readonly property string dialCaption: {
    if (!detail || nowMinutes < 0) return "hora sin verificar"
    return curfewLocked === 1 ? "hasta que abra" : "hasta el curfew"
  }

  // --- pieces ---------------------------------------------------------------

  // A 24-hour dial: the whole day as a ring, the curfew as one arc and the
  // hours the pact may be weakened as another, with a mark at now and the next
  // transition counted down in the middle.
  //
  // A ring rather than another bar because a day is a cycle, and the question
  // it answers — "how long until this changes?" — is a distance around a
  // circle. Built with Shape/PathAngleArc, which is how the shell draws its own
  // dial (Ui/SpeedTestOverlay.qml:265-321); Canvas is used nowhere in the tree.
  component DayDial: Item {
    id: dial

    property int curfewStart: -1
    property int curfewEnd: -1
    property int windowStart: -1
    property int windowEnd: -1
    property int nowMinutes: -1
    property string headline: ""
    property string caption: ""
    property color headlineColor: root.foreground

    readonly property real ringRadius: Math.min(width, height) / 2 - Style.space(7)
    readonly property real ringWidth: Math.max(Style.space(6), Style.space(7))

    // Midnight at the top, clockwise. PathAngleArc puts 0 degrees at 3 o'clock,
    // so the day starts a quarter turn back.
    function angleOf(minutes) { return -90 + (minutes / 1440) * 360 }

    // An arc that wraps midnight is still one arc here — unlike the flat strip,
    // a ring has no seam to split at, which is half the reason it reads better.
    function sweepOf(from, to) {
      var span = to - from
      if (span < 0) span += 1440
      return (span / 1440) * 360
    }
    function drawable(from, to) { return from >= 0 && to >= 0 && from !== to }

    implicitHeight: Style.space(150)

    Shape {
      anchors.fill: parent
      preferredRendererType: Shape.CurveRenderer

      // The day itself.
      ShapePath {
        strokeWidth: dial.ringWidth
        strokeColor: root.track
        fillColor: "transparent"
        capStyle: ShapePath.FlatCap
        PathAngleArc {
          centerX: dial.width / 2; centerY: dial.height / 2
          radiusX: dial.ringRadius; radiusY: dial.ringRadius
          startAngle: -90; sweepAngle: 360
        }
      }

      // The curfew.
      ShapePath {
        strokeWidth: dial.ringWidth
        strokeColor: dial.drawable(dial.curfewStart, dial.curfewEnd)
                     ? root.alpha(root.urgent, 0.85) : "transparent"
        fillColor: "transparent"
        capStyle: ShapePath.FlatCap
        PathAngleArc {
          centerX: dial.width / 2; centerY: dial.height / 2
          radiusX: dial.ringRadius; radiusY: dial.ringRadius
          startAngle: dial.angleOf(dial.curfewStart)
          sweepAngle: dial.drawable(dial.curfewStart, dial.curfewEnd)
                      ? dial.sweepOf(dial.curfewStart, dial.curfewEnd) : 0
        }
      }

      // When the pact may be weakened, on an inner track so the two never
      // overlap into an unreadable smear.
      ShapePath {
        strokeWidth: Math.max(2, Style.space(3))
        strokeColor: dial.drawable(dial.windowStart, dial.windowEnd)
                     ? Color.accent : "transparent"
        fillColor: "transparent"
        capStyle: ShapePath.FlatCap
        PathAngleArc {
          centerX: dial.width / 2; centerY: dial.height / 2
          radiusX: dial.ringRadius - dial.ringWidth
          radiusY: dial.ringRadius - dial.ringWidth
          startAngle: dial.angleOf(dial.windowStart)
          sweepAngle: dial.drawable(dial.windowStart, dial.windowEnd)
                      ? dial.sweepOf(dial.windowStart, dial.windowEnd) : 0
        }
      }
    }

    // Now.
    Rectangle {
      visible: dial.nowMinutes >= 0
      width: Style.space(7)
      height: width
      radius: width / 2
      color: root.foreground
      border.width: Math.max(1, Style.space(2))
      border.color: Color.popups.background
      x: dial.width / 2 + dial.ringRadius * Math.cos(dial.angleOf(dial.nowMinutes) * Math.PI / 180) - width / 2
      y: dial.height / 2 + dial.ringRadius * Math.sin(dial.angleOf(dial.nowMinutes) * Math.PI / 180) - height / 2
    }

    // The one number worth reading, in the middle where the eye lands.
    Column {
      anchors.centerIn: parent
      spacing: Style.space(2)

      Text {
        anchors.horizontalCenter: parent.horizontalCenter
        textFormat: Text.PlainText
        text: dial.headline
        color: dial.headlineColor
        font.family: root.fontFamily
        font.pixelSize: Style.font.heading
        font.bold: true
      }
      Text {
        anchors.horizontalCenter: parent.horizontalCenter
        textFormat: Text.PlainText
        text: dial.caption
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }
    }

    // 00 / 06 / 12 / 18, so the ring can be read as a clock.
    Repeater {
      model: [0, 6, 12, 18]
      Text {
        required property int modelData
        readonly property real a: dial.angleOf(modelData * 60) * Math.PI / 180
        textFormat: Text.PlainText
        text: modelData < 10 ? "0" + modelData : String(modelData)
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        x: dial.width / 2 + (dial.ringRadius + Style.space(9)) * Math.cos(a) - width / 2
        y: dial.height / 2 + (dial.ringRadius + Style.space(9)) * Math.sin(a) - height / 2
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
      // Enter/Space only ever reach refresh() — this panel has no per-button
      // focus, so "Abrir ngtui" (its whole reason to exist) had no keyboard
      // path at all. A mnemonic, matching the clock panel's 't'/'T' pattern,
      // rather than building a cursor/onMoveRequested pair for two buttons
      // (found in the cross-model UI audit, 2026-09-07).
      onTextKey: function(t) {
        if (t === "r" || t === "R") root.refresh()
        else if (t === "o" || t === "O") root.openTui()
      }

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
          // `width:` rather than anchors.fill, because a Flickable's content
          // item has no meaningful height to fill. This is NOT about a binding
          // loop: an earlier commit here claimed it was, and that was wrong.
          // Both external reviews and a control run of this suite agree —
          // anchoring a Column while the popup reads its implicitHeight is the
          // first-party idiom and loops nothing, since a Column's implicitHeight
          // comes from its children and never from its own height.
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

          DayDial {
            width: parent.width
            curfewStart: root.curfewStartMin
            curfewEnd: root.curfewEndMin
            windowStart: root.windowStartMin
            windowEnd: root.windowEndMin
            nowMinutes: root.nowMinutes
            headline: root.dialHeadline
            caption: root.dialCaption
            headlineColor: root.curfewLocked === 1 ? root.urgent : root.foreground
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
              id: tuiButton
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
