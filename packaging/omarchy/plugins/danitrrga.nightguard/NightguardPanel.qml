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
// It can now write, and the way it writes is the product. An edit stages
// locally, `ngtui propose` asks the SIGNER'S OWN classifier what that edit does
// and what it costs, the cost and any refusal go on screen, and only then does
// a confirmation lead to `pkexec` and the root signer. Nothing here classifies
// a direction, counts a token or decides a refusal; it renders what the signer
// said. The staging and the two CLI calls live in NightguardWriter.qml, shared
// with the workshop so the surface that prices a change and the surface that
// signs it can never drift apart.
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

  readonly property var blocking: detail && detail.blocking ? detail.blocking : null
  readonly property var blockedEntries: blocking && blocking.entries ? blocking.entries : []
  // The mode does not filter one list, it chooses which of two lists governs --
  // and it inverts what the list MEANS. Naming the section from the mode is the
  // difference between "these die" and "only these live".
  readonly property bool allowlistMode: !!blocking && String(blocking.mode) === "allowlist"

  // What this machine actually answers to for one configured entry. A state the
  // payload could not read renders as a dash: not read is not the same as fine,
  // and it is not the same as broken, and guessing either way is a lie the user
  // would act on.
  // The row's two halves. The left is the name a person recognises, falling
  // back to the raw identity when no desktop entry claims it. The right is
  // whichever fact is worth the column: the identity being enforced when all
  // is well, and the alarm when the entry names nothing on this machine.
  function entryTitle(entry) {
    return entry && entry.label ? String(entry.label) : String(entry ? entry.name : "")
  }

  function entryValue(entry) {
    if (!entry) return "—"
    if (String(entry.state) === "unmatched") return "no coincide con nada"
    if (!entry.state) return "—"
    return entry.label ? String(entry.name) : root.resolutionWord(entry.state)
  }

  function entryColor(entry) {
    return entry && String(entry.state) === "unmatched" ? root.urgent : root.dim
  }

  function resolutionWord(state) {
    switch (String(state)) {
    case "running":   return "activa ahora"
    case "installed": return "instalada"
    case "unmatched": return "no coincide con nada"
    default:          return "—"
    }
  }

  function resolutionColor(state) {
    switch (String(state)) {
    case "unmatched": return root.urgent
    case "running":   return root.foreground
    case "installed": return root.dim
    default:          return root.dim
    }
  }

  // The payload's verdict word is English because the terminal UI and the bar
  // widget read the same field. This surface is Spanish throughout, so it is
  // translated here rather than in the payload -- and an unrecognised verdict
  // falls through to whatever the payload said, so a verdict added later shows
  // up untranslated instead of vanishing.
  readonly property string stateWord: {
    if (!detail) return "…"
    switch (String(detail.verdict)) {
    case "locked":          return "CERRADO"
    case "outside_curfew":  return "ABIERTO"
    case "grace_active":    return "GRACIA"
    case "clock_tamper":    return "RELOJ MANIPULADO"
    case "offline_blocked": return "SIN RED"
    case "unavailable":     return "NO DISPONIBLE"
    default:                return String(detail.word)
    }
  }
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

  // The staging + signing path, shared with the workshop. Re-reading after a
  // commit is not optimism-avoidance decoration: the token count, the roster
  // and the switches must all come back from the config that was actually
  // signed, never from what this panel believed it asked for.
  NightguardWriter {
    id: writer
    tokensTotal: root.tokensTotal > 0 ? root.tokensTotal : 3
    onCommitted: root.refresh()
  }

  readonly property color resultColor: {
    switch (writer.resultKind) {
    case "ok":        return Color.accent
    case "refused":   return root.urgent
    case "error":     return root.urgent
    default:          return root.dim
    }
  }

  // The description under each switch says what the state MEANS, not what it
  // is. "0 bloqueados" could not tell "off" from "on with nothing to enforce",
  // and those are opposite problems.
  readonly property string gamesDescription: {
    if (!blocking) return "—"
    return blocking.games
      ? "Steam y Heroic, detectados solos según los instalas"
      : "los juegos que instales no quedan cubiertos"
  }

  readonly property string sitesDescription: {
    if (!blocking) return "—"
    if (!blocking.sites_enabled) return "desactivado — la política del navegador no se aplica"
    if (blocking.sites === 0) return "activo, pero sin ninguna dirección que aplicar"
    return blocking.sites + (blocking.sites === 1 ? " dirección" : " direcciones") + " · vía la política del navegador"
  }

  // Where the first action button sits on screen while the panel is open.
  // Published so a test can put a real pointer on it: driving the same function
  // over IPC proves the function works, not that the button is reachable, and
  // "the buttons do nothing" was a claim about reachability.
  function actionButtonRect() {
    if (!opened || !tuiButton) return null
    var p = tuiButton.mapToGlobal(0, 0)
    return { x: p.x, y: p.y, w: tuiButton.width, h: tuiButton.height }
  }
  // The workshop is a second entry point of this same plugin, so the shell
  // opens it by id rather than the panel spawning a process of its own. `toggle`
  // and not `summon`: clicking twice should put it away, not summon a second.
  function openWorkshop() {
    // Single-quoted: `bar.run` hands the string to `bash -lc`, and an unquoted
    // {} is one comma away from being brace-expanded into something else.
    if (root.bar) root.bar.run("omarchy-shell shell toggle danitrrga.nightguard '{}'")
    root.close()
  }

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

  // The payload describes the window in English because it is also read by
  // non-Spanish surfaces; this panel is Spanish throughout, so the ordinary
  // open/closed cases are composed here from the structured minutes. The edge
  // states (unconfigured, disabled, malformed, clock unverified) keep the
  // payload's own wording -- those are judgements, not descriptions, and
  // rewording a judgement is how a panel starts disagreeing with the signer.
  readonly property string gateDetail: {
    if (!detail || !detail.edit_window) return "leyendo…"
    var w = detail.edit_window
    if (w.configured !== true) return String(w.detail)
    if (nowMinutes < 0) return String(w.detail)
    if (windowStartMin < 0 || windowEndMin < 0) return String(w.detail)
    if (w.open === true)
      return "abierta hasta las " + w.end + " · quedan " + humanDuration(untilMinutes(windowEndMin))
    return "se abre a las " + w.start + " · quedan " + humanDuration(untilMinutes(windowStartMin))
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

  }

  // One thing that dies tonight. A bordered, filled object rather than a line
  // of text: the roster is the subject of this panel, and a run of flat
  // label/value lines reads as a printout of the config no matter what the
  // words say. An entry that names nothing is tinted urgent as a whole row --
  // the defect belongs to the entry, not to a word at its right edge.
  component EntryRow: Rectangle {
    id: entryRow
    property var entry: null
    readonly property bool broken: !!entry && String(entry.state) === "unmatched"

    implicitHeight: entryLabel.implicitHeight + Style.space(14)
    radius: Style.cornerRadius
    color: entryRow.broken ? root.alpha(root.urgent, 0.10)
                           : Style.normalFillFor(root.foreground, Color.accent)
    border.width: Style.normalBorderWidth
    border.color: entryRow.broken ? root.alpha(root.urgent, 0.45)
                                  : Style.normalBorderFor(root.foreground, Color.accent)

    Text {
      id: entryLabel
      textFormat: Text.PlainText
      anchors.left: parent.left
      anchors.leftMargin: Style.spacing.rowPaddingX
      anchors.verticalCenter: parent.verticalCenter
      text: root.entryTitle(entryRow.entry)
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall
    }

    Text {
      textFormat: Text.PlainText
      anchors.right: parent.right
      anchors.rightMargin: Style.spacing.rowPaddingX
      anchors.left: entryLabel.right
      anchors.leftMargin: Style.spacing.sm
      anchors.verticalCenter: parent.verticalCenter
      horizontalAlignment: Text.AlignRight
      text: root.entryValue(entryRow.entry)
      color: root.entryColor(entryRow.entry)
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
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
    // The footer is pinned, so its height is part of what the popup must be
    // tall enough for -- leaving it out let the scroll area eat the apply
    // button whenever the content was long, which is exactly when it matters.
    //
    // The cap is a last resort and not the real limit: `fittedContentHeight`
    // already clamps to `availableCardHeight`, which is the screen. A cap of
    // 660 was a number picked when the roster was two entries long, and it bit
    // first the moment it was seven -- the sites card and the buttons under it
    // were simply cut off, with the scroll area sized to hide that they were
    // there at all.
    contentHeight: panel.fittedContentHeight(
      column.implicitHeight + (footer.visible ? footer.implicitHeight + Style.space(10) : 0),
      Style.space(900))

    // Overlays the whole popup. The gate between a click and an authentication
    // dialog: it states the consequence in one sentence, in the user's own
    // terms, using the direction and cost the SIGNER computed -- so the
    // sentence cannot say "free" about a change the signer is about to charge
    // for. `selectedIndex: 0` starts on Cancel, because the default answer to
    // "do you want to weaken this?" at two in the morning is no.
    ConfirmDialog {
      id: confirmApply
      anchors.fill: parent
      z: 100
      message: writer.confirmMessage
      cancelText: "Cancelar"
      confirmText: writer.applyLabel
      selectedIndex: 0
      foreground: root.foreground
      fontFamily: root.fontFamily
      onCanceled: { opened = false; selectedIndex = 0 }
      onConfirmed: { opened = false; selectedIndex = 0; writer.apply() }
    }

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent

      // While the confirmation is up, Esc answers the question rather than
      // closing the panel out from under it.
      //
      // There is deliberately no key that CONFIRMS. Enter is one keystroke from
      // a fingerprint prompt, and a single unmodified keystroke that ends in an
      // authorised write is exactly the impulse this product exists to slow
      // down. Confirming is a click, on a button that starts unselected.
      onCloseRequested: {
        if (confirmApply.opened) { confirmApply.opened = false; confirmApply.selectedIndex = 0 }
        else root.close()
      }
      onActivateRequested: if (!confirmApply.opened) root.refresh()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      // Enter/Space only ever reach refresh(), so the panel's own actions had
      // no keyboard path at all. Mnemonics, matching the clock panel's 't'/'T'
      // pattern, rather than a cursor/onMoveRequested pair for three buttons
      // (found in the cross-model UI audit, 2026-09-07).
      //
      // 'a' is deliberately NOT bound to apply: a single unmodified keystroke
      // that leads to an authentication dialog is the impulse this whole
      // product exists to slow down.
      onTextKey: function(t) {
        if (confirmApply.opened) return
        if (t === "r" || t === "R") root.refresh()
        else if (t === "o" || t === "O") root.openWorkshop()
        else if (t === "d" || t === "D") writer.discard()
      }

      // The scroll holds everything you READ. What you must ACT on is pinned
      // below it: a cost line and an apply button that can be scrolled out of
      // sight are a cost line and an apply button the user does not know are
      // there, and this is the one place in the product where that matters.
      Flickable {
        id: panelFlick
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: footer.top
        anchors.bottomMargin: footer.visible ? Style.space(10) : 0
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

            // The week's remaining tokens sit with the state rather than in a
            // section of their own: what you may still spend is part of where
            // you stand, and it cost a heading and a whole band to say it
            // twice. The hero reserves this space itself.
            trailingControl: Component {
              Row {
                spacing: Style.space(4)

                Repeater {
                  model: root.tokensTotal
                  Rectangle {
                    required property int index
                    width: Style.space(22)
                    height: Style.space(6)
                    anchors.verticalCenter: parent.verticalCenter
                    radius: Style.cornerRadius > 0 ? height / 2 : 0
                    color: index < root.tokensLeft ? Color.accent : root.track
                  }
                }
              }
            }
          }

          PanelSeparator { width: parent.width; foreground: root.foreground }

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
                text: root.gateDetail
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                wrapMode: Text.WordWrap
              }
            }
          }

          // ---------- what dies tonight ----------
          // Names, not a count. A count cannot say that an entry matches
          // nothing, and an entry that matches nothing is a pact that is
          // quietly not being kept. On this machine "discord" named nothing at
          // all for months -- it is a webapp and runs as chromium -- and the
          // old "2 · blocklist" row had no way to show it.
          PanelSectionHeader {
            width: parent.width
            text: root.allowlistMode ? "SOBREVIVEN ESTA NOCHE" : "MUEREN ESTA NOCHE"
            foreground: root.foreground
            fontFamily: root.fontFamily
          }

          Text {
            textFormat: Text.PlainText
            width: parent.width
            visible: root.allowlistMode
            text: "Todo lo demás muere."
            color: root.urgent
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }

          Column {
            width: parent.width
            spacing: Style.spacing.xs

            Repeater {
              model: root.blockedEntries

              EntryRow {
                required property var modelData
                width: column.width
                entry: modelData
              }
            }
          }

          Text {
            textFormat: Text.PlainText
            width: parent.width
            visible: root.blockedEntries.length === 0
            // Both empties are dangers, and opposite ones: nothing listed in
            // blocklist mode means the tool does nothing, and nothing listed in
            // allowlist mode means nothing survives.
            text: root.allowlistMode
                  ? "Ninguna permitida — en este modo no sobreviviría nada."
                  : "Ninguna aplicación en la lista — no hay nada que terminar."
            color: root.urgent
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }

          // Not part of the roster above. These are settings that decide what
          // ELSE falls, and running them together as identical lines was what
          // made the whole panel read as four loose facts.
          //
          // Real switches, because the write path exists now. A switch shows
          // the value it WOULD have once applied, not the value on disk --
          // otherwise the control the user just flipped snaps back while the
          // change sits waiting in the pending list, which reads as the click
          // having failed.
          Toggle {
            width: parent.width
            label: "Bloquear juegos"
            description: root.gamesDescription
            foreground: root.foreground
            fontFamily: root.fontFamily
            checked: writer.stagedValue("blocking.native_apps.block_games",
                                        !!root.blocking && root.blocking.games === true) === true
            onClicked: writer.stage("blocking.native_apps.block_games", "set", !checked,
                                    checked ? "Dejar de bloquear juegos" : "Bloquear juegos")
          }

          Toggle {
            width: parent.width
            label: "Bloquear sitios"
            description: root.sitesDescription
            foreground: root.foreground
            fontFamily: root.fontFamily
            checked: writer.stagedValue("blocking.browser_extension.enabled",
                                        !!root.blocking && root.blocking.sites_enabled === true) === true
            onClicked: writer.stage("blocking.browser_extension.enabled", "set", !checked,
                                    checked ? "Dejar de bloquear sitios" : "Bloquear sitios")
          }

          // ---------- what is waiting to be signed ----------
          // Absent entirely when nothing is staged: a section that is always
          // there and usually empty teaches the eye to skip it, and this is the
          // one section that must never be skipped.
          PanelSeparator {
            width: parent.width
            foreground: root.foreground
            visible: writer.count > 0
          }

          PanelSectionHeader {
            width: parent.width
            visible: writer.count > 0
            text: "CAMBIOS PENDIENTES"
            foreground: root.foreground
            fontFamily: root.fontFamily
          }

          Column {
            width: parent.width
            spacing: Style.spacing.xs
            visible: writer.count > 0

            Repeater {
              model: writer.ops

              Rectangle {
                required property var modelData
                required property int index
                width: column.width
                implicitHeight: pendingLabel.implicitHeight + Style.space(12)
                radius: Style.cornerRadius
                color: Style.normalFillFor(root.foreground, Color.accent)
                border.width: Style.normalBorderWidth
                border.color: Style.normalBorderFor(root.foreground, Color.accent)

                Text {
                  id: pendingLabel
                  textFormat: Text.PlainText
                  anchors.left: parent.left
                  anchors.leftMargin: Style.spacing.rowPaddingX
                  anchors.verticalCenter: parent.verticalCenter
                  text: String(parent.modelData.label || parent.modelData.key)
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                }

                PanelActionButton {
                  anchors.right: parent.right
                  anchors.rightMargin: Style.space(6)
                  anchors.verticalCenter: parent.verticalCenter
                  iconText: "󰅖"
                  tooltipText: "Quitar este cambio"
                  foreground: root.foreground
                  fontFamily: root.fontFamily
                  onClicked: writer.unstage(parent.index)
                }
              }
            }
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
          // The workshop is where the app list is chosen; this panel holds the
          // two switches that are safe at a glance and nothing else.
          Row {
            width: parent.width
            spacing: Style.space(8)

            Button {
              id: tuiButton
              width: (parent.width - Style.space(8)) * 0.62
              text: "Abrir el taller"
              tooltipText: "Elegir qué aplicaciones y qué sitios mueren en curfew"
              bordered: true
              foreground: root.foreground
              fontFamily: root.fontFamily
              fontSize: Style.font.caption
              onClicked: root.openWorkshop()
            }

            Button {
              width: (parent.width - Style.space(8)) * 0.38
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

      Column {
        id: footer
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        spacing: Style.space(8)
        visible: writer.count > 0 || writer.resultText !== ""

        // The cost, before any authentication. This is the whole reason the
        // preview call exists and is unprivileged: a polkit dialog must never
        // be the first place the user learns what a change costs, and it must
        // never appear at all for a change the signer has already refused.
        Text {
          textFormat: Text.PlainText
          width: parent.width
          visible: writer.count > 0
          text: writer.costLine
          color: writer.refusalReason !== "" ? root.urgent
                                             : (writer.costsToken ? Color.accent : root.foreground)
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }

        Row {
          width: parent.width
          spacing: Style.space(8)
          visible: writer.count > 0

          Button {
            width: (parent.width - Style.space(8)) * 0.62
            text: writer.applyLabel
            tooltipText: "Firmar y aplicar — pedirá autorización"
            bordered: true
            enabled: writer.canApply
            opacity: writer.canApply ? 1 : 0.45
            foreground: writer.costsToken ? Color.accent : root.foreground
            fontFamily: root.fontFamily
            fontSize: Style.font.caption
            onClicked: if (writer.canApply) confirmApply.opened = true
          }

          Button {
            width: (parent.width - Style.space(8)) * 0.38
            text: "Descartar"
            tooltipText: "Olvidar los cambios sin aplicar"
            bordered: true
            foreground: root.foreground
            fontFamily: root.fontFamily
            fontSize: Style.font.caption
            onClicked: writer.discard()
          }
        }

        // What the signer said, in its own words inside a Spanish frame.
        Text {
          textFormat: Text.PlainText
          width: parent.width
          visible: writer.resultText !== ""
          text: writer.resultText
          color: root.resultColor
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }
      }
    }
  }
}
