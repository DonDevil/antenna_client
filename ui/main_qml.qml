import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: root
    visible: true
    width: 1600
    height: 1000
    title: "Antenna Design Studio"
    color: "#0f172a"

    // Modern color scheme - Dark theme
    readonly property color primaryColor: "#3b82f6"
    readonly property color primaryDark: "#1e3a8a"
    readonly property color secondaryColor: "#06b6d4"
    readonly property color accentColor: "#10b981"
    readonly property color successColor: "#22c55e"
    readonly property color warningColor: "#f59e0b"
    readonly property color backgroundColor: "#0f172a"
    readonly property color surfaceColor: "#1e293b"
    readonly property color surfaceLight: "#334155"
    readonly property color borderColor: "#475569"
    readonly property color textPrimary: "#f1f5f9"
    readonly property color textSecondary: "#cbd5e1"
    readonly property color textTertiary: "#94a3b8"

    // Top Bar
    Rectangle {
        id: topBar
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 60
        color: root.surfaceColor
        border.bottom.width: 1
        border.bottom.color: root.borderColor

        RowLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 16

            Text {
                text: "🎯 Antenna Design Studio"
                font.pixelSize: 20
                font.weight: Font.Bold
                color: root.textPrimary
            }

            Item { Layout.fillWidth: true }

            // Status Indicators
            RowLayout {
                spacing: 16

                RowLayout {
                    spacing: 6
                    Rectangle {
                        width: 10
                        height: 10
                        radius: 5
                        color: root.successColor
                    }
                    Text {
                        text: "CST"
                        font.pixelSize: 11
                        color: root.textSecondary
                    }
                }

                RowLayout {
                    spacing: 6
                    Rectangle {
                        width: 10
                        height: 10
                        radius: 5
                        color: root.successColor
                    }
                    Text {
                        text: "API"
                        font.pixelSize: 11
                        color: root.textSecondary
                    }
                }

                RowLayout {
                    spacing: 6
                    Rectangle {
                        width: 10
                        height: 10
                        radius: 5
                        color: root.warningColor
                    }
                    Text {
                        text: "Server"
                        font.pixelSize: 11
                        color: root.textSecondary
                    }
                }
            }
        }
    }

    // Main Content
    RowLayout {
        anchors.top: topBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 0
        spacing: 0

        // ===== LEFT PANEL: DESIGN INPUTS =====
        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: 420
            color: root.surfaceColor
            border.right.width: 1
            border.right.color: root.borderColor

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 18

                // Section Header
                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: root.borderColor
                }

                Text {
                    text: "Design Parameters"
                    font.pixelSize: 16
                    font.weight: Font.Bold
                    color: root.textPrimary
                }

                // Chat Mode Card
                Rectangle {
                    Layout.fillWidth: true
                    height: 56
                    color: root.surfaceLight
                    border.color: root.borderColor
                    border.width: 1
                    radius: 8

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 4

                        Text {
                            text: "Chat Mode"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: root.textSecondary
                        }

                        ComboBox {
                            id: chatModeCombo
                            Layout.fillWidth: true
                            model: ["⚡ Speed Mode", "💎 Quality Mode"]
                            currentIndex: 0

                            background: Rectangle {
                                color: root.surfaceColor
                                border.color: root.primaryColor
                                border.width: 1
                                radius: 6
                                opacity: 0.6
                            }

                            contentItem: Text {
                                text: chatModeCombo.displayText
                                color: root.textPrimary
                                font.pixelSize: 12
                                leftPadding: 8
                            }
                        }
                    }
                }

                // Antenna Family Card
                Rectangle {
                    Layout.fillWidth: true
                    height: 56
                    color: root.surfaceLight
                    border.color: root.borderColor
                    border.width: 1
                    radius: 8

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 4

                        Text {
                            text: "Antenna Family"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: root.textSecondary
                        }

                        ComboBox {
                            id: familyCombo
                            Layout.fillWidth: true
                            model: ["📡 Patch", "📌 Dipole", "🎯 Monopole", "📢 Horn", "🌀 Helical"]
                            currentIndex: 0

                            background: Rectangle {
                                color: root.surfaceColor
                                border.color: root.primaryColor
                                border.width: 1
                                radius: 6
                                opacity: 0.6
                            }

                            contentItem: Text {
                                text: familyCombo.displayText
                                color: root.textPrimary
                                font.pixelSize: 12
                                leftPadding: 8
                            }
                        }
                    }
                }

                // Materials Section
                Text {
                    text: "Materials"
                    font.pixelSize: 12
                    font.weight: Font.Bold
                    color: root.textSecondary
                    Layout.topMargin: 8
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 48
                    color: root.surfaceLight
                    border.color: root.borderColor
                    border.width: 1
                    radius: 8

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 12

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            Text {
                                text: "Substrate"
                                font.pixelSize: 10
                                color: root.textTertiary
                            }

                            TextInput {
                                Layout.fillWidth: true
                                text: "FR4"
                                color: root.textPrimary
                                font.pixelSize: 12
                            }
                        }

                        Rectangle {
                            width: 1
                            height: parent.height - 8
                            color: root.borderColor
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            Text {
                                text: "Conductor"
                                font.pixelSize: 10
                                color: root.textTertiary
                            }

                            TextInput {
                                Layout.fillWidth: true
                                text: "Copper"
                                color: root.textPrimary
                                font.pixelSize: 12
                            }
                        }
                    }
                }

                // Dimensions Section
                Text {
                    text: "Dimensions (mm)"
                    font.pixelSize: 12
                    font.weight: Font.Bold
                    color: root.textSecondary
                    Layout.topMargin: 8
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: 8
                    rowSpacing: 8

                    Repeater {
                        model: [
                            { label: "Patch Width", icon: "◀▶" },
                            { label: "Patch Length", icon: "▲▼" },
                            { label: "Substrate W", icon: "◀▶" },
                            { label: "Substrate L", icon: "▲▼" }
                        ]

                        Rectangle {
                            Layout.fillWidth: true
                            height: 44
                            color: root.surfaceLight
                            border.color: root.borderColor
                            border.width: 1
                            radius: 6

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 2

                                Text {
                                    text: modelData.label
                                    font.pixelSize: 9
                                    color: root.textTertiary
                                }

                                TextInput {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    placeholderText: "0.0"
                                    color: root.textPrimary
                                    font.pixelSize: 11
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }
                    }
                }

                // Target Frequency
                Text {
                    text: "Target Specifications"
                    font.pixelSize: 12
                    font.weight: Font.Bold
                    color: root.textSecondary
                    Layout.topMargin: 8
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Rectangle {
                        Layout.fillWidth: true
                        height: 48
                        color: root.surfaceLight
                        border.color: root.borderColor
                        border.width: 1
                        radius: 6

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 2

                            Text {
                                text: "Frequency (GHz)"
                                font.pixelSize: 10
                                color: root.textTertiary
                            }

                            TextInput {
                                Layout.fillWidth: true
                                placeholderText: "2.45"
                                color: root.textPrimary
                                font.pixelSize: 12
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 48
                        color: root.surfaceLight
                        border.color: root.borderColor
                        border.width: 1
                        radius: 6

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 2

                            Text {
                                text: "Bandwidth (MHz)"
                                font.pixelSize: 10
                                color: root.textTertiary
                            }

                            TextInput {
                                Layout.fillWidth: true
                                placeholderText: "100"
                                color: root.textPrimary
                                font.pixelSize: 12
                            }
                        }
                    }
                }

                // Spacer
                Item {
                    Layout.fillHeight: true
                }

                // Action Buttons
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Button {
                        Layout.fillWidth: true
                        text: "▶ Start Optimization"
                        height: 48

                        background: Rectangle {
                            color: root.primaryColor
                            radius: 8
                            border.width: 0

                            Behavior on color {
                                ColorAnimation { duration: 200 }
                            }
                        }

                        contentItem: Text {
                            text: parent.text
                            color: root.textPrimary
                            font.weight: Font.Bold
                            font.pixelSize: 13
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        hoverEnabled: true
                        onHoveredChanged: {
                            background.color = hovered ? root.secondaryColor : root.primaryColor
                        }
                    }

                    Button {
                        Layout.fillWidth: true
                        text: "✕ Clear All"
                        height: 40

                        background: Rectangle {
                            color: root.surfaceLight
                            radius: 8
                            border.color: root.borderColor
                            border.width: 1

                            Behavior on color {
                                ColorAnimation { duration: 200 }
                            }
                        }

                        contentItem: Text {
                            text: parent.text
                            color: root.textSecondary
                            font.weight: Font.Bold
                            font.pixelSize: 12
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        hoverEnabled: true
                        onHoveredChanged: {
                            background.color = hovered ? root.borderColor : root.surfaceLight
                        }
                    }
                }
            }
        }

        // ===== MIDDLE PANEL: CHAT =====
        Rectangle {
            Layout.fillHeight: true
            Layout.fillWidth: true
            color: "#ffffff"
            border.color: root.borderColor
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 0
                spacing: 0

                // Chat Header
                Rectangle {
                    Layout.fillWidth: true
                    height: 60
                    color: root.backgroundColor
                    border.color: root.borderColor
                    border.width: 0
                    border.bottom.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Text {
                            text: "Design Assistant"
                            font.pixelSize: 16
                            font.weight: Font.Bold
                            color: root.textPrimary
                        }

                        Item {
                            Layout.fillWidth: true
                        }

                        Rectangle {
                            width: 12
                            height: 12
                            radius: 6
                            color: root.accentColor
                        }

                        Text {
                            text: "Connected"
                            font.pixelSize: 11
                            color: root.textSecondary
                        }
                    }
                }

                // Chat Messages Area
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "#fafafa"

                    ListView {
                        id: chatListView
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12
                        clip: true

                        model: 3

                        delegate: Rectangle {
                            width: chatListView.width - 32
                            height: messageText.height + 16
                            color: index % 2 === 0 ? "#e0f2fe" : "#f0f9ff"
                            radius: 8
                            border.color: root.borderColor
                            border.width: 1

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 4

                                Text {
                                    text: index % 2 === 0 ? "You" : "Assistant"
                                    font.pixelSize: 10
                                    font.weight: Font.Bold
                                    color: root.textSecondary
                                }

                                Text {
                                    id: messageText
                                    text: index % 2 === 0 ? 
                                        "Can you optimize the antenna for 2.4 GHz?" :
                                        "I'll optimize the antenna design for 2.4 GHz operation. Using the current dimensions, I'll adjust the patch length and width..."
                                    color: root.textPrimary
                                    font.pixelSize: 12
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }

                // Chat Input Area
                Rectangle {
                    Layout.fillWidth: true
                    height: 70
                    color: root.backgroundColor
                    border.color: root.borderColor
                    border.top.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 8

                        Rectangle {
                            Layout.fillWidth: true
                            height: 44
                            color: "#ffffff"
                            border.color: root.borderColor
                            border.width: 1
                            radius: 6

                            TextInput {
                                anchors.fill: parent
                                anchors.margins: 12
                                verticalAlignment: Text.AlignVCenter
                                placeholderText: "Ask about your antenna design..."
                                color: root.textPrimary
                            }
                        }

                        Button {
                            width: 44
                            height: 44

                            background: Rectangle {
                                color: root.primaryColor
                                radius: 6
                            }

                            contentItem: Text {
                                text: "→"
                                color: "#ffffff"
                                font.pixelSize: 20
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }

                            hoverEnabled: true
                            onHoveredChanged: {
                                background.color = hovered ? root.secondaryColor : root.primaryColor
                            }
                        }
                    }
                }
            }
        }

        // ===== RIGHT PANEL: RESULTS =====
        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: 350
            color: root.backgroundColor
            border.color: root.borderColor
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12

                // Tabs
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Repeater {
                        model: ["Results", "Frequency", "Metrics"]

                        Button {
                            text: modelData
                            Layout.fillWidth: true
                            height: 36

                            background: Rectangle {
                                color: index === 0 ? root.primaryColor : "#f3f4f6"
                                radius: 4
                            }

                            contentItem: Text {
                                text: parent.text
                                color: index === 0 ? "#ffffff" : root.textPrimary
                                font.weight: Font.Bold
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }

                // Results Display
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "#ffffff"
                    border.color: root.borderColor
                    border.width: 1
                    radius: 6

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 8

                        Text {
                            text: "Design Metrics"
                            font.pixelSize: 14
                            font.weight: Font.Bold
                            color: root.textPrimary
                        }

                        Repeater {
                            model: [
                                { label: "Frequency", value: "2.45 GHz" },
                                { label: "Bandwidth", value: "450 MHz" },
                                { label: "Gain", value: "6.2 dB" },
                                { label: "VSWR", value: "1.15" }
                            ]

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12

                                Text {
                                    text: modelData.label
                                    color: root.textSecondary
                                    font.pixelSize: 11
                                    Layout.fillWidth: true
                                }

                                Rectangle {
                                    width: 100
                                    height: 24
                                    color: root.primaryColor
                                    radius: 4
                                    opacity: 0.1

                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.value
                                        color: root.primaryColor
                                        font.weight: Font.Bold
                                        font.pixelSize: 11
                                    }
                                }
                            }
                        }

                        Item {
                            Layout.fillHeight: true
                        }

                        Button {
                            Layout.fillWidth: true
                            text: "Export Results"
                            height: 40

                            background: Rectangle {
                                color: root.accentColor
                                radius: 6
                            }

                            contentItem: Text {
                                text: parent.text
                                color: "#ffffff"
                                font.weight: Font.Bold
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }
            }
        }
    }
}
