import QtQuick
import qs.Commons

// The reading of the hours, in one place, for every surface that shows them.
//
// Headless on purpose: it draws nothing and owns no layout. It exists because
// the dropdown and the window both have to answer "how long until this
// changes?" and "may the pact be weakened right now?", and the first time those
// two sentences were written twice they immediately said it differently — one
// rounding to hours, one to minutes. A panel and a window disagreeing about
// when the curfew begins is worse than either being wrong, because the reader
// has no way to tell which one to believe.
//
// Every reader here is display-only. The signer decides; this puts words on
// what it decided. A disagreement shows a wrong hour, it never lets a change
// through.
Item {
  id: clock

  // The whole `ngtui panel` payload. Null while the first read is in flight.
  property var detail: null

  // The verdict to word. The dropdown gets this from its bar widget, which is
  // refreshed on a timer; the window reads it out of the payload.
  property string verdict: detail ? String(detail.verdict) : ""

  visible: false

  function minuteOr(value) {
    var n = Number(value)
    return isFinite(n) ? n : -1
  }

  readonly property int nowMinutes: minuteOr(detail ? detail.now_minutes : -1)
  readonly property int curfewStartMin: minuteOr(detail && detail.curfew ? detail.curfew.start_minutes : -1)
  readonly property int curfewEndMin: minuteOr(detail && detail.curfew ? detail.curfew.end_minutes : -1)
  readonly property int windowStartMin: minuteOr(detail && detail.edit_window ? detail.edit_window.start_minutes : -1)
  readonly property int windowEndMin: minuteOr(detail && detail.edit_window ? detail.edit_window.end_minutes : -1)

  readonly property string curfewStartText: detail && detail.curfew ? String(detail.curfew.start) : ""
  readonly property string curfewEndText: detail && detail.curfew ? String(detail.curfew.end) : ""

  readonly property bool curfewEnabled: !!detail && !!detail.curfew && detail.curfew.enabled === true
  readonly property bool locked: verdict === "locked"
  readonly property bool windowOpen: !!detail && !!detail.edit_window && detail.edit_window.open === true

  // Minutes from now to a time of day, wrapping past midnight.
  function untilMinutes(target) {
    if (nowMinutes < 0 || target < 0) return -1
    var d = target - nowMinutes
    return d < 0 ? d + 1440 : d
  }

  // "3 h 18", "45 min", "2 h". Never "0 h 0" and never a bare number: a
  // duration with no unit beside a clock full of times reads as a time.
  function humanDuration(minutes) {
    if (minutes < 0) return "—"
    var h = Math.floor(minutes / 60)
    var m = minutes % 60
    if (h === 0) return m + " min"
    if (m === 0) return h + " h"
    return h + " h " + m
  }

  // A verdict is a judgement the signer made; this only translates it. An
  // unknown verdict falls through to whatever the payload said, so a verdict
  // added later shows up untranslated instead of vanishing.
  readonly property string stateWord: {
    if (!detail) return "…"
    switch (clock.verdict) {
    case "locked":          return "CERRADO"
    case "outside_curfew":  return "ABIERTO"
    case "grace_active":    return "GRACIA"
    case "clock_tamper":    return "RELOJ MANIPULADO"
    case "offline_blocked": return "SIN RED"
    case "unavailable":     return "NO DISPONIBLE"
    default:                return String(detail.word)
    }
  }

  // The single number worth putting in the middle of the dial: how long until
  // the thing that is about to change, changes.
  readonly property string dialHeadline: {
    if (!detail || nowMinutes < 0) return "—"
    return humanDuration(untilMinutes(locked ? curfewEndMin : curfewStartMin))
  }
  readonly property string dialCaption: {
    if (!detail || nowMinutes < 0) return "hora sin verificar"
    return locked ? "hasta que abra" : "hasta el curfew"
  }

  // Empty when the curfew is ordinary. The dial prints both hours on the ring
  // and counts down to the next one in the middle, and the state word says
  // which side of them we are on -- a sentence repeating all three is the kind
  // of caption that makes a screen feel like a manual. What is left is the
  // cases the ring cannot draw.
  readonly property string curfewSentence: {
    if (!detail) return "leyendo…"
    if (!curfewEnabled) return "El curfew está apagado. No se cierra nada."
    if (curfewStartText === "" || curfewEndText === "") return "El curfew no tiene horas válidas."
    return ""
  }
  readonly property bool curfewSentenceIsWarning: curfewSentence !== "" && !!detail

  // The payload describes the edit window in English because it is also read by
  // non-Spanish surfaces; these panels are Spanish throughout, so the ordinary
  // open/closed cases are composed here from the structured minutes. The edge
  // states (unconfigured, disabled, malformed, clock unverified) keep the
  // payload's own wording — those are judgements, not descriptions, and
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

  readonly property string gateHeadline: windowOpen
    ? "Puedes debilitar el pacto"
    : "No puedes debilitar el pacto"
}
