import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    width: 390
    height: 844
    color: "#ffffff"

    Column {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 16

        Text {
            text: "Settings"
            font.pixelSize: 24
            color: "#1f1f1f"
        }

        TextField {
            id: nameField
            width: parent.width
            placeholderText: "Display name"
        }

        Row {
            spacing: 12
            Text {
                text: "Notifications"
                font.pixelSize: 16
                color: "#1f1f1f"
                anchors.verticalCenter: parent.verticalCenter
            }
            Rectangle {
                id: toggle
                width: 20
                height: 20
                radius: 4
                color: "#1b5fd1"
                Accessible.role: Accessible.CheckBox
                MouseArea {
                    anchors.fill: parent
                    onClicked: toggle.color = toggle.color == "#1b5fd1" ? "#cccccc" : "#1b5fd1"
                }
            }
        }
    }
}
