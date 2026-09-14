import QtQuick
import QtQuick.Shapes
import qs.Commons

// A 24-hour dial: the whole day as a ring, the curfew as one arc and the hours
// the pact may be weakened as another, with a mark at now and the next
// transition counted down in the middle.
//
// A ring rather than a bar because a day is a cycle, and the question it
// answers — "how long until this changes?" — is a distance around a circle.
// Built with Shape/PathAngleArc, which is how the shell draws its own dial
// (Ui/SpeedTestOverlay.qml:265-321); Canvas is used nowhere in the tree.
//
// One file, two callers: the dropdown draws it small and mute, the window draws
// it large with the two boundary times printed where they fall on the clock.
// They were one component copied twice for about a day, which is how a panel
// and a window start disagreeing about which hour the curfew begins.
Item {
  id: dial

  // Minutes past midnight, or -1 for "not known" — which draws nothing rather
  // than drawing a plausible wrong arc.
  property int curfewStart: -1
  property int curfewEnd: -1
  property int windowStart: -1
  property int windowEnd: -1
  property int nowMinutes: -1

  property string headline: ""
  property string caption: ""
  property string startLabel: ""
  property string endLabel: ""

  // Off in the dropdown, on in the window: at 150px the two times crowd the
  // ring, at 240 they are the reason the ring reads as a clock.
  property bool showTimes: false
  property bool showQuarters: true

  property color foregroundColor: Color.foreground
  property color dimColor: Qt.darker(Color.foreground, 1.55)
  property color trackColor: Style.selectedFillFor(Color.foreground, Color.accent)
  property color curfewColor: Color.urgent
  property color windowColor: Color.accent
  property color headlineColor: dial.foregroundColor
  // What the ring is drawn ON. The quarter notches and the ring behind the
  // now-marker are punched in this colour, so a caller on a different surface
  // must say so or the notches show up as smudges.
  property color voidColor: Color.background
  property string fontFamily: Style.font.family
  property int headlineSize: Style.font.heading

  // Room outside the ring: the quarter notches sit on it, the boundary times
  // sit beyond it.
  readonly property real edgePadding: showTimes ? Style.space(30) : Style.space(7)
  readonly property real ringRadius: Math.max(Style.space(20),
                                              Math.min(width, height) / 2 - edgePadding)
  readonly property real ringWidth: Style.space(7)

  // Midnight at the top, clockwise. PathAngleArc puts 0 degrees at 3 o'clock,
  // so the day starts a quarter turn back.
  function angleOf(minutes) { return -90 + (minutes / 1440) * 360 }

  // An arc that wraps midnight is still one arc here — unlike a flat strip, a
  // ring has no seam to split at, which is half the reason it reads better.
  function sweepOf(from, to) {
    var span = to - from
    if (span < 0) span += 1440
    return (span / 1440) * 360
  }
  function drawable(from, to) { return from >= 0 && to >= 0 && from !== to }

  function pointX(minutes, radius) {
    return width / 2 + radius * Math.cos(angleOf(minutes) * Math.PI / 180)
  }
  function pointY(minutes, radius) {
    return height / 2 + radius * Math.sin(angleOf(minutes) * Math.PI / 180)
  }

  implicitHeight: Style.space(150)
  implicitWidth: implicitHeight

  Shape {
    anchors.fill: parent
    preferredRendererType: Shape.CurveRenderer

    // The day itself.
    ShapePath {
      strokeWidth: dial.ringWidth
      strokeColor: dial.trackColor
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
                   ? Qt.rgba(dial.curfewColor.r, dial.curfewColor.g, dial.curfewColor.b, 0.85)
                   : "transparent"
      fillColor: "transparent"
      capStyle: ShapePath.FlatCap
      PathAngleArc {
        id: curfewArc
        centerX: dial.width / 2; centerY: dial.height / 2
        radiusX: dial.ringRadius; radiusY: dial.ringRadius
        startAngle: dial.angleOf(dial.curfewStart)
        sweepAngle: dial.drawable(dial.curfewStart, dial.curfewEnd)
                    ? dial.sweepOf(dial.curfewStart, dial.curfewEnd) : 0
        // Staging a new hour moves the arc instead of teleporting it. The
        // movement is the confirmation that the edit landed on the thing the
        // ring is about — a redrawn ring in a new position is just a different
        // picture.
        Behavior on startAngle { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
        Behavior on sweepAngle { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
      }
    }

    // When the pact may be weakened, on an inner track so the two never overlap
    // into an unreadable smear.
    ShapePath {
      strokeWidth: Math.max(2, Style.space(3))
      strokeColor: dial.drawable(dial.windowStart, dial.windowEnd)
                   ? dial.windowColor : "transparent"
      fillColor: "transparent"
      capStyle: ShapePath.FlatCap
      PathAngleArc {
        centerX: dial.width / 2; centerY: dial.height / 2
        radiusX: dial.ringRadius - dial.ringWidth
        radiusY: dial.ringRadius - dial.ringWidth
        startAngle: dial.angleOf(dial.windowStart)
        sweepAngle: dial.drawable(dial.windowStart, dial.windowEnd)
                    ? dial.sweepOf(dial.windowStart, dial.windowEnd) : 0
        Behavior on startAngle { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
        Behavior on sweepAngle { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
      }
    }
  }

  // Midnight, six, noon, six — cut out of the ring rather than drawn outside
  // it, so the clock reads in quarters without the dial needing a wider box.
  Repeater {
    model: dial.showQuarters ? [0, 360, 720, 1080] : []

    Rectangle {
      required property int modelData
      width: Math.max(1, Style.space(2))
      height: dial.ringWidth + Style.space(2)
      color: dial.voidColor
      antialiasing: true
      x: dial.pointX(modelData, dial.ringRadius) - width / 2
      y: dial.pointY(modelData, dial.ringRadius) - height / 2
      rotation: dial.angleOf(modelData) + 90
    }
  }

  // Now.
  Rectangle {
    visible: dial.nowMinutes >= 0
    width: Style.space(7)
    height: width
    radius: width / 2
    color: dial.foregroundColor
    border.width: Math.max(1, Style.space(2))
    border.color: dial.voidColor
    x: dial.pointX(dial.nowMinutes, dial.ringRadius) - width / 2
    y: dial.pointY(dial.nowMinutes, dial.ringRadius) - height / 2
  }

  // The two hours the ring is actually about, printed where they fall on it.
  // This is the legend; a colour key in a corner would make the reader carry
  // the mapping across the card instead of reading it off the clock.
  Repeater {
    model: dial.showTimes
           ? [{ minutes: dial.curfewStart, text: dial.startLabel },
              { minutes: dial.curfewEnd,   text: dial.endLabel }]
           : []

    Text {
      required property var modelData
      readonly property real radius: dial.ringRadius + dial.ringWidth / 2 + Style.space(9)
      visible: modelData.minutes >= 0 && modelData.text !== ""
      textFormat: Text.PlainText
      text: modelData.text
      color: dial.dimColor
      font.family: dial.fontFamily
      font.pixelSize: Style.font.caption
      // Pushed out along its own angle by half its own size, so the label's
      // INNER edge sits on the ring's outer edge instead of its centre landing
      // there -- which put half of "05:30" on top of the curfew arc.
      readonly property real theta: dial.angleOf(modelData.minutes) * Math.PI / 180
      x: dial.pointX(modelData.minutes, radius) - width / 2 + (width / 2) * Math.cos(theta)
      y: dial.pointY(modelData.minutes, radius) - height / 2 + (height / 2) * Math.sin(theta)
    }
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
      font.family: dial.fontFamily
      font.pixelSize: dial.headlineSize
      font.bold: true
    }
    Text {
      anchors.horizontalCenter: parent.horizontalCenter
      textFormat: Text.PlainText
      text: dial.caption
      color: dial.dimColor
      font.family: dial.fontFamily
      font.pixelSize: Style.font.caption
    }
  }
}
