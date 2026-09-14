import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// The workshop: a window whose only job is choosing what dies in curfew.
//
// It exists because the dropdown cannot hold it. A hundred and one candidates
// with a filter, two lists and a cost line is not a popup, and the thing it
// replaces was worse than either — a text field you typed an executable name
// into from memory, with no way to find out whether you had spelled it the way
// the watchdog reads it.
//
// The left column is ordered by CONFIDENCE, and that ordering is the feature:
//
//   corriendo ahora   the process was read from /proc; the only case where the
//                     panel knows, rather than believes, that the watchdog
//                     would end it
//   tus juegos        matched by install path, so a launcher-hosted title is
//                     caught too
//   instaladas        a launcher pointing at a real binary — very likely right,
//                     never seen to be right
//   no son aplicaciones
//                     webapps. They all run as the same browser process, so
//                     blocking one as an app ends the browser and every other
//                     webapp with it. Their identity is the address, so they go
//                     to the site list instead — which is exactly the mistake
//                     already live in this machine's own config.
//
// Every row shows two names: the one you recognise, and the executable, which
// is the only string the watchdog can act on. Showing just the pretty one
// would be the lie.
Item {
  id: root

  // ---- plugin lifecycle (the shape a `panel`-kind entry point has) ---------
  property bool closingFromHost: false
  property var shell: null

  readonly property bool opened: window.visible

  // The payload may name the view to land on: `{"view":"apps"}` opens straight
  // on the picker. The launcher entry passes `{}` and gets the glance, which is
  // the right landing for somebody who opened the application rather than
  // followed a link into one of its rooms.
  function open(payloadJson) {
    closingFromHost = false
    var asked = ""
    try {
      var payload = JSON.parse(payloadJson || "{}")
      if (payload && payload.view) asked = String(payload.view)
    } catch (e) { /* an unreadable payload is not a reason to refuse to open */ }
    if (asked === "glance" || asked === "apps" || asked === "schedule")
      root.view = asked
    window.visible = true
    root.reload()
    // Only where there is something to type into. Landing on the glance and
    // stealing the keyboard for a field that is not on screen is how a window
    // eats the first thing somebody types.
    if (root.view === "apps")
      Qt.callLater(function() { filterField.forceActiveFocus() })
  }

  function close() {
    closingFromHost = true
    window.visible = false
    closingFromHost = false
  }

  function requestClose() {
    if (shell && typeof shell.hide === "function") shell.hide("danitrrga.nightguard")
    else window.visible = false
  }

  // ---- theme ---------------------------------------------------------------
  readonly property color foreground: Color.foreground
  readonly property color background: Color.background
  readonly property color urgent: Color.urgent
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property color track: Style.selectedFillFor(foreground, Color.accent)
  readonly property string fontFamily: Style.font.family

  function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

  // ---- data ----------------------------------------------------------------
  property var items: []
  property var detail: null
  property string catalogError: ""
  property string filter: ""

  // Three views, one window. The roster and the clock are different questions —
  // "what dies tonight" and "when is tonight" — and putting them in one scroll
  // made the clock look like a footnote to the app list. A rail rather than
  // tabs because the rail can carry counts, and a count is the fastest way to
  // see that a list is empty when it should not be.
  //
  // It lands on the glance and not on the roster. Opening straight into a
  // hundred-row picker answers a question nobody asked yet; the first thing
  // somebody opening this wants to know is whether they are in curfew and
  // whether they may change anything at this hour.
  property string view: "glance"

  readonly property var blocking: detail && detail.blocking ? detail.blocking : null
  readonly property string signedMode: !!blocking && String(blocking.mode) === "allowlist"
    ? "allowlist" : "blocklist"

  // The mode a click WOULD put us in. Everything downstream reads this and not
  // the signed one, because a staged mode change has to take effect on screen
  // the instant it is staged: the whole point of the switch is to SEE what the
  // other mode would mean before paying for it.
  readonly property string mode: String(writer.stagedValue("blocking.native_apps.mode", root.signedMode))
  readonly property bool allowlistMode: root.mode === "allowlist"
  readonly property bool modeStaged: root.mode !== root.signedMode

  // Which list the mode enforces. Adding to it is the ordinary act in both
  // modes -- what changes is the DIRECTION, and the cost line says so because
  // the signer said so.
  readonly property string governingKey: allowlistMode
    ? "blocking.native_apps.allowlist" : "blocking.native_apps.blacklist"
  readonly property string governingList: allowlistMode ? "allowlist" : "blacklist"

  // How many programs this machine would actually end tonight under the mode
  // currently on screen. The signer can say "tightens"; it cannot say "and that
  // is a hundred and eighty more deaths", and that number is the entire reason
  // this switch needs a warning at all. Only the catalog knows it.
  readonly property int survivorCount: root.listedRows.length
  readonly property int casualtyCount: Math.max(0, root.items.length - root.listedRows.length)

  // Switching view is not only a visibility flip: the roster view has a filter
  // field that is useless unless it has the keyboard, and the glance has none
  // to give it to.
  function showView(name) {
    root.view = name
    if (name === "apps") Qt.callLater(function() { filterField.forceActiveFocus() })
  }

  function reload() {
    if (!appsProc.running) appsProc.running = true
    if (!detailProc.running) detailProc.running = true
  }

  Process {
    id: appsProc
    command: [writer.ngtuiPath, "apps"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var parsed = null
        try {
          parsed = JSON.parse(text || "")
        } catch (e) {
          root.catalogError = "No se pudo leer el catálogo de aplicaciones."
          return
        }
        root.items = parsed && parsed.items ? parsed.items : []
        root.catalogError = parsed && parsed.error ? String(parsed.error) : ""
      }
    }
  }

  Process {
    id: detailProc
    command: [writer.ngtuiPath, "panel"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          root.detail = JSON.parse(text || "")
        } catch (e) { /* the last good reading stands */ }
      }
    }
  }

  // Re-read after every signed change: the lists, the token count and what is
  // already on them must come back from the config that was signed, never from
  // what this window believed it asked for.
  NightguardWriter {
    id: writer
    tokensTotal: root.detail ? Number(root.detail.tokens_total) : 3
    onCommitted: root.reload()
  }

  // ---- the shape of one row ------------------------------------------------

  // How much is known about this candidate, in one word plus a colour. Never
  // green unless the process was actually read: a tick on something that has
  // never been seen running is the promise this whole surface exists to stop
  // making.
  function confidenceWord(c) {
    switch (String(c)) {
    case "verified": return "verificada"
    case "path":     return "por ruta"
    case "probable": return "probable"
    case "site":     return "es un sitio"
    default:         return "desconocida"
    }
  }

  // The verdict column is measured, not a percentage. A percentage narrows with
  // the window and the first casualty is the word itself: "verifica…" is worse
  // than no verdict at all, because it looks like a verdict and is not one.
  // Every other column can elide -- a truncated name is still recognisable, a
  // truncated one-word judgement is not.
  TextMetrics {
    id: confidenceMetrics
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
    text: "desconocida"
  }

  function confidenceColor(c) {
    switch (String(c)) {
    case "verified": return Color.accent
    case "path":     return Color.accent
    case "probable": return root.dim
    case "site":     return root.urgent
    default:         return root.urgent
    }
  }

  function groupTitle(g) {
    switch (String(g)) {
    case "running":   return "CORRIENDO AHORA · IDENTIDAD LEÍDA"
    case "games":     return "TUS JUEGOS · CASAN POR RUTA"
    case "installed": return "INSTALADAS · SIN COMPROBAR"
    case "listed":    return "EN TU LISTA · SIN RESOLVER"
    case "webapps":   return "NO SON APLICACIONES · SON SITIOS"
    default:          return String(g).toUpperCase()
    }
  }

  function groupNote(g) {
    switch (String(g)) {
    case "webapps":
      return "Todas arrancan como el mismo navegador. Bloquear una como aplicación mataría el navegador entero y las demás con él, así que su identidad es la dirección y van a la lista de sitios."
    case "listed":
      return "Están en tu configuración pero nada en esta máquina responde a ese nombre. Ese medio pacto no se está cumpliendo."
    default:
      return ""
    }
  }

  // The filter reads both names, because the user may remember either one.
  function matchesFilter(item) {
    if (root.filter === "") return true
    var needle = root.filter.toLowerCase()
    return String(item.name).toLowerCase().indexOf(needle) !== -1
        || String(item.identity).toLowerCase().indexOf(needle) !== -1
        || String(item.url || "").toLowerCase().indexOf(needle) !== -1
  }

  // The left column, flattened into rows with group headers interleaved. One
  // model rather than five Repeaters so an empty group takes no space and the
  // headers stay in the same scroll as what they head.
  readonly property var catalogRows: {
    var order = ["running", "games", "installed", "listed", "webapps"]
    var rows = []
    for (var g = 0; g < order.length; g++) {
      var group = order[g]
      var inGroup = []
      for (var i = 0; i < root.items.length; i++) {
        var item = root.items[i]
        if (item.group !== group) continue
        if (!root.matchesFilter(item)) continue
        inGroup.push(item)
      }
      if (inGroup.length === 0) continue
      rows.push({ header: true, group: group })
      for (var k = 0; k < inGroup.length; k++)
        rows.push({ header: false, item: inGroup[k] })
    }
    return rows
  }

  // The right column: what the mode currently enforces, read from the payload
  // rather than recomputed here, plus whatever is staged on top.
  readonly property var listedRows: {
    var rows = []
    // `entries` carries the resolution, but only for the list the SIGNED mode
    // governs. Once a mode change is staged the governing list is the other
    // one, and nobody asked this machine what it resolves to -- so those rows
    // render as plain names. An unread state must never be drawn as a state.
    var entries = root.modeStaged
      ? (root.blocking && root.blocking[root.governingList] ? root.blocking[root.governingList] : [])
      : (root.blocking && root.blocking.entries ? root.blocking.entries : [])
    for (var i = 0; i < entries.length; i++) {
      var entry = entries[i]
      var name = String(root.modeStaged ? entry : entry.name)
      if (writer.staged(root.governingKey, "remove", name)) continue
      rows.push({
        name: name,
        label: root.modeStaged ? null : entry.label,
        state: root.modeStaged ? null : entry.state,
        pending: false,
      })
    }
    for (var k = 0; k < writer.ops.length; k++) {
      var op = writer.ops[k]
      if (op.key === root.governingKey && op.action === "add")
        rows.push({ name: String(op.value), label: null, state: null, pending: true })
    }
    return rows
  }

  readonly property var siteRows: {
    var rows = []
    var sites = root.blocking && root.blocking.site_entries ? root.blocking.site_entries : []
    for (var i = 0; i < sites.length; i++) {
      if (writer.staged("blocking.browser_extension.blocked_urls", "remove", String(sites[i]))) continue
      rows.push({ name: String(sites[i]), pending: false })
    }
    for (var k = 0; k < writer.ops.length; k++) {
      var op = writer.ops[k]
      if (op.key === "blocking.browser_extension.blocked_urls" && op.action === "add")
        rows.push({ name: String(op.value), pending: true })
    }
    return rows
  }

  readonly property string modeConsequence: {
    if (!root.blocking) return ""
    var survivors = root.survivorCount
    var casualties = root.casualtyCount
    if (root.allowlistMode) {
      var head = root.modeStaged ? "Si aplicas esto: sólo " : "Sólo "
      return head + "sobreviven estas " + survivors
           + (survivors === 1 ? " aplicación. Todo lo demás muere — unas "
                              : " aplicaciones. Todo lo demás muere — unas ")
           + casualties + " de las que tienes, tus terminales incluidas si no están en la lista."
    }
    if (root.modeStaged)
      return "Si aplicas esto: sólo mueren estas " + survivors
           + (survivors === 1 ? " aplicación." : " aplicaciones.")
           + " Las otras " + casualties + " se salvan."
    return "Mueren sólo las de esta lista."
  }

  // --- the schedule -----------------------------------------------------
  //
  // Every reader below answers with the value the config WOULD have once
  // applied, not the value on disk. A field that snapped back to the signed
  // value while the change sat in the pending list would read as the edit
  // having failed.
  readonly property var curfew: root.detail && root.detail.curfew ? root.detail.curfew : null

  // The two defence switches used to default to ON when nothing was staged,
  // because the payload carried no reading of them. That drew a panel claiming
  // hand edits were being reverted on a machine where the watchdog was off --
  // a true-looking picture of a protection that is not running. They now read
  // the signed config, and refuse to be touched until that reading has arrived.
  readonly property var defences: root.detail && root.detail.defences
    ? root.detail.defences : null
  readonly property bool defencesRead: !!defences
  readonly property var editWindow: root.detail && root.detail.edit_window
    ? root.detail.edit_window : null

  function stagedBool(key, fallback) {
    return writer.stagedValue(key, fallback) === true
  }

  function stagedText(key, fallback) {
    var v = writer.stagedValue(key, fallback)
    return v === undefined || v === null ? "" : String(v)
  }

  // "HH:MM" to minutes past midnight, or -1. The ring beside these fields
  // reads the STAGED value, so typing a new hour moves the arc before anything
  // is signed -- which is the whole point of staging a curfew you cannot see.
  function hhmmToMinutes(text) {
    var m = /^([01]?\d|2[0-3]):([0-5]\d)$/.exec(String(text).trim())
    return m ? Number(m[1]) * 60 + Number(m[2]) : -1
  }

  readonly property bool curfewOn: root.stagedBool("curfew.enabled",
                                                   !!root.curfew && root.curfew.enabled === true)
  readonly property bool gateOn: root.stagedBool("edit_window.enabled",
                                                 !!root.editWindow && root.editWindow.enabled === true)
  readonly property int stagedCurfewStart: curfewOn
    ? hhmmToMinutes(root.stagedText("curfew.start", root.curfew ? root.curfew.start : "")) : -1
  readonly property int stagedCurfewEnd: curfewOn
    ? hhmmToMinutes(root.stagedText("curfew.end", root.curfew ? root.curfew.end : "")) : -1
  readonly property int stagedGateStart: gateOn
    ? hhmmToMinutes(root.stagedText("edit_window.start", root.editWindow ? root.editWindow.start : "")) : -1
  readonly property int stagedGateEnd: gateOn
    ? hhmmToMinutes(root.stagedText("edit_window.end", root.editWindow ? root.editWindow.end : "")) : -1

  function setTime(key, value, label) {
    var text = String(value).trim()
    // Refused here as well as in the CLI, because the CLI's refusal arrives as
    // a red line under a field the user has already left. The signer reads an
    // unparseable time as "no window", so a malformed edit window does not
    // fail — it silently stops gating.
    if (!/^([01]?\d|2[0-3]):[0-5]\d$/.test(text)) return false
    var parts = text.split(":")
    var normalised = (parts[0].length === 1 ? "0" : "") + parts[0] + ":" + parts[1]
    writer.stage(key, "set", normalised, label + " " + normalised)
    return true
  }

  function isListed(identity) {
    for (var i = 0; i < root.listedRows.length; i++)
      if (root.listedRows[i].name === identity) return true
    return false
  }

  function isSiteListed(host) {
    for (var i = 0; i < root.siteRows.length; i++)
      if (root.siteRows[i].name === host) return true
    return false
  }

  // The host a webapp blocks under. The browser policy blocks by host, so the
  // address shown is not the string written.
  function siteHost(url) {
    var text = String(url || "").trim()
    var lower = text.toLowerCase()
    if (lower.indexOf("https://") === 0) text = text.substring(8)
    else if (lower.indexOf("http://") === 0) text = text.substring(7)
    else return ""
    var host = text.split("/")[0].split("?")[0].split("#")[0]
    if (host.indexOf("@") !== -1) host = host.substring(host.lastIndexOf("@") + 1)
    host = host.split(":")[0].toLowerCase()
    if (host === "" || host.indexOf(".") === -1) return ""
    return host
  }

  // --- acting on a row ------------------------------------------------------

  function toggleApp(item) {
    var identity = String(item.identity)
    if (identity === "") return
    if (root.isListed(identity))
      writer.stage(root.governingKey, "remove", identity,
                   "Quitar " + identity + " de " + (root.allowlistMode ? "las permitidas" : "la lista"))
    else
      writer.stage(root.governingKey, "add", identity,
                   "Añadir " + identity + " a " + (root.allowlistMode ? "las permitidas" : "la lista"))
  }

  function toggleSite(host) {
    if (host === "") return
    if (root.isSiteListed(host))
      writer.stage("blocking.browser_extension.blocked_urls", "remove", host,
                   "Quitar " + host + " de los sitios")
    else
      writer.stage("blocking.browser_extension.blocked_urls", "add", host,
                   "Bloquear " + host)
  }

  // One of the two modes, as a thing you press. Not a dropdown: there are
  // exactly two and they are opposites, so both belong on screen at once with
  // the live one visibly holding.
  component ModeChip: Rectangle {
    id: modeChip
    property string label: ""
    property string value: ""
    readonly property bool on: root.mode === modeChip.value
    signal picked()

    implicitWidth: chipLabel.implicitWidth + Style.space(20)
    implicitHeight: chipLabel.implicitHeight + Style.space(12)
    radius: Style.cornerRadius
    color: modeChip.on ? Style.selectedFillFor(root.foreground, Color.accent)
                       : (chipMouse.containsMouse
                          ? Style.normalFillFor(root.foreground, Color.accent)
                          : "transparent")
    border.width: Style.normalBorderWidth
    border.color: modeChip.on ? Color.accent
                              : Style.normalBorderFor(root.foreground, Color.accent)

    MouseArea {
      id: chipMouse
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: Qt.PointingHandCursor
      onClicked: modeChip.picked()
    }

    Text {
      id: chipLabel
      textFormat: Text.PlainText
      anchors.centerIn: parent
      text: modeChip.label
      color: modeChip.on ? root.foreground : root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
    }
  }

  // One editable line of the schedule: a label, the thing you change, and a
  // sentence saying what it means. The sentence is not decoration — "05:30" is
  // not a fact anybody can act on until something says it is when the door
  // opens.
  component FieldRow: Rectangle {
    id: fieldRow
    property string label: ""
    property string note: ""
    property bool staged: false
    default property alias control: controlSlot.data

    implicitHeight: Math.max(fieldCol.implicitHeight, Style.space(34)) + Style.space(14)
    radius: Style.cornerRadius
    color: Style.normalFillFor(root.foreground, Color.accent)
    border.width: Style.normalBorderWidth
    border.color: fieldRow.staged ? Color.accent
                                  : Style.normalBorderFor(root.foreground, Color.accent)

    Column {
      id: fieldCol
      x: Style.spacing.rowPaddingX
      y: Style.space(7)
      width: parent.width - Style.spacing.rowPaddingX * 2 - controlSlot.width - Style.space(12)
      spacing: Style.space(2)

      Text {
        textFormat: Text.PlainText
        width: parent.width
        text: fieldRow.label
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
        elide: Text.ElideRight
      }
      Text {
        textFormat: Text.PlainText
        width: parent.width
        visible: fieldRow.note !== ""
        text: fieldRow.note
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        wrapMode: Text.WordWrap
      }
    }

    Item {
      id: controlSlot
      anchors.right: parent.right
      anchors.rightMargin: Style.spacing.rowPaddingX
      anchors.verticalCenter: parent.verticalCenter
      implicitWidth: childrenRect.width
      implicitHeight: childrenRect.height
      width: implicitWidth
      height: implicitHeight
    }
  }

  component CatalogRow: Rectangle {
    id: catalogRow
    property var item: null
    readonly property bool isSite: !!item && String(item.confidence) === "site"
    readonly property string host: catalogRow.isSite ? root.siteHost(item.url) : ""
    readonly property bool on: catalogRow.isSite
      ? (catalogRow.host !== "" && root.isSiteListed(catalogRow.host))
      : (!!item && root.isListed(String(item.identity)))
    readonly property bool actionable: catalogRow.isSite ? catalogRow.host !== "" : true
    // A game's executable IS its title, so the row was printing one string
    // twice and truncating both halves to do it. When they are the same, the
    // name takes the whole width and the second column is not drawn.
    readonly property bool namesDiffer: !!item
      && String(item.identity) !== String(item.name)

    implicitHeight: rowText.implicitHeight + Style.space(14)
    radius: Style.cornerRadius
    color: catalogRow.on ? Style.selectedFillFor(root.foreground, Color.accent)
                         : (rowMouse.containsMouse ? Style.normalFillFor(root.foreground, Color.accent)
                                                   : "transparent")
    border.width: catalogRow.on ? Style.normalBorderWidth : 0
    border.color: Style.normalBorderFor(root.foreground, Color.accent)

    MouseArea {
      id: rowMouse
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: catalogRow.actionable ? Qt.PointingHandCursor : Qt.ArrowCursor
      onClicked: {
        if (!catalogRow.actionable) return
        if (catalogRow.isSite) root.toggleSite(catalogRow.host)
        else root.toggleApp(catalogRow.item)
      }
    }

    Row {
      id: rowText
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.leftMargin: Style.spacing.rowPaddingX
      anchors.rightMargin: Style.spacing.rowPaddingX
      anchors.verticalCenter: parent.verticalCenter
      spacing: Style.space(8)

      readonly property real verdictWidth: confidenceMetrics.width + Style.space(2)
      readonly property real namesWidth: Math.max(0, rowText.width - verdictWidth - Style.space(16))

      Text {
        textFormat: Text.PlainText
        width: catalogRow.namesDiffer || catalogRow.isSite
               ? rowText.namesWidth * 0.5 : rowText.namesWidth
        text: catalogRow.on ? "✓ " + String(catalogRow.item.name) : String(catalogRow.item.name)
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
        elide: Text.ElideRight
      }

      // The executable, or the address for a site. This is the string the
      // watchdog or the browser policy actually acts on, and it is on screen
      // for every row on purpose -- the pretty name alone is what let a webapp
      // sit on a kill list for months doing nothing.
      Text {
        textFormat: Text.PlainText
        visible: catalogRow.namesDiffer || catalogRow.isSite
        width: visible ? rowText.namesWidth * 0.5 : 0
        text: catalogRow.isSite ? (catalogRow.host !== "" ? catalogRow.host : String(catalogRow.item.url))
                                : String(catalogRow.item.identity)
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        // Right, not left. These are basenames, not paths: the distinguishing
        // part of "BlackmagicRAWSpeedTest" is the front, and eliding from the
        // left hid exactly the half that tells two of them apart.
        elide: Text.ElideRight
      }

      Text {
        textFormat: Text.PlainText
        width: rowText.verdictWidth
        horizontalAlignment: Text.AlignRight
        text: root.confidenceWord(catalogRow.item.confidence)
        color: root.confidenceColor(catalogRow.item.confidence)
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        elide: Text.ElideRight
      }
    }
  }

  component ListedRow: Rectangle {
    id: listedRow
    property string name: ""
    property string label: ""
    property string state: ""
    property bool pending: false
    signal removeRequested()

    readonly property bool broken: listedRow.state === "unmatched"

    implicitHeight: listedLabel.implicitHeight + Style.space(14)
    radius: Style.cornerRadius
    color: listedRow.broken ? root.alpha(root.urgent, 0.10)
                            : Style.normalFillFor(root.foreground, Color.accent)
    border.width: Style.normalBorderWidth
    border.color: listedRow.pending ? Color.accent
                                    : (listedRow.broken ? root.alpha(root.urgent, 0.45)
                                                        : Style.normalBorderFor(root.foreground, Color.accent))

    Text {
      id: listedLabel
      textFormat: Text.PlainText
      anchors.left: parent.left
      anchors.leftMargin: Style.spacing.rowPaddingX
      anchors.verticalCenter: parent.verticalCenter
      text: (listedRow.pending ? "+ " : "") + (listedRow.label !== "" ? listedRow.label : listedRow.name)
      color: listedRow.pending ? Color.accent : root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.bodySmall
    }

    Text {
      textFormat: Text.PlainText
      anchors.right: removeButton.left
      anchors.rightMargin: Style.space(6)
      anchors.left: listedLabel.right
      anchors.leftMargin: Style.space(8)
      anchors.verticalCenter: parent.verticalCenter
      horizontalAlignment: Text.AlignRight
      text: listedRow.broken ? "no coincide con nada"
                             : (listedRow.label !== "" ? listedRow.name : "")
      color: listedRow.broken ? root.urgent : root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      elide: Text.ElideRight
    }

    PanelActionButton {
      id: removeButton
      anchors.right: parent.right
      anchors.rightMargin: Style.space(6)
      anchors.verticalCenter: parent.verticalCenter
      iconText: "󰅖"
      tooltipText: "Quitar de la lista"
      foreground: root.foreground
      fontFamily: root.fontFamily
      onClicked: listedRow.removeRequested()
    }
  }

  // ---- the window ----------------------------------------------------------

  FloatingWindow {
    id: window
    title: "Nightguard Control"
    color: root.background
    // Sized so the glance lands whole. The roster and the schedule both scroll
    // by nature -- a catalogue of a hundred always will -- but a landing screen
    // that opens already scrolled has hidden the one thing it exists to show.
    implicitWidth: 940
    implicitHeight: 820
    minimumSize: Qt.size(700, 520)

    onVisibleChanged: {
      if (!visible && !root.closingFromHost && root.shell && typeof root.shell.hide === "function")
        root.shell.hide("danitrrga.nightguard")
    }

    FocusScope {
      id: scope
      anchors.fill: parent
      focus: true

      // AfterItem so typing in the filter field still reaches it first; the
      // dialog's own handler owns every key while it is up, which is what makes
      // Escape reliably answer the QUESTION rather than reaching whichever
      // child happened to hold focus when it opened. `selectedIndex: 0` means
      // Enter CANCELS: the default answer to "do you want to weaken this?" is
      // no, so a reflex keypress never signs anything.
      //
      // It is not true that only a click can say yes -- the kit's dialog moves
      // the selection on Left/Right/Tab, so right-then-Enter confirms. This
      // comment claimed otherwise for a while. The dropdown (NightguardPanel)
      // genuinely has no keyboard path; the window has a deliberate two-key
      // one. Nobody reflexively presses two keys, which is the friction that
      // was wanted, but say what is true.
      Keys.priority: Keys.AfterItem
      Keys.onPressed: function(event) {
        if (confirmApply.opened) {
          if (confirmApply.handleKey(event)) event.accepted = true
          return
        }
        if (event.key === Qt.Key_Escape) {
          root.requestClose()
          event.accepted = true
        }
      }

      // Capped and centred. A tiling compositor will hand this window whatever
      // width the workspace has, and three columns spread across 1900px stop
      // being a row and become three unrelated things. The cap is the same
      // reason running text gets a measure.
      Item {
        id: layout
        anchors.fill: parent
        anchors.margins: Style.space(16)

        readonly property real contentWidth: Math.min(width, Style.space(1040))
        readonly property real contentX: (width - contentWidth) / 2

        Column {
          id: headerBlock
          x: layout.contentX
          width: layout.contentWidth
          anchors.top: parent.top
          spacing: Style.space(12)

        PanelHero {
          width: parent.width
          title: "Nightguard"
          meta: {
            switch (root.view) {
            case "glance":   return "LO QUE ESTÁ FIRMADO AHORA MISMO"
            case "schedule": return "LAS HORAS Y LAS DEFENSAS"
            default:         return root.allowlistMode ? "SOLO SOBREVIVEN LAS PERMITIDAS"
                                                       : "MUEREN LAS DE LA LISTA"
            }
          }
          foreground: root.foreground
          fontFamily: root.fontFamily

          iconComponent: Component {
            Text {
              textFormat: Text.PlainText
              text: "󰌾"
              color: Color.accent
              font.family: root.fontFamily
              font.pixelSize: Style.font.display
            }
          }

          trailingControl: Component {
            Row {
              // The glance carries these with a sentence beside them. Two
              // copies of the same three marks on one screen reads as two
              // different counts.
              visible: root.view !== "glance"
              spacing: Style.space(4)
              Repeater {
                model: root.detail ? Number(root.detail.tokens_total) : 0
                Rectangle {
                  required property int index
                  width: Style.space(22)
                  height: Style.space(6)
                  anchors.verticalCenter: parent.verticalCenter
                  radius: Style.cornerRadius > 0 ? height / 2 : 0
                  color: index < (root.detail ? Number(root.detail.tokens_left) : 0)
                         ? Color.accent : root.track
                }
              }
            }
          }
        }

          PanelSeparator { width: parent.width; foreground: root.foreground }
        }

        Item {
          id: middle
          x: layout.contentX
          width: layout.contentWidth
          anchors.top: headerBlock.bottom
          anchors.topMargin: Style.space(12)
          anchors.bottom: footerBlock.top
          anchors.bottomMargin: Style.space(12)

          // --- the rail ----------------------------------------------------
          Column {
            id: rail
            width: Style.space(150)
            height: parent.height
            spacing: Style.spacing.xs

            Repeater {
              model: [
                { id: "glance",   label: "El vistazo", count: -1 },
                { id: "apps",     label: "Qué muere",  count: root.listedRows.length + root.siteRows.length },
                { id: "schedule", label: "El horario", count: -1 },
              ]

              Rectangle {
                required property var modelData
                readonly property bool on: root.view === modelData.id
                width: rail.width
                implicitHeight: railLabel.implicitHeight + Style.space(14)
                radius: Style.cornerRadius
                color: on ? Style.selectedFillFor(root.foreground, Color.accent)
                          : (railMouse.containsMouse
                             ? Style.normalFillFor(root.foreground, Color.accent)
                             : "transparent")

                MouseArea {
                  id: railMouse
                  anchors.fill: parent
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.showView(parent.modelData.id)
                }

                Text {
                  id: railLabel
                  textFormat: Text.PlainText
                  anchors.left: parent.left
                  anchors.leftMargin: Style.spacing.rowPaddingX
                  anchors.verticalCenter: parent.verticalCenter
                  text: parent.modelData.label
                  color: parent.on ? root.foreground : root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                }

                Text {
                  textFormat: Text.PlainText
                  anchors.right: parent.right
                  anchors.rightMargin: Style.spacing.rowPaddingX
                  anchors.verticalCenter: parent.verticalCenter
                  visible: parent.modelData.count >= 0
                  text: String(parent.modelData.count)
                  color: root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                }
              }
            }
          }

          // --- the glance --------------------------------------------------
          NightguardGlance {
            visible: root.view === "glance"
            x: rail.width + Style.space(20)
            width: parent.width - rail.width - Style.space(20)
            height: parent.height
            detail: root.detail
            mode: root.mode
            pendingCount: writer.count
            foregroundColor: root.foreground
            dimColor: root.dim
            trackColor: root.track
            urgentColor: root.urgent
            voidColor: root.background
            fontFamily: root.fontFamily
            onGoToApps: root.showView("apps")
            onGoToSchedule: root.showView("schedule")
          }

          // --- the schedule ------------------------------------------------
          //
          // The fields on the left, the day they describe on the right. Four
          // times in four boxes are not a schedule until something shows them
          // as one shape -- and the ring answers the question the boxes cannot:
          // whether the hours you may weaken the pact fall inside the hours it
          // is enforced. It reads the staged values, so the arc moves as you
          // type, before anything is signed.
          readonly property real scheduleSpace: width - rail.width - Style.space(20)
          readonly property bool scheduleWide: scheduleSpace > Style.space(500)
          readonly property real schedulePreview: scheduleWide ? Style.space(180) : 0

          Item {
            id: schedulePreviewPane
            visible: root.view === "schedule" && middle.scheduleWide
            anchors.right: parent.right
            anchors.top: parent.top
            width: middle.schedulePreview
            height: previewColumn.implicitHeight

            Column {
              id: previewColumn
              width: parent.width
              spacing: Style.space(8)

              DayDial {
                width: parent.width
                height: width
                curfewStart: root.stagedCurfewStart
                curfewEnd: root.stagedCurfewEnd
                windowStart: root.stagedGateStart
                windowEnd: root.stagedGateEnd
                nowMinutes: -1
                headline: root.curfewOn ? "el día" : "sin curfew"
                caption: writer.count > 0 ? "como quedaría" : "como está"
                headlineColor: root.foreground
                foregroundColor: root.foreground
                dimColor: root.dim
                trackColor: root.track
                curfewColor: root.urgent
                fontFamily: root.fontFamily
                voidColor: root.background
                headlineSize: Style.font.title
              }

              Text {
                width: parent.width
                textFormat: Text.PlainText
                visible: !root.gateOn
                text: "Sin puerta: se puede aflojar a cualquier hora, incluida esta noche."
                color: root.urgent
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                wrapMode: Text.WordWrap
              }
            }
          }

          Flickable {
            visible: root.view === "schedule"
            x: rail.width + Style.space(20)
            width: middle.scheduleSpace - middle.schedulePreview
                   - (middle.scheduleWide ? Style.space(20) : 0)
            height: parent.height
            contentWidth: width
            contentHeight: scheduleColumn.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            Column {
              id: scheduleColumn
              width: parent.width
              spacing: Style.space(8)

              PanelSectionHeader {
                width: parent.width
                text: "EL CURFEW"
                foreground: root.foreground
                fontFamily: root.fontFamily
              }

              FieldRow {
                width: parent.width
                label: "Curfew activo"
                // A note only on the state that costs something. "Curfew
                // activo / la casa se cierra todas las noches" says one thing
                // twice.
                note: root.stagedBool("curfew.enabled", !!root.curfew && root.curfew.enabled === true)
                      ? "" : "No se cierra nada, a ninguna hora."
                staged: writer.staged("curfew.enabled", "set", true)
                        || writer.staged("curfew.enabled", "set", false)
                ToggleSwitch {
                  checked: root.stagedBool("curfew.enabled",
                                           !!root.curfew && root.curfew.enabled === true)
                  foreground: root.foreground
                  onToggled: writer.stage("curfew.enabled", "set", !checked,
                                          checked ? "Apagar el curfew" : "Encender el curfew")
                }
              }

              FieldRow {
                width: parent.width
                label: "Se cierra a las"
                staged: root.stagedText("curfew.start", "") !== ""
                        && writer.stagedValue("curfew.start", null) !== null
                TextField {
                  width: Style.space(90)
                  text: root.stagedText("curfew.start", root.curfew ? root.curfew.start : "")
                  foreground: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  horizontalAlignment: Text.AlignHCenter
                  onEditingFinished: root.setTime("curfew.start", text, "Cerrar a las")
                }
              }

              FieldRow {
                width: parent.width
                label: "Se abre a las"
                TextField {
                  width: Style.space(90)
                  text: root.stagedText("curfew.end", root.curfew ? root.curfew.end : "")
                  foreground: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  horizontalAlignment: Text.AlignHCenter
                  onEditingFinished: root.setTime("curfew.end", text, "Abrir a las")
                }
              }

              PanelSectionHeader {
                width: parent.width
                text: "CUÁNDO PUEDES DEBILITARLO"
                foreground: root.foreground
                fontFamily: root.fontFamily
              }

              Text {
                textFormat: Text.PlainText
                width: parent.width
                text: "Fuera de estas horas, aflojar el pacto se rechaza antes de mirar las fichas."
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                wrapMode: Text.WordWrap
              }

              FieldRow {
                width: parent.width
                label: "Puerta activa"
                note: root.stagedBool("edit_window.enabled",
                                      !!root.editWindow && root.editWindow.enabled === true)
                      ? "" : "Se puede aflojar a cualquier hora — sólo cuesta ficha."
                ToggleSwitch {
                  checked: root.stagedBool("edit_window.enabled",
                                           !!root.editWindow && root.editWindow.enabled === true)
                  foreground: root.foreground
                  onToggled: writer.stage("edit_window.enabled", "set", !checked,
                                          checked ? "Quitar la puerta de edición"
                                                  : "Poner la puerta de edición")
                }
              }

              FieldRow {
                width: parent.width
                label: "Abre a las"
                TextField {
                  width: Style.space(90)
                  text: root.stagedText("edit_window.start",
                                        root.editWindow ? root.editWindow.start : "")
                  foreground: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  horizontalAlignment: Text.AlignHCenter
                  onEditingFinished: root.setTime("edit_window.start", text, "Puerta abre a las")
                }
              }

              FieldRow {
                width: parent.width
                label: "Cierra a las"
                TextField {
                  width: Style.space(90)
                  text: root.stagedText("edit_window.end",
                                        root.editWindow ? root.editWindow.end : "")
                  foreground: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  horizontalAlignment: Text.AlignHCenter
                  onEditingFinished: root.setTime("edit_window.end", text, "Puerta cierra a las")
                }
              }

              PanelSectionHeader {
                width: parent.width
                text: "LAS DEFENSAS"
                foreground: root.foreground
                fontFamily: root.fontFamily
              }

              FieldRow {
                width: parent.width
                label: "Comprobar el reloj"
                note: root.stagedBool("clock_protection.enabled",
                                      !!root.defences
                                      && root.defences.clock_protection.enabled === true)
                      ? "" : "Mover la hora del sistema abriría la noche."
                ToggleSwitch {
                  checked: root.stagedBool("clock_protection.enabled",
                                           !!root.defences
                                           && root.defences.clock_protection.enabled === true)
                  enabled: root.defencesRead
                  opacity: root.defencesRead ? 1 : 0.45
                  foreground: root.foreground
                  onToggled: writer.stage("clock_protection.enabled", "set", !checked,
                                          checked ? "Dejar de comprobar el reloj"
                                                  : "Comprobar el reloj")
                }
              }

              FieldRow {
                width: parent.width
                label: "Vigilante activo"
                note: root.stagedBool("watchdog.enabled",
                                      !!root.defences
                                      && root.defences.watchdog.enabled === true)
                      ? "" : "Una edición a mano de la configuración se queda."
                ToggleSwitch {
                  checked: root.stagedBool("watchdog.enabled",
                                           !!root.defences
                                           && root.defences.watchdog.enabled === true)
                  enabled: root.defencesRead
                  opacity: root.defencesRead ? 1 : 0.45
                  foreground: root.foreground
                  onToggled: writer.stage("watchdog.enabled", "set", !checked,
                                          checked ? "Parar el vigilante" : "Arrancar el vigilante")
                }
              }

              FieldRow {
                width: parent.width
                label: "Bloqueo de aplicaciones"
                note: root.stagedBool("blocking.native_apps.enabled",
                                      !!root.blocking && root.blocking.apps_enabled === true)
                      ? "" : "No se cierra ninguna aplicación, esté en la lista o no."
                ToggleSwitch {
                  checked: root.stagedBool("blocking.native_apps.enabled",
                                           !!root.blocking && root.blocking.apps_enabled === true)
                  foreground: root.foreground
                  onToggled: writer.stage("blocking.native_apps.enabled", "set", !checked,
                                          checked ? "Apagar el bloqueo de aplicaciones"
                                                  : "Encender el bloqueo de aplicaciones")
                }
              }
            }
          }

          // The two columns of the picker. The right one holds fixed-shape
          // rows -- a name, a verdict and a remove button -- so it gets a floor
          // and the catalogue takes what is left. A straight percentage split
          // crushed it first on a tiled window, which is most of them.
          readonly property real pickerSpace: width - rail.width - Style.space(32)
          readonly property real pickerRight: Math.min(pickerSpace * 0.5,
                                                       Math.max(Style.space(280),
                                                                pickerSpace * 0.44))
          readonly property real pickerLeft: pickerSpace - pickerRight

          // --- left: the catalog -------------------------------------------
          Column {
            id: leftColumn
            visible: root.view === "apps"
            x: rail.width + Style.space(20)
            width: middle.pickerLeft
            height: parent.height
            spacing: Style.space(8)

            Row {
              width: parent.width
              spacing: Style.space(8)

              PanelSectionHeader {
                width: parent.width - countLabel.implicitWidth - Style.space(8)
                text: "CATÁLOGO"
                foreground: root.foreground
                fontFamily: root.fontFamily
              }
              Text {
                id: countLabel
                textFormat: Text.PlainText
                anchors.verticalCenter: parent.verticalCenter
                text: root.items.length + " encontradas"
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
              }
            }

            TextField {
              id: filterField
              width: parent.width
              placeholderText: "filtrar por nombre o por ejecutable…"
              foreground: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              onTextChanged: root.filter = text.trim()
            }

            Flickable {
              width: parent.width
              height: parent.height - y
              contentWidth: width
              contentHeight: catalogColumn.implicitHeight
              clip: true
              boundsBehavior: Flickable.StopAtBounds
              ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

              Column {
                id: catalogColumn
                width: parent.width
                spacing: Style.spacing.xs

                Repeater {
                  model: root.catalogRows

                  Loader {
                    required property var modelData
                    width: catalogColumn.width
                    sourceComponent: modelData.header ? headerPiece : rowPiece

                    Component {
                      id: headerPiece
                      Column {
                        spacing: Style.space(2)
                        topPadding: Style.space(8)

                        PanelSectionHeader {
                          width: catalogColumn.width
                          text: root.groupTitle(modelData.group)
                          foreground: root.foreground
                          fontFamily: root.fontFamily
                        }
                        Text {
                          textFormat: Text.PlainText
                          width: catalogColumn.width
                          visible: text !== ""
                          text: root.groupNote(modelData.group)
                          color: root.urgent
                          font.family: root.fontFamily
                          font.pixelSize: Style.font.caption
                          wrapMode: Text.WordWrap
                        }
                      }
                    }

                    Component {
                      id: rowPiece
                      CatalogRow {
                        width: catalogColumn.width
                        item: modelData.item
                      }
                    }
                  }
                }

                Text {
                  textFormat: Text.PlainText
                  width: parent.width
                  visible: root.catalogRows.length === 0
                  text: root.catalogError !== "" ? root.catalogError
                        : (root.filter !== "" ? "Nada coincide con «" + root.filter + "»."
                                              : "Leyendo el catálogo…")
                  color: root.catalogError !== "" ? root.urgent : root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  wrapMode: Text.WordWrap
                }
              }
            }
          }

          // --- right: the two lists ----------------------------------------
          Flickable {
            visible: root.view === "apps"
            anchors.right: parent.right
            width: middle.pickerRight
            height: parent.height
            contentWidth: width
            contentHeight: rightColumn.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            Column {
              id: rightColumn
              width: parent.width
              spacing: Style.space(8)

              PanelSectionHeader {
                width: parent.width
                text: root.allowlistMode ? "SOBREVIVEN ESTA NOCHE" : "MUEREN ESTA NOCHE"
                foreground: root.foreground
                fontFamily: root.fontFamily
              }

              // The two modes do not filter one list. They choose which of two
              // lists governs, and both keep existing whichever is picked --
              // nothing is deleted by switching. What DOES invert is the cost
              // of every future edit, and that is the part that must not be
              // learned by accident.
              Row {
                width: parent.width
                spacing: Style.space(6)

                ModeChip {
                  label: "Lista de bloqueo"
                  value: "blocklist"
                  onPicked: writer.stage("blocking.native_apps.mode", "set", "blocklist",
                                         "Cambiar a lista de bloqueo")
                }
                ModeChip {
                  label: "Sólo permitidas"
                  value: "allowlist"
                  onPicked: writer.stage("blocking.native_apps.mode", "set", "allowlist",
                                         "Cambiar a sólo permitidas")
                }
              }

              // What the mode on screen actually costs, in programs. The signer
              // can say "tightens"; it cannot say "and that is 93 more deaths",
              // because only the catalog knows how many things are installed.
              Text {
                textFormat: Text.PlainText
                width: parent.width
                text: root.modeConsequence
                color: root.modeStaged ? root.urgent : root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                wrapMode: Text.WordWrap
              }

              Repeater {
                model: root.listedRows

                ListedRow {
                  required property var modelData
                  width: rightColumn.width
                  name: String(modelData.name)
                  label: modelData.label ? String(modelData.label) : ""
                  state: modelData.state ? String(modelData.state) : ""
                  pending: modelData.pending === true
                  onRemoveRequested: {
                    if (pending) writer.stage(root.governingKey, "add", name, "")
                    else writer.stage(root.governingKey, "remove", name,
                                      "Quitar " + name + " de " + (root.allowlistMode ? "las permitidas" : "la lista"))
                  }
                }
              }

              Text {
                textFormat: Text.PlainText
                width: parent.width
                visible: root.listedRows.length === 0
                text: root.allowlistMode
                      ? "Ninguna permitida — en este modo no sobreviviría nada."
                      : "Ninguna aplicación en la lista — no hay nada que terminar."
                color: root.urgent
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                wrapMode: Text.WordWrap
              }

              PanelSectionHeader {
                width: parent.width
                text: "SITIOS BLOQUEADOS"
                foreground: root.foreground
                fontFamily: root.fontFamily
              }

              Repeater {
                model: root.siteRows

                ListedRow {
                  required property var modelData
                  width: rightColumn.width
                  name: String(modelData.name)
                  pending: modelData.pending === true
                  onRemoveRequested: {
                    if (pending) writer.stage("blocking.browser_extension.blocked_urls", "add", name, "")
                    else writer.stage("blocking.browser_extension.blocked_urls", "remove", name,
                                      "Quitar " + name + " de los sitios")
                  }
                }
              }

              Text {
                textFormat: Text.PlainText
                width: parent.width
                visible: root.siteRows.length === 0
                // Not urgent. Blocking no sites is a configuration somebody can
                // reasonably choose -- this machine blocks applications, not
                // addresses -- and painting a choice red is how a reader learns
                // to ignore red on the screen where it means something.
                text: "Ningún sitio bloqueado — la política del navegador no tiene nada que aplicar."
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                wrapMode: Text.WordWrap
              }
            }
          }
        }

        // --- what it costs, then what it does ------------------------------
        Column {
          id: footerBlock
          x: layout.contentX
          width: layout.contentWidth
          anchors.bottom: parent.bottom
          spacing: Style.space(8)

          PanelSeparator { width: parent.width; foreground: root.foreground }

          Text {
            textFormat: Text.PlainText
            width: parent.width
            visible: writer.count > 0 || writer.resultText !== ""
            text: writer.resultText !== "" ? writer.resultText : writer.costLine
            color: {
              if (writer.resultText !== "") {
                switch (writer.resultKind) {
                case "ok":      return Color.accent
                case "refused": return root.urgent
                case "error":   return root.urgent
                default:        return root.dim
                }
              }
              if (writer.refusalReason !== "") return root.urgent
              return writer.costsToken ? Color.accent : root.foreground
            }
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }

          Row {
            width: parent.width
            spacing: Style.space(8)

            Text {
              textFormat: Text.PlainText
              anchors.verticalCenter: parent.verticalCenter
              width: parent.width - applyButton.width - discardButton.width - Style.space(16)
              // Empty when nothing is staged. The buttons beside it are already
              // greyed out; a sentence telling somebody to use the rail they
              // can see is furniture.
              text: writer.count === 0 ? ""
                    : writer.count + (writer.count === 1 ? " cambio sin aplicar"
                                                         : " cambios sin aplicar")
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              elide: Text.ElideRight
            }

            Button {
              id: discardButton
              text: "Descartar"
              tooltipText: "Olvidar los cambios sin aplicar"
              bordered: true
              enabled: writer.count > 0
              opacity: writer.count > 0 ? 1 : 0.45
              foreground: root.foreground
              fontFamily: root.fontFamily
              fontSize: Style.font.caption
              onClicked: writer.discard()
            }

            Button {
              id: applyButton
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
          }
        }
      }

      // The gate between a click and an authentication dialog. It starts on
      // Cancel, because the default answer to "do you want to weaken this?" at
      // two in the morning is no, and nothing here confirms from the keyboard.
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
    }
  }
}
