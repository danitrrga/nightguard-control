import QtQuick
import QtQuick.Controls
import qs.Commons
import qs.Ui

// The landing: what is true right now, before anything is changed.
//
// The two editing views answer "what do you want this to become". This one
// answers the four questions somebody actually opens the application with, in
// the order they ask them:
//
//   1. am I in curfew, and how long until that changes   -> the dial
//   2. can I change anything at this hour                -> the gate + the tokens
//   3. what dies tonight                                 -> the roster
//   4. is any of it actually switched on                 -> the defences
//
// It shows the SIGNED state and nothing else. A staged change previews inside
// the view that stages it; if the landing previewed too, two surfaces would be
// showing different futures and neither would be the present. What it does say
// is how many changes are waiting, because "this is not what you are looking
// at" is itself an answer to question one.
Item {
  id: glance

  property var detail: null
  property string mode: "blocklist"
  property int pendingCount: 0

  property color foregroundColor: Color.foreground
  property color dimColor: Qt.darker(Color.foreground, 1.55)
  property color trackColor: Style.selectedFillFor(Color.foreground, Color.accent)
  property color urgentColor: Color.urgent
  property color voidColor: Color.background
  property string fontFamily: Style.font.family

  signal goToApps()
  signal goToSchedule()

  readonly property bool allowlistMode: glance.mode === "allowlist"
  readonly property var blocking: detail && detail.blocking ? detail.blocking : null
  readonly property var defences: detail && detail.defences ? detail.defences : null
  readonly property var entries: blocking && blocking.entries ? blocking.entries : []
  readonly property var siteEntries: blocking && blocking.site_entries ? blocking.site_entries : []
  readonly property var warnings: detail && detail.warnings ? detail.warnings : []

  readonly property int tokensLeft: detail ? Number(detail.tokens_left) : 0
  readonly property int tokensTotal: detail ? Number(detail.tokens_total) : 0

  function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

  NightguardClock {
    id: clock
    detail: glance.detail
  }

  readonly property color stateColor: {
    switch (clock.verdict) {
    case "locked":          return glance.urgentColor
    case "clock_tamper":    return glance.urgentColor
    case "grace_active":    return Color.accent
    case "offline_blocked": return Color.accent
    case "outside_curfew":  return glance.foregroundColor
    default:                return glance.dimColor
    }
  }

  // What the roster means depends on which way round the mode has it, and the
  // two readings are opposites. Getting this wrong would print the list of
  // programs that survive under the heading of the ones that die.
  readonly property string rosterTitle: allowlistMode ? "SOBREVIVEN AL CURFEW" : "MUEREN ESTA NOCHE"
  readonly property string rosterEmpty: allowlistMode
    ? "Lista vacía: en este modo muere todo, incluida tu terminal."
    : "Todavía no muere nada en curfew."
  readonly property bool rosterEmptyIsDangerous: allowlistMode

  // How many rows fit before the list stops being a glance and becomes the
  // other view. Five, then a count.
  readonly property int rosterShown: Math.min(5, entries.length)

  function entryName(entry) {
    return entry && entry.label ? String(entry.label) : String(entry ? entry.name : "")
  }
  function entrySecond(entry) {
    if (!entry) return ""
    if (String(entry.state) === "unmatched") return "no coincide con nada"
    return entry.label ? String(entry.name) : glance.resolutionWord(entry.state)
  }
  function resolutionWord(state) {
    switch (String(state)) {
    case "running":   return "corriendo ahora"
    case "installed": return "instalada"
    case "game":      return "juego detectado"
    default:          return ""
    }
  }
  function entryColor(entry) {
    return entry && String(entry.state) === "unmatched" ? glance.urgentColor : glance.dimColor
  }

  // ---- pieces ---------------------------------------------------------------

  // A heading with the thing it counts, and the way to go and change it. One
  // control per section rather than a row of buttons at the bottom: the button
  // that edits the roster belongs beside the roster, where the question it
  // answers was just asked.
  component SectionBar: Item {
    id: sectionBar
    property string title: ""
    property string count: ""
    property string action: ""
    signal activated()

    implicitHeight: Math.max(barHeader.implicitHeight, actionButton.implicitHeight)

    PanelSectionHeader {
      id: barHeader
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      text: sectionBar.title
      foreground: glance.foregroundColor
      fontFamily: glance.fontFamily
    }

    Text {
      anchors.left: barHeader.right
      anchors.leftMargin: Style.space(8)
      anchors.verticalCenter: barHeader.verticalCenter
      visible: sectionBar.count !== ""
      textFormat: Text.PlainText
      text: sectionBar.count
      color: glance.dimColor
      font.family: glance.fontFamily
      font.pixelSize: Style.font.caption
    }

    Button {
      id: actionButton
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      visible: sectionBar.action !== ""
      text: sectionBar.action
      bordered: true
      foreground: glance.foregroundColor
      fontFamily: glance.fontFamily
      fontSize: Style.font.caption
      onClicked: sectionBar.activated()
    }
  }

  // One fact with a state: a dot that is accent when the thing is doing its
  // job and urgent when it is not, the name, and a sentence about what that
  // means. The dot is never the only carrier -- the sentence changes too, so a
  // reader who cannot separate the two hues still gets the answer.
  component FactRow: Item {
    id: factRow
    property string label: ""
    property string note: ""
    property bool on: false
    property bool neutral: false

    implicitHeight: factCol.implicitHeight + Style.space(10)

    Rectangle {
      id: dot
      width: Style.space(7)
      height: width
      radius: width / 2
      x: Style.space(2)
      y: factCol.y + Style.space(4)
      color: factRow.neutral ? glance.dimColor
                             : (factRow.on ? Color.accent : glance.urgentColor)
    }

    Column {
      id: factCol
      anchors.left: dot.right
      anchors.leftMargin: Style.space(10)
      anchors.right: parent.right
      y: Style.space(5)
      spacing: Style.space(2)

      Text {
        width: parent.width
        textFormat: Text.PlainText
        text: factRow.label
        color: glance.foregroundColor
        font.family: glance.fontFamily
        font.pixelSize: Style.font.bodySmall
        elide: Text.ElideRight
      }
      Text {
        width: parent.width
        textFormat: Text.PlainText
        visible: factRow.note !== ""
        text: factRow.note
        color: glance.dimColor
        font.family: glance.fontFamily
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }
    }
  }

  // ---- the view -------------------------------------------------------------

  Flickable {
    anchors.fill: parent
    contentWidth: width
    contentHeight: column.implicitHeight
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

    Column {
      id: column
      width: parent.width
      spacing: Style.space(18)

      // ---------- 1 · where the night stands ----------
      Rectangle {
        width: parent.width
        implicitHeight: Math.max(dialColumn.implicitHeight, stateColumn.implicitHeight) + Style.space(28)
        radius: Style.cornerRadius
        color: Style.normalFillFor(glance.foregroundColor, Color.accent)
        border.width: Style.normalBorderWidth
        border.color: Style.normalBorderFor(glance.foregroundColor, Color.accent)

        Column {
          id: dialColumn
          x: Style.space(16)
          anchors.verticalCenter: parent.verticalCenter
          width: Style.space(226)
          spacing: Style.space(8)

        DayDial {
          id: dial
          width: parent.width
          height: width
          showTimes: true
          headlineSize: Style.font.display
          curfewStart: clock.curfewStartMin
          curfewEnd: clock.curfewEndMin
          windowStart: clock.windowStartMin
          windowEnd: clock.windowEndMin
          nowMinutes: clock.nowMinutes
          headline: clock.dialHeadline
          caption: clock.dialCaption
          startLabel: clock.curfewStartText
          endLabel: clock.curfewEndText
          headlineColor: clock.locked ? glance.urgentColor : glance.foregroundColor
          foregroundColor: glance.foregroundColor
          dimColor: glance.dimColor
          trackColor: glance.trackColor
          curfewColor: glance.urgentColor
          fontFamily: glance.fontFamily
          // The card is a tinted fill over the window, so the notches have to be
          // punched in the window's colour blended with that fill -- not in the
          // window's colour, which would show as pale nicks.
          voidColor: Qt.tint(glance.voidColor,
                             Style.normalFillFor(glance.foregroundColor, Color.accent))
        }

          // The key. Two arcs on one ring is a chart until something says which
          // is which, and the inner one — the hours the pact may be weakened —
          // is the half nobody would guess.
          Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: Style.space(14)

            Repeater {
              model: [
                { swatch: glance.urgentColor, text: "curfew" },
                { swatch: Color.accent,       text: "puedes editar" },
              ]

              Row {
                required property var modelData
                spacing: Style.space(5)

                Rectangle {
                  anchors.verticalCenter: parent.verticalCenter
                  width: Style.space(12)
                  height: Style.space(3)
                  radius: Style.cornerRadius > 0 ? height / 2 : 0
                  color: parent.modelData.swatch
                }
                Text {
                  anchors.verticalCenter: parent.verticalCenter
                  textFormat: Text.PlainText
                  text: parent.modelData.text
                  color: glance.dimColor
                  font.family: glance.fontFamily
                  font.pixelSize: Style.font.caption
                }
              }
            }
          }
        }

        Column {
          id: stateColumn
          anchors.left: dialColumn.right
          anchors.leftMargin: Style.space(22)
          anchors.right: parent.right
          anchors.rightMargin: Style.space(18)
          anchors.verticalCenter: parent.verticalCenter
          spacing: Style.space(10)

          Text {
            textFormat: Text.PlainText
            text: clock.stateWord
            color: glance.stateColor
            font.family: glance.fontFamily
            font.pixelSize: Style.font.displayLarge
            font.bold: true
          }

          Text {
            width: parent.width
            visible: text !== ""
            textFormat: Text.PlainText
            text: clock.curfewSentence
            color: clock.curfewSentenceIsWarning ? glance.urgentColor : glance.dimColor
            font.family: glance.fontFamily
            font.pixelSize: Style.font.bodySmall
            wrapMode: Text.WordWrap
            lineHeight: 1.25
          }

          // The gate. Its own object because it is the one thing on this screen
          // that answers a question about the reader rather than about the
          // night: not "what happens", but "what may you do about it".
          Rectangle {
            width: parent.width
            implicitHeight: gateColumn.implicitHeight + Style.space(18)
            radius: Style.cornerRadius
            color: clock.windowOpen ? glance.alpha(Color.accent, 0.10)
                                    : glance.alpha(glance.urgentColor, 0.10)
            border.width: Style.normalBorderWidth
            border.color: clock.windowOpen ? glance.alpha(Color.accent, 0.55)
                                           : glance.alpha(glance.urgentColor, 0.55)

            Column {
              id: gateColumn
              x: Style.spacing.rowPaddingX
              y: Style.space(9)
              width: parent.width - Style.spacing.rowPaddingX * 2
              spacing: Style.space(3)

              Row {
                spacing: Style.space(8)

                Text {
                  textFormat: Text.PlainText
                  text: clock.windowOpen ? "󰌿" : "󰌾"
                  color: clock.windowOpen ? Color.accent : glance.urgentColor
                  font.family: glance.fontFamily
                  font.pixelSize: Style.font.body
                }
                Text {
                  textFormat: Text.PlainText
                  text: clock.gateHeadline
                  color: glance.foregroundColor
                  font.family: glance.fontFamily
                  font.pixelSize: Style.font.bodySmall
                }
              }

              Text {
                width: parent.width
                textFormat: Text.PlainText
                text: clock.gateDetail
                color: glance.dimColor
                font.family: glance.fontFamily
                font.pixelSize: Style.font.caption
                wrapMode: Text.WordWrap
              }
            }
          }

          // The week's tokens. Pips and not a number because the question is
          // "have I got one left", and three marks answer it without reading.
          Row {
            spacing: Style.space(10)

            Row {
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(4)
              Repeater {
                model: glance.tokensTotal
                Rectangle {
                  required property int index
                  width: Style.space(22)
                  height: Style.space(6)
                  radius: Style.cornerRadius > 0 ? height / 2 : 0
                  color: index < glance.tokensLeft ? Color.accent : glance.trackColor
                }
              }
            }

            Text {
              anchors.verticalCenter: parent.verticalCenter
              textFormat: Text.PlainText
              text: glance.tokensLeft === 0
                    ? "sin fichas — no puedes debilitar nada hasta el lunes"
                    : glance.tokensLeft + (glance.tokensLeft === 1
                        ? " ficha esta semana" : " fichas esta semana")
              color: glance.tokensLeft === 0 ? glance.urgentColor : glance.dimColor
              font.family: glance.fontFamily
              font.pixelSize: Style.font.caption
            }
          }
        }
      }

      // ---------- 2 · the roster ----------
      Column {
        width: parent.width
        spacing: Style.space(8)

        SectionBar {
          width: parent.width
          title: glance.rosterTitle
          count: glance.entries.length > 0 ? String(glance.entries.length) : ""
          action: "Elegir qué muere"
          onActivated: glance.goToApps()
        }

        Text {
          width: parent.width
          visible: glance.entries.length === 0
          textFormat: Text.PlainText
          text: glance.rosterEmpty
          color: glance.rosterEmptyIsDangerous ? glance.urgentColor : glance.dimColor
          font.family: glance.fontFamily
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }

        // Two columns, because five one-line rows down a 440px column is a
        // stack of mostly-empty rows, and the roster is the second thing the
        // eye should land on -- not the longest.
        Grid {
          width: parent.width
          columns: 2
          columnSpacing: Style.space(8)
          rowSpacing: Style.space(6)

          Repeater {
            model: glance.rosterShown

            Rectangle {
              id: entryCard
              required property int index
              readonly property var entry: glance.entries[index]
              width: (parent.width - Style.space(8)) / 2
              implicitHeight: Math.max(entryCol.implicitHeight + Style.space(12), Style.space(38))
              radius: Style.cornerRadius
              color: Style.normalFillFor(glance.foregroundColor, Color.accent)
              border.width: Style.normalBorderWidth
              border.color: String(entryCard.entry.state) === "unmatched"
                            ? glance.alpha(glance.urgentColor, 0.6)
                            : Style.normalBorderFor(glance.foregroundColor, Color.accent)

              Column {
                id: entryCol
                x: Style.spacing.rowPaddingX
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - Style.spacing.rowPaddingX * 2
                spacing: Style.space(1)

                Text {
                  width: parent.width
                  textFormat: Text.PlainText
                  text: glance.entryName(entryCard.entry)
                  color: glance.foregroundColor
                  font.family: glance.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  elide: Text.ElideRight
                }
                Text {
                  width: parent.width
                  textFormat: Text.PlainText
                  visible: text !== ""
                  text: glance.entrySecond(entryCard.entry)
                  color: glance.entryColor(entryCard.entry)
                  font.family: glance.fontFamily
                  font.pixelSize: Style.font.caption
                  elide: Text.ElideRight
                }
              }
            }
          }

          // The rest, as the last cell rather than a line under the grid: a
          // count that sits outside the shape it counts reads as a footnote,
          // and this one is a door.
          Rectangle {
            id: overflowCard
            visible: glance.entries.length > glance.rosterShown
            width: (parent.width - Style.space(8)) / 2
            implicitHeight: Style.space(38)
            radius: Style.cornerRadius
            color: overflowMouse.containsMouse
                   ? Style.hoverFillFor(glance.foregroundColor, Color.accent)
                   : "transparent"
            border.width: Style.normalBorderWidth
            border.color: Style.normalBorderFor(glance.foregroundColor, Color.accent)

            MouseArea {
              id: overflowMouse
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: glance.goToApps()
            }

            Text {
              x: Style.spacing.rowPaddingX
              anchors.verticalCenter: parent.verticalCenter
              textFormat: Text.PlainText
              text: "y " + (glance.entries.length - glance.rosterShown) + " más"
              color: glance.dimColor
              font.family: glance.fontFamily
              font.pixelSize: Style.font.bodySmall
            }
          }
        }

        FactRow {
          width: parent.width
          label: !glance.blocking || !glance.blocking.games
                 ? "Los juegos nuevos no quedan cubiertos"
                 : "Los juegos nuevos quedan cubiertos solos"
          note: !glance.blocking || !glance.blocking.games
                ? "un juego instalado mañana seguiría abriéndose esta noche"
                : "Steam y Heroic, según los instalas"
          on: !!glance.blocking && glance.blocking.games === true
        }

        FactRow {
          width: parent.width
          label: glance.siteEntries.length === 0
                 ? "Ningún sitio bloqueado"
                 : glance.siteEntries.length + (glance.siteEntries.length === 1
                     ? " sitio bloqueado" : " sitios bloqueados")
          note: !glance.blocking || glance.blocking.sites_enabled !== true
                ? "la política del navegador está desactivada"
                : (glance.siteEntries.length === 0
                   ? "la política del navegador está activa, pero no tiene ninguna dirección que aplicar"
                   : glance.siteEntries.join(" · "))
          on: !!glance.blocking && glance.blocking.sites_enabled === true
              && glance.siteEntries.length > 0
          neutral: !!glance.blocking && glance.blocking.sites_enabled === true
                   && glance.siteEntries.length === 0
        }
      }

      // ---------- 3 · the defences ----------
      Column {
        width: parent.width
        spacing: Style.space(8)

        SectionBar {
          width: parent.width
          title: "LAS DEFENSAS"
          action: "Ajustar el horario"
          onActivated: glance.goToSchedule()
        }

        // No reading is not the same as OFF, and drawing it as OFF is the
        // dangerous direction: a red dot beside "las ediciones a mano se
        // quedan" on a machine whose watchdog is running tells the reader to go
        // and fix something that is not broken -- and teaches them to ignore
        // the dot. An older ngtui carries no reading of these at all, which is
        // exactly when this happens.
        FactRow {
          width: parent.width
          visible: !glance.defences
          label: "No se puede leer el estado de las defensas"
          note: "el ngtui instalado es anterior a esta lectura — vuelve a desplegar para verlas"
          neutral: true
        }

        FactRow {
          width: parent.width
          visible: !!glance.defences
          label: glance.defences && glance.defences.watchdog.enabled
                 ? "Las ediciones a mano se revierten"
                 : "Las ediciones a mano se quedan"
          note: {
            if (!glance.defences) return ""
            var w = glance.defences.watchdog
            if (!w.enabled) return "el vigilante está apagado — cualquiera que edite el archivo a mano gana"
            return w.check_interval_seconds > 0
                   ? "el vigilante comprueba cada " + w.check_interval_seconds + " s y devuelve el archivo firmado"
                   : "el vigilante devuelve el archivo firmado"
          }
          on: !!glance.defences && glance.defences.watchdog.enabled === true
        }

        FactRow {
          width: parent.width
          visible: !!glance.defences
          label: glance.defences && glance.defences.clock_protection.enabled
                 ? "El reloj está vigilado"
                 : "El reloj no está vigilado"
          note: {
            if (!glance.defences) return ""
            var c = glance.defences.clock_protection
            if (!c.enabled) return "atrasar la hora del sistema abriría el curfew sin gastar nada"
            return c.max_offset_minutes > 0
                   ? "un desfase de más de " + c.max_offset_minutes + " min se lee como manipulación"
                   : "un desfase con la hora real se lee como manipulación"
          }
          on: !!glance.defences && glance.defences.clock_protection.enabled === true
        }
      }

      // ---------- 4 · anything the stack wants to say ----------
      Repeater {
        model: glance.warnings

        Rectangle {
          required property var modelData
          width: column.width
          implicitHeight: warnText.implicitHeight + Style.space(18)
          radius: Style.cornerRadius
          color: glance.alpha(glance.urgentColor, 0.10)
          border.width: Style.normalBorderWidth
          border.color: glance.alpha(glance.urgentColor, 0.55)

          Text {
            id: warnText
            x: Style.spacing.rowPaddingX
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - Style.spacing.rowPaddingX * 2
            textFormat: Text.PlainText
            text: String(modelData)
            color: glance.foregroundColor
            font.family: glance.fontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }
        }
      }
    }
  }
}
