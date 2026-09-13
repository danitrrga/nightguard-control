import QtQuick
import Quickshell.Io
import qs.Commons

// The write path, in one place: stage, price, confirm, sign.
//
// Both surfaces that can change the config — the dropdown and the workshop —
// instantiate this rather than each growing its own copy. A second
// implementation would eventually price a change differently from the one that
// signs it, and the whole product is the promise that those two agree.
//
// Nothing here decides anything. `ngtui propose` asks the signer's own
// classifier what a staged edit DOES and what it costs; `ngtui commit` hands
// the result to the root signer through polkit. This object only carries the
// answers between them and reports what came back, verbatim.
//
// The order is a contract and it is the whole point:
//
//     stage  →  propose (unprivileged, writes nothing)
//            →  cost and refusal ON SCREEN
//            →  the user confirms
//            →  commit → pkexec → the signer
//            →  the result, then re-read
//
// A polkit dialog must never appear for a change the signer has already
// refused. `canApply` is false in that case and the reason is beside the
// button before it is pressed.
Item {
  id: writer

  // Absolute on purpose: the shell does not inherit the login PATH and
  // ~/.local/bin is not on its own.
  property string ngtuiPath: "/home/danitrrga/.local/bin/ngtui"

  // Staged edits, in the order the user made them. Each is
  // { key, action, value, label } — `label` is what the pending list shows and
  // is never sent to the CLI.
  property var ops: []

  // The last answer from `ngtui propose`, verbatim. Null until one arrives.
  property var preview: null
  property string previewError: ""
  property bool previewing: false

  property bool committing: false
  property string resultText: ""
  property string resultKind: ""   // "ok" | "noop" | "refused" | "cancelled" | "error"

  signal committed()

  readonly property int count: ops.length
  readonly property var decision: preview && preview.decision ? preview.decision : null
  readonly property bool loosening: !!preview && preview.loosening === true
  readonly property bool costsToken: !!decision && decision.costs_token === true
  readonly property bool isNoop: !!decision && decision.is_noop === true

  // Everything that must be true before an authentication dialog is allowed to
  // appear. A preview that failed counts as "not allowed": a commit whose cost
  // could not be computed is a commit whose cost the user was not told.
  readonly property bool canApply: count > 0 && !previewing && !committing
                                   && !!preview && preview.ok === true
                                   && !!decision && decision.allowed === true
                                   && previewError === ""

  readonly property string refusalReason: {
    if (previewError !== "") return previewError
    if (!!decision && decision.allowed === false) return String(decision.reason || "")
    return ""
  }

  // --- staging --------------------------------------------------------------

  // Add an edit, or take it back off if the same one is already staged. A
  // second click on the same switch is the user changing his mind, and it must
  // leave nothing behind to sign.
  function stage(key, action, value, label) {
    var next = []
    var removed = false
    for (var i = 0; i < ops.length; i++) {
      var op = ops[i]
      if (op.key === key && op.action === action && String(op.value) === String(value)) {
        removed = true
        continue
      }
      // One key can only carry one scalar edit. Staging "games on" after
      // "games off" replaces it rather than queueing both.
      if (op.key === key && op.action === "set" && action === "set") continue
      next.push(op)
    }
    if (!removed) next.push({ key: key, action: action, value: value, label: label })
    ops = next
    refreshPreview()
  }

  function unstage(index) {
    var next = []
    for (var i = 0; i < ops.length; i++) if (i !== index) next.push(ops[i])
    ops = next
    refreshPreview()
  }

  function discard() {
    ops = []
    preview = null
    previewError = ""
    resultText = ""
    resultKind = ""
    refreshPreview()
  }

  // Is this exact edit staged right now? Lets a switch show the value it WOULD
  // have, so the control the user just flipped does not snap back while the
  // change waits to be applied.
  function staged(key, action, value) {
    for (var i = 0; i < ops.length; i++) {
      var op = ops[i]
      if (op.key === key && op.action === action && String(op.value) === String(value))
        return true
    }
    return false
  }

  function stagedValue(key, fallback) {
    for (var i = 0; i < ops.length; i++)
      if (ops[i].key === key && ops[i].action === "set") return ops[i].value
    return fallback
  }

  // --- pricing --------------------------------------------------------------

  function refreshPreview() {
    resultText = ""
    resultKind = ""
    if (ops.length === 0) {
      preview = null
      previewError = ""
      previewing = false
      if (proposeProc.running) proposeProc.running = false
      return
    }
    // A Process that is still running cannot be relaunched, so a preview that
    // never returned would freeze every edit after it. The watchdog below is
    // what makes a second keystroke possible at all.
    if (proposeProc.running) proposeProc.running = false
    var payload = []
    for (var i = 0; i < ops.length; i++)
      payload.push({ key: ops[i].key, action: ops[i].action, value: ops[i].value })
    proposeProc.command = [writer.ngtuiPath, "propose", "--ops-json", JSON.stringify(payload)]
    previewing = true
    previewError = ""
    proposeProc.running = true
    proposeWatchdog.restart()
  }

  Process {
    id: proposeProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        proposeWatchdog.stop()
        writer.previewing = false
        var parsed = null
        try {
          parsed = JSON.parse(text || "")
        } catch (e) {
          writer.preview = null
          writer.previewError = "No se pudo calcular el coste. No se aplica nada hasta que se pueda."
          return
        }
        writer.preview = parsed
        writer.previewError = parsed && parsed.ok === true ? "" : String(parsed && parsed.error ? parsed.error : "No se pudo calcular el coste.")
      }
    }
  }

  Timer {
    id: proposeWatchdog
    interval: 10000
    onTriggered: {
      if (proposeProc.running) proposeProc.running = false
      writer.previewing = false
      writer.preview = null
      writer.previewError = "No se pudo calcular el coste. No se aplica nada hasta que se pueda."
    }
  }

  // --- signing --------------------------------------------------------------

  function apply() {
    if (!canApply) return
    if (commitProc.running) return
    commitProc.command = [writer.ngtuiPath, "commit", "--from", String(preview.path)]
    committing = true
    resultText = ""
    resultKind = ""
    commitProc.running = true
    commitWatchdog.restart()
  }

  Process {
    id: commitProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        commitWatchdog.stop()
        writer.committing = false
        var parsed = null
        try {
          parsed = JSON.parse(text || "")
        } catch (e) {
          writer.resultKind = "error"
          writer.resultText = "Detalle no disponible: el ngtui instalado no conoce «commit». Ejecuta el despliegue."
          return
        }
        writer.report(parsed)
      }
    }
  }

  Timer {
    id: commitWatchdog
    interval: 120000   // a fingerprint or a password prompt is a human, not a program
    onTriggered: {
      if (commitProc.running) commitProc.running = false
      writer.committing = false
      writer.resultKind = "error"
      writer.resultText = "La autorización no respondió. No se ha escrito nada."
    }
  }

  // What came back, said in Spanish around words that are never translated.
  //
  // The signer's own REFUSED(...) and committed(...) lines are surfaced
  // verbatim: translating a refusal would put words in the trust boundary's
  // mouth. 126 and 127 are pkexec's own — 126 is the user dismissing the
  // dialog and 127 is not being authorised — and they are two different
  // sentences because a user who CHOSE to cancel must not be told he was
  // refused.
  function report(parsed) {
    if (parsed.error) {
      resultKind = "error"
      resultText = "✕ " + String(parsed.error)
      return
    }
    var rc = Number(parsed.returncode)
    var out = String(parsed.stdout || "")
    var err = String(parsed.stderr || "")
    if (rc === 0) {
      if (out.indexOf("no-op") === 0) {
        resultKind = "noop"
        resultText = "· sin cambios: la configuración ya era esa"
      } else {
        resultKind = "ok"
        resultText = "✓ aplicado — " + out
      }
      ops = []
      preview = null
      committed()
      return
    }
    if (rc === 126) {
      resultKind = "cancelled"
      resultText = "✕ cancelado — no se autorizó nada, no se ha escrito nada"
      return
    }
    if (rc === 127) {
      resultKind = "error"
      resultText = "✕ no autorizado — no se ha escrito nada"
      return
    }
    var last = ""
    var lines = err.split("\n")
    for (var i = lines.length - 1; i >= 0; i--) {
      if (lines[i].trim() !== "") { last = lines[i].trim(); break }
    }
    resultKind = "refused"
    resultText = "✕ rechazado — " + (last !== "" ? last : out)
  }

  // --- the sentence under the button ---------------------------------------

  readonly property string costLine: {
    if (count === 0) return ""
    if (previewing) return "calculando el coste…"
    if (previewError !== "") return previewError
    if (!preview || preview.ok !== true) return "No se pudo calcular el coste. No se aplica nada hasta que se pueda."
    if (!decision) return "No se pudo calcular el coste. No se aplica nada hasta que se pueda."
    if (decision.allowed === false) return "✕ no se puede aplicar: " + String(decision.reason || "")
    if (isNoop) return count + (count === 1 ? " cambio · sin efecto" : " cambios · sin efecto")
    if (!costsToken) return count + (count === 1 ? " cambio · refuerza · gratis" : " cambios · refuerzan · gratis")
    var spent = Number(decision.effective_spent || 0)
    var left = Math.max(0, writer.tokensTotal - (spent + 1))
    return count + (count === 1 ? " cambio · debilita · cuesta 1 ficha · te quedarán "
                                : " cambios · debilitan · cuestan 1 ficha · te quedarán ") + left
  }

  // The signer's ceiling, injected rather than assumed: the panel payload
  // carries it and a literal here could drift from what the signer charges.
  property int tokensTotal: 3

  readonly property string applyLabel: {
    if (committing) return "Autorizando…"
    if (costsToken) return "Aplicar · 1 ficha"
    return "Aplicar cambios"
  }

  readonly property string confirmMessage: {
    if (costsToken)
      return "Esto DEBILITA el pacto y gasta una de tus fichas de la semana. Hay que autorizarlo."
    return "Esto refuerza el pacto y no gasta ficha. Hay que autorizarlo igualmente."
  }
}
