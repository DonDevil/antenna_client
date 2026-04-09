import QtQuick
import QtQuick.Controls
import QtQuick.Window

ApplicationWindow {
    id: root
    visible: true
    width: 1200
    height: 620
    title: "Antenna Design Studio"
    color: "#c7c7c9"
    onClosing: function(close) {
        designController.shutdown()
    }

    property color panelBg: "#9ea0ad"
    property color chatBg: "#b9a3a4"
    property color fieldBg: "#e3e3e3"
    property color btnBg: "#5e84de"
    property string statusText: "Ready"
    property string historyLoadError: ""
    property string historySearchText: ""
    property bool showArchivedHistory: false
    property string pendingHistoryAction: ""
    property string pendingHistorySessionId: ""
    property string pendingHistoryHeading: ""
    property string sessionNamePopupMode: ""
    property string sessionNameError: ""
    property string configPageText: ""
    property string configLoadError: ""
    property string stateLoadError: ""
    property string cstResultsError: ""
    property string cstResultsMessage: ""
    property bool annConnected: false
    property bool llmConnected: false
    property bool cstConnected: false
    property bool commConnected: false
    property var historyCache: []
    property var stateSections: []
    property var cstResultsSections: []
    property var cstArtifactItems: []
    property var configSections: []

    ListModel {
        id: chatModel
    }

    ListModel {
        id: historyModel
    }

    function prettyLabel(value) {
        return String(value || "")
            .replace(/_/g, " ")
            .replace(/\b\w/g, function(letter) { return letter.toUpperCase() })
    }

    function displayValue(value) {
        if (value === undefined || value === null || value === "") {
            return "-"
        }
        if (Array.isArray(value)) {
            return value.join(", ")
        }
        if (typeof value === "object") {
            return JSON.stringify(value)
        }
        return String(value)
    }

    function makeField(label, value) {
        return {"label": label, "value": displayValue(value)}
    }

    function setComboValue(combo, value) {
        if (value === undefined || value === null || value === "") {
            return
        }
        var resolved = String(value)
        for (var i = 0; i < combo.model.length; i++) {
            if (String(combo.model[i]) === resolved) {
                combo.currentIndex = i
                return
            }
        }
    }

    function applyFamilyDefaults(family) {
        var resolved = String(family || "")
        if (resolved === "microstrip_patch") {
            setComboValue(patchShapeCombo, "rectangular")
            setComboValue(feedTypeCombo, "edge")
            setComboValue(polarizationCombo, "linear")
            return
        }
        setComboValue(patchShapeCombo, "auto")
        setComboValue(feedTypeCombo, "auto")
        setComboValue(polarizationCombo, "unspecified")
    }

    function buildFieldsFromObject(data) {
        var fields = []
        if (!data) {
            return fields
        }
        for (var key in data) {
            fields.push(makeField(prettyLabel(key), data[key]))
        }
        return fields
    }

    function lastMessageBySender(history, sender) {
        if (!history) {
            return ""
        }
        for (var index = history.length - 1; index >= 0; index--) {
            var item = history[index]
            if (item && item.sender === sender && item.message) {
                return String(item.message)
            }
        }
        return ""
    }

    function loadStateSections() {
        stateSections = []
        stateLoadError = ""

        var payload = designController.currentStateText()
        var state = {}
        try {
            state = JSON.parse(payload)
        } catch (error) {
            stateLoadError = "Unable to read current session state"
            return
        }

        var sections = []
        sections.push({
            "title": "Session Overview",
            "fields": [
                makeField("Session Name", state.session_name),
                makeField("Session ID", state.session_id),
                makeField("Trace ID", state.trace_id),
                makeField("Design ID", state.design_id),
                makeField("Current Stage", state.current_stage),
                makeField("Iteration", state.iteration_index)
            ]
        })

        var designFields = buildFieldsFromObject(state.current_design)
        if (designFields.length > 0) {
            sections.push({"title": "Design Inputs", "fields": designFields})
        }

        var resultFields = buildFieldsFromObject(state.last_result)
        if (resultFields.length > 0) {
            sections.push({"title": "Latest Result", "fields": resultFields})
        }

        var history = state.chat_history || []
        var commandPackage = state.current_command_package || {}
        sections.push({
            "title": "Activity",
            "fields": [
                makeField("Chat Messages", history.length),
                makeField("Last User Message", lastMessageBySender(history, "You")),
                makeField("Last Assistant Message", lastMessageBySender(history, "Assistant")),
                makeField("Command Count", commandPackage.commands ? commandPackage.commands.length : 0),
                makeField("Command Package Design ID", commandPackage.design_id),
                makeField("Command Package Iteration", commandPackage.iteration_index)
            ]
        })

        stateSections = sections
    }

    function loadCstResultsSections() {
        cstResultsError = ""
        cstResultsMessage = ""
        cstResultsSections = []
        cstArtifactItems = []

        var payload = designController.currentCstResultsText()
        var data = {}
        try {
            data = JSON.parse(payload)
        } catch (error) {
            cstResultsError = "Unable to read CST export data"
            return
        }

        cstResultsMessage = String(data.message || "")
        cstResultsSections = data.sections || []
        cstArtifactItems = data.artifacts || []
    }

    function buildConfigField(label, value, path) {
        var spec = configFieldSpecForPath(path, value)
        var fieldType = spec.type
        var fieldValue = value
        var fieldOptions = spec.options

        if (fieldType === "enum") {
            fieldValue = value === undefined || value === null ? "" : String(value)
        } else if (fieldType === "array") {
            if (Array.isArray(value)) {
                fieldValue = value.join(", ")
            } else if (value === undefined || value === null) {
                fieldValue = ""
            } else {
                fieldValue = String(value)
            }
        } else if (fieldType === "bool") {
            if (typeof value === "boolean") {
                fieldValue = value
            } else {
                fieldValue = String(value || "").toLowerCase() === "true"
            }
        } else if (fieldType === "number") {
            fieldValue = value === undefined || value === null ? "" : String(value)
        } else if (value === null || value === undefined) {
            fieldValue = ""
        } else {
            fieldValue = String(value)
        }

        return {
            "label": prettyLabel(label),
            "path": path,
            "type": fieldType,
            "value": fieldValue,
            "options": fieldOptions
        }
    }

    function configFieldSpecForPath(path, value) {
        var enumOptions = enumOptionsForPath(path, value)
        if (enumOptions.length > 0) {
            return {"type": "enum", "options": enumOptions}
        }

        var boolPaths = [
            "cst.auto_save",
            "ui.auto_connect",
            "ui.show_advanced",
            "client_capabilities.supports_farfield_export",
            "client_capabilities.supports_current_distribution_export"
        ]
        if (boolPaths.indexOf(path) !== -1 || typeof value === "boolean" || /^(true|false)$/i.test(String(value || ""))) {
            return {"type": "bool", "options": []}
        }

        var numberPaths = [
            "server.timeout_sec",
            "server.retry_count",
            "server.retry_backoff",
            "cst.save_interval_sec",
            "ui.default_width",
            "ui.default_height",
            "logging.max_file_size_mb",
            "logging.backup_count",
            "client_capabilities.max_simulation_timeout_sec"
        ]
        if (numberPaths.indexOf(path) !== -1 || typeof value === "number") {
            return {"type": "number", "options": []}
        }

        if (path === "client_capabilities.export_formats" || Array.isArray(value)) {
            return {"type": "array", "options": []}
        }

        return {"type": "string", "options": []}
    }

    function enumOptionsForPath(path, value) {
        var options = []
        if (path === "ui.theme") {
            options = ["light", "dark", "system"]
        } else if (path === "logging.level") {
            options = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        }

        if (options.length === 0) {
            return options
        }

        var current = value === undefined || value === null ? "" : String(value)
        if (current.length > 0 && options.indexOf(current) === -1) {
            options.unshift(current)
        }
        return options
    }

    function optionIndex(options, value) {
        var current = String(value || "")
        for (var index = 0; index < options.length; index++) {
            if (String(options[index]) === current) {
                return index
            }
        }
        return options.length > 0 ? 0 : -1
    }

    function collectConfigFields(source, pathPrefix, fields) {
        for (var key in source) {
            var value = source[key]
            var nextPath = pathPrefix ? pathPrefix + "." + key : key
            if (value !== null && typeof value === "object" && !Array.isArray(value)) {
                collectConfigFields(value, nextPath, fields)
            } else {
                fields.push(buildConfigField(key, value, nextPath))
            }
        }
    }

    function loadConfigSections() {
        configLoadError = ""
        configSections = []
        configPageText = designController.loadConfigText()

        var config = {}
        try {
            config = JSON.parse(configPageText)
        } catch (error) {
            configLoadError = "Unable to parse config.json"
            return
        }

        var sections = []
        for (var key in config) {
            var fields = []
            var value = config[key]
            if (value !== null && typeof value === "object" && !Array.isArray(value)) {
                collectConfigFields(value, key, fields)
            } else {
                fields.push(buildConfigField(key, value, key))
            }
            sections.push({
                "title": prettyLabel(key),
                "fields": fields
            })
        }
        configSections = sections
    }

    function updateConfigField(sectionIndex, fieldIndex, value) {
        if (!configSections || !configSections[sectionIndex] || !configSections[sectionIndex].fields || !configSections[sectionIndex].fields[fieldIndex]) {
            return
        }
        configSections[sectionIndex].fields[fieldIndex].value = value
    }

    function applyPathValue(target, pathParts, value) {
        var node = target
        for (var index = 0; index < pathParts.length - 1; index++) {
            var part = pathParts[index]
            if (!node[part] || typeof node[part] !== "object" || Array.isArray(node[part])) {
                node[part] = {}
            }
            node = node[part]
        }
        node[pathParts[pathParts.length - 1]] = value
    }

    function normalizeConfigValue(field) {
        if (field.type === "bool") {
            return field.value === true || String(field.value || "").toLowerCase() === "true"
        }

        if (field.type === "number") {
            var numeric = Number(field.value)
            if (isNaN(numeric)) {
                throw new Error(field.label + " must be a number")
            }
            return numeric
        }

        if (field.type === "array") {
            var text = String(field.value || "")
            if (text.trim().length === 0) {
                return []
            }
            return text.split(",").map(function(item) { return item.trim() }).filter(function(item) { return item.length > 0 })
        }

        if (field.type === "enum") {
            return String(field.value || "")
        }

        return String(field.value || "")
    }

    function saveConfigSections() {
        try {
            var config = {}
            for (var sectionIndex = 0; sectionIndex < configSections.length; sectionIndex++) {
                var section = configSections[sectionIndex]
                var fields = section.fields || []
                for (var fieldIndex = 0; fieldIndex < fields.length; fieldIndex++) {
                    var field = fields[fieldIndex]
                    applyPathValue(config, String(field.path).split("."), normalizeConfigValue(field))
                }
            }
            var serialized = JSON.stringify(config, null, 2)
            designController.saveConfigText(serialized)
            configPageText = serialized
            configLoadError = ""
            loadConfigSections()
        } catch (error) {
            configLoadError = error.message
        }
    }

    function sendMessage() {
        var text = chatInputField.text.trim()
        if (text.length === 0) {
            return
        }
        chatInputField.text = ""

        if (text.startsWith("/")) {
            designController.handleCommand(text)
        } else {
            designController.sendChatMessage(text, "speed")
        }
    }

    function feedbackPayload() {
        return JSON.stringify({
            "actual_frequency": actualFrequencyValue.text,
            "actual_bandwidth": actualBandwidthValue.text,
            "actual_gain": gainValue.text,
            "actual_vswr": vswrValue.text,
            "farfield": farfieldValue.text
        })
    }

    function loadHistorySessions() {
        historyLoadError = ""
        historyCache = []

        var payload = designController.historyDetails()
        var sessions = []
        try {
            sessions = JSON.parse(payload)
        } catch (error) {
            historyLoadError = "Unable to load session history"
            return
        }

        if (!sessions || sessions.length === 0) {
            historyModel.clear()
            historyLoadError = "No saved sessions yet"
            return
        }

        historyCache = sessions
        applyHistoryFilter()
    }

    function applyHistoryFilter() {
        historyModel.clear()

        var query = historySearchText.trim().toLowerCase()
        var matched = 0
        for (var index = 0; index < historyCache.length; index++) {
            var entry = historyCache[index]
            if (!showArchivedHistory && !!entry["is_archived"]) {
                continue
            }

            if (query.length > 0) {
                var haystack = String(entry["search_blob"] || "").toLowerCase()
                if (haystack.indexOf(query) === -1) {
                    continue
                }
            }

            historyModel.append(entry)
            matched += 1
        }

        if (historyCache.length > 0 && matched === 0) {
            historyLoadError = "No sessions match the current filter"
        } else {
            historyLoadError = ""
        }
    }

    function refreshHistoryAfterAction() {
        loadHistorySessions()
    }

    function openHistoryAction(actionName, sessionId, headingText) {
        pendingHistoryAction = actionName
        pendingHistorySessionId = sessionId
        pendingHistoryHeading = headingText
        historyActionPopup.open()
    }

    function confirmHistoryAction() {
        if (pendingHistoryAction === "archive") {
            designController.setSessionArchived(pendingHistorySessionId, true)
        } else if (pendingHistoryAction === "unarchive") {
            designController.setSessionArchived(pendingHistorySessionId, false)
        } else if (pendingHistoryAction === "delete") {
            designController.deleteSessionFromHistory(pendingHistorySessionId)
        }
        historyActionPopup.close()
        refreshHistoryAfterAction()
    }

    function openSessionNamePopup(mode) {
        sessionNamePopupMode = mode
        sessionNameError = ""
        sessionNameField.text = designController.currentSessionName()
        sessionNamePopup.open()
        sessionNameField.forceActiveFocus()
        sessionNameField.selectAll()
    }

    function confirmSessionName() {
        var name = sessionNameField.text.trim()
        if (name.length === 0) {
            sessionNameError = "Session name is required"
            return
        }

        designController.setSessionName(name)
        if (sessionNamePopupMode === "save") {
            designController.saveCurrentSession(name)
        }
        sessionNamePopup.close()
    }

    Component.onCompleted: {
        designController.refreshConnections()
        root.openSessionNamePopup("startup")
    }

    Rectangle {
        anchors.fill: parent
        color: "#c7c7c9"

        Connections {
            target: designController

            function onChatMessageReceived(sender, message) {
                chatModel.append({"sender": sender, "message": message})
                chatList.positionViewAtEnd()
            }

            function onStatusChanged(status) {
                root.statusText = status
            }

            function onConnectionStatusChanged(payload) {
                root.annConnected = !!payload["ann_connected"]
                root.llmConnected = !!payload["llm_connected"]
                root.cstConnected = !!payload["cst_connected"]
                root.commConnected = !!payload["comm_connected"]
            }

            function onErrorOccurred(errorMessage) {
                root.statusText = "Error: " + errorMessage
                chatModel.append({"sender": "System", "message": errorMessage})
                chatList.positionViewAtEnd()
            }

            function onDesignUpdated(data) {
                if (data["frequency_ghz"] !== undefined) {
                    frequencyField.text = Number(data["frequency_ghz"]).toFixed(2)
                }
                if (data["bandwidth_mhz"] !== undefined) {
                    bandwidthField.text = String(data["bandwidth_mhz"])
                }
                if (data["antenna_family"] !== undefined) {
                    setComboValue(antennaFamilyCombo, String(data["antenna_family"]))
                    applyFamilyDefaults(antennaFamilyCombo.currentText)
                }
                if (data["patch_shape"] !== undefined) {
                    setComboValue(patchShapeCombo, String(data["patch_shape"]))
                }
                if (data["feed_type"] !== undefined) {
                    setComboValue(feedTypeCombo, String(data["feed_type"]))
                }
                if (data["polarization"] !== undefined) {
                    setComboValue(polarizationCombo, String(data["polarization"]))
                }
                if (data["substrate_material"] !== undefined) {
                    substrateField.text = String(data["substrate_material"])
                }
                if (data["conductor_material"] !== undefined) {
                    conductorField.text = String(data["conductor_material"])
                }
            }

            function onResultReceived(result) {
                if (result["patch_width"] !== undefined) patchWidthValue.text = String(result["patch_width"])
                if (result["patch_length"] !== undefined) patchLengthValue.text = String(result["patch_length"])
                if (result["substrate_width"] !== undefined) substrateWidthValue.text = String(result["substrate_width"])
                if (result["substrate_length"] !== undefined) substrateLengthValue.text = String(result["substrate_length"])
                if (result["feed_width"] !== undefined) feedWidthValue.text = String(result["feed_width"])
                if (result["feed_length"] !== undefined) feedLengthValue.text = String(result["feed_length"])
                if (result["actual_frequency"] !== undefined) actualFrequencyValue.text = String(result["actual_frequency"])
                if (result["actual_bandwidth"] !== undefined) actualBandwidthValue.text = String(result["actual_bandwidth"])
                if (result["farfield"] !== undefined) farfieldValue.text = String(result["farfield"])
                if (result["gain_db"] !== undefined) gainValue.text = String(result["gain_db"])
                if (result["vswr"] !== undefined) vswrValue.text = String(result["vswr"])
            }

            function onSessionRestored(payload) {
                var restored = JSON.parse(payload)
                var design = restored.design || {}
                var result = restored.result || {}
                var history = restored.chat_history || []

                substrateField.text = String(design.substrate_material || "")
                conductorField.text = String(design.conductor_material || "")
                frequencyField.text = design.frequency_ghz !== undefined ? String(design.frequency_ghz) : ""
                bandwidthField.text = design.bandwidth_mhz !== undefined ? String(design.bandwidth_mhz) : ""
                setComboValue(antennaFamilyCombo, String(design.antenna_family || "amc_patch"))
                applyFamilyDefaults(antennaFamilyCombo.currentText)
                setComboValue(patchShapeCombo, String(design.patch_shape || ""))
                setComboValue(feedTypeCombo, String(design.feed_type || ""))
                setComboValue(polarizationCombo, String(design.polarization || ""))

                chatModel.clear()
                for (var i = 0; i < history.length; i++) {
                    chatModel.append(history[i])
                }

                patchWidthValue.text = String(result.patch_width || "")
                patchLengthValue.text = String(result.patch_length || "")
                substrateWidthValue.text = String(result.substrate_width || "")
                substrateLengthValue.text = String(result.substrate_length || "")
                feedWidthValue.text = String(result.feed_width || "")
                feedLengthValue.text = String(result.feed_length || "")
                actualFrequencyValue.text = String(result.actual_frequency || "")
                actualBandwidthValue.text = String(result.actual_bandwidth || "")
                farfieldValue.text = String(result.farfield || "")
                gainValue.text = String(result.gain_db || "")
                vswrValue.text = String(result.vswr || "")
                sessionNameField.text = String(restored.session_name || designController.currentSessionName())

                if (historyOverlay.visible) {
                    root.loadHistorySessions()
                }
            }
        }

        // Menu row
        Row {
            id: menuRow
            x: 34
            y: 16
            spacing: 24

            Rectangle {
                id: sessionMenuButton
                width: 72
                height: 24
                color: "transparent"
                Text {
                    anchors.centerIn: parent
                    text: "Session"
                    font.pixelSize: 30 * 0.45
                    color: "#1f1f1f"
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: sessionPopup.open()
                }
            }

            Rectangle {
                width: 72
                height: 24
                color: "transparent"
                Text {
                    anchors.centerIn: parent
                    text: "History"
                    font.pixelSize: 30 * 0.45
                    color: "#1f1f1f"
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        root.loadHistorySessions()
                        historyOverlay.visible = true
                    }
                }
            }

            Rectangle {
                width: 72
                height: 24
                color: "transparent"
                Text {
                    anchors.centerIn: parent
                    text: "Results"
                    font.pixelSize: 30 * 0.45
                    color: "#1f1f1f"
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        root.loadCstResultsSections()
                        cstResultsPopup.open()
                    }
                }
            }

            Rectangle {
                width: 62
                height: 24
                color: "transparent"
                Text {
                    anchors.centerIn: parent
                    text: "Config"
                    font.pixelSize: 30 * 0.45
                    color: "#1f1f1f"
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        root.loadConfigSections()
                        configOverlay.visible = true
                    }
                }
            }

            Rectangle {
                width: 64
                height: 24
                color: "transparent"
                Text {
                    anchors.centerIn: parent
                    text: "Restart"
                    font.pixelSize: 30 * 0.45
                    color: "#1f1f1f"
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: designController.restartApplication()
                }
            }

            Rectangle {
                width: 84
                height: 24
                color: "transparent"
                Text {
                    anchors.centerIn: parent
                    text: "Reconnect"
                    font.pixelSize: 30 * 0.45
                    color: "#1f1f1f"
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        root.statusText = "Reconnecting services..."
                        designController.refreshConnections()
                    }
                }
            }
        }

        Popup {
            id: sessionPopup
            x: sessionMenuButton.x
            y: menuRow.y + menuRow.height + 8
            width: 210
            height: sessionMenuContent.implicitHeight + (padding * 2)
            modal: false
            focus: true
            padding: 8
            clip: true
            background: Rectangle {
                color: "#ededed"
                border.width: 1
                border.color: "#777"
            }

            Column {
                id: sessionMenuContent
                anchors.fill: parent
                spacing: 8

                Button {
                    width: parent.width
                    text: "Current State"
                    onClicked: {
                        root.loadStateSections()
                        statePopup.open()
                        sessionPopup.close()
                    }
                }

                Button {
                    width: parent.width
                    text: "Restore Latest"
                    onClicked: {
                        designController.restoreLatestSession()
                        sessionPopup.close()
                    }
                }

                Button {
                    width: parent.width
                    text: "Save Session"
                    onClicked: {
                        root.openSessionNamePopup("save")
                        sessionPopup.close()
                    }
                }

                Button {
                    width: parent.width
                    text: "Continue by ID"
                    onClicked: {
                        continueSessionPopup.open()
                        sessionPopup.close()
                    }
                }
            }
        }

        Popup {
            id: sessionNamePopup
            anchors.centerIn: Overlay.overlay
            width: 360
            height: 190
            modal: true
            focus: true
            padding: 12
            closePolicy: Popup.CloseOnEscape
            background: Rectangle {
                color: "#efefef"
                border.width: 1
                border.color: "#777"
            }

            Column {
                anchors.fill: parent
                spacing: 10

                Text {
                    text: sessionNamePopupMode === "startup" ? "Name This Session" : "Save Session"
                    font.pixelSize: 16
                    color: "#111"
                }

                Text {
                    width: parent.width
                    text: sessionNamePopupMode === "startup"
                          ? "Enter a session name now, or skip and name it later when saving."
                          : "Choose a session name before saving it to history."
                    font.pixelSize: 12
                    color: "#333"
                    wrapMode: Text.WordWrap
                }

                TextField {
                    id: sessionNameField
                    width: parent.width
                    placeholderText: "Session name"
                    onAccepted: root.confirmSessionName()
                }

                Text {
                    width: parent.width
                    visible: sessionNameError.length > 0
                    text: sessionNameError
                    font.pixelSize: 12
                    color: "#b00020"
                    wrapMode: Text.WordWrap
                }

                Row {
                    spacing: 8

                    Button {
                        text: sessionNamePopupMode === "startup" ? "Start Session" : "Save"
                        onClicked: root.confirmSessionName()
                    }

                    Button {
                        text: sessionNamePopupMode === "startup" ? "Skip for now" : "Cancel"
                        onClicked: sessionNamePopup.close()
                    }
                }
            }
        }

        Popup {
            id: continueSessionPopup
            anchors.centerIn: Overlay.overlay
            width: 320
            height: 150
            modal: true
            focus: true
            padding: 12
            background: Rectangle {
                color: "#efefef"
                border.width: 1
                border.color: "#777"
            }

            Column {
                anchors.fill: parent
                spacing: 10

                Text {
                    text: "Continue Session by ID"
                    font.pixelSize: 16
                    color: "#111"
                }

                TextField {
                    id: continueSessionIdField
                    width: parent.width
                    placeholderText: "Enter session id"
                }

                Row {
                    spacing: 8
                    Button {
                        text: "Continue"
                        onClicked: {
                            designController.continueSessionById(continueSessionIdField.text)
                            continueSessionPopup.close()
                        }
                    }
                    Button {
                        text: "Cancel"
                        onClicked: continueSessionPopup.close()
                    }
                }
            }
        }

        Popup {
            id: statePopup
            anchors.centerIn: Overlay.overlay
            width: 640
            height: 430
            modal: true
            focus: true
            padding: 12
            background: Rectangle {
                color: "#efefef"
                border.width: 1
                border.color: "#777"
            }

            Column {
                anchors.fill: parent
                spacing: 8

                Text {
                    text: "Current State"
                    font.pixelSize: 16
                    color: "#111"
                }

                Text {
                    width: parent.width
                    visible: stateLoadError.length > 0
                    text: stateLoadError
                    font.pixelSize: 12
                    color: "#b00020"
                    wrapMode: Text.WordWrap
                }

                ScrollView {
                    width: parent.width
                    height: parent.height - 48 - (stateLoadError.length > 0 ? 24 : 0)

                    Column {
                        width: statePopup.width - 40
                        spacing: 12

                        Repeater {
                            model: stateSections

                            delegate: Rectangle {
                                width: parent.width
                                color: "#f7f7f8"
                                border.width: 1
                                border.color: "#d0d4db"
                                radius: 4
                                implicitHeight: stateSectionColumn.implicitHeight + 20

                                Column {
                                    id: stateSectionColumn
                                    x: 12
                                    y: 10
                                    width: parent.width - 24
                                    spacing: 8

                                    Text {
                                        width: parent.width
                                        text: modelData.title
                                        font.pixelSize: 15
                                        font.bold: true
                                        color: "#111"
                                    }

                                    Repeater {
                                        model: modelData.fields

                                        delegate: Row {
                                            width: parent.width
                                            spacing: 12

                                            Text {
                                                width: 180
                                                text: modelData.label
                                                font.pixelSize: 12
                                                color: "#444"
                                                wrapMode: Text.WordWrap
                                            }

                                            Text {
                                                width: parent.width - 192
                                                text: modelData.value
                                                font.pixelSize: 12
                                                color: "#111"
                                                wrapMode: Text.WrapAnywhere
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        Popup {
            id: cstResultsPopup
            anchors.centerIn: Overlay.overlay
            width: 760
            height: 500
            modal: true
            focus: true
            padding: 12
            background: Rectangle {
                color: "#efefef"
                border.width: 1
                border.color: "#777"
            }

            Column {
                anchors.fill: parent
                spacing: 8

                Row {
                    width: parent.width
                    spacing: 8

                    Text {
                        width: parent.width - 250
                        text: "CST Results"
                        font.pixelSize: 16
                        color: "#111"
                    }

                    Button {
                        width: 70
                        text: "Refresh"
                        onClicked: root.loadCstResultsSections()
                    }

                    Button {
                        width: 90
                        text: "Export"
                        onClicked: designController.exportResults()
                    }

                    Button {
                        width: 60
                        text: "Close"
                        onClicked: cstResultsPopup.close()
                    }
                }

                Text {
                    width: parent.width
                    visible: cstResultsError.length > 0
                    text: cstResultsError
                    font.pixelSize: 12
                    color: "#b00020"
                    wrapMode: Text.WordWrap
                }

                Text {
                    width: parent.width
                    visible: cstResultsError.length === 0 && cstResultsMessage.length > 0
                    text: cstResultsMessage
                    font.pixelSize: 12
                    color: "#333"
                    wrapMode: Text.WordWrap
                }

                ScrollView {
                    width: parent.width
                    height: parent.height - 48 - ((cstResultsError.length > 0 || cstResultsMessage.length > 0) ? 24 : 0)

                    Column {
                        width: cstResultsPopup.width - 40
                        spacing: 12

                        Repeater {
                            model: cstResultsSections

                            delegate: Rectangle {
                                width: parent.width
                                color: "#f7f7f8"
                                border.width: 1
                                border.color: "#d0d4db"
                                radius: 4
                                implicitHeight: cstSectionColumn.implicitHeight + 20

                                Column {
                                    id: cstSectionColumn
                                    x: 12
                                    y: 10
                                    width: parent.width - 24
                                    spacing: 8

                                    Text {
                                        width: parent.width
                                        text: modelData.title
                                        font.pixelSize: 15
                                        font.bold: true
                                        color: "#111"
                                    }

                                    Repeater {
                                        model: modelData.fields

                                        delegate: Row {
                                            width: parent.width
                                            spacing: 12

                                            Text {
                                                width: 210
                                                text: modelData.label
                                                font.pixelSize: 12
                                                color: "#444"
                                                wrapMode: Text.WordWrap
                                            }

                                            Text {
                                                width: parent.width - 222
                                                text: modelData.value
                                                font.pixelSize: 12
                                                color: "#111"
                                                wrapMode: Text.WrapAnywhere
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Rectangle {
                            width: parent.width
                            color: "#f7f7f8"
                            border.width: 1
                            border.color: "#d0d4db"
                            radius: 4
                            implicitHeight: artifactSectionColumn.implicitHeight + 20

                            Column {
                                id: artifactSectionColumn
                                x: 12
                                y: 10
                                width: parent.width - 24
                                spacing: 8

                                Text {
                                    width: parent.width
                                    text: "Artifacts"
                                    font.pixelSize: 15
                                    font.bold: true
                                    color: "#111"
                                }

                                Repeater {
                                    model: cstArtifactItems

                                    delegate: Row {
                                        width: parent.width
                                        spacing: 12

                                        Text {
                                            width: 170
                                            text: modelData.label
                                            font.pixelSize: 12
                                            color: "#444"
                                            wrapMode: Text.WordWrap
                                        }

                                        Text {
                                            width: parent.width - 266
                                            text: modelData.path.length > 0 ? modelData.path : "Not available"
                                            font.pixelSize: 12
                                            color: modelData.exists ? "#111" : "#777"
                                            wrapMode: Text.WrapAnywhere
                                        }

                                        Button {
                                            width: 72
                                            text: modelData.exists ? "Open" : "Missing"
                                            enabled: modelData.exists
                                            onClicked: designController.openArtifactPath(modelData.path)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // Right metrics side panel
        Rectangle {
            id: rightPanel
            x: parent.width - 290
            y: 12
            width: 260
            height: parent.height - 24
            color: panelBg

            Column {
                anchors.fill: parent
                anchors.margins: 22
                spacing: 12

                function metricRow(label) { return label }

                Repeater {
                    model: ["Patch Width", "Patch Length", "Substrate Width", "Substrate Length", "Feed Width", "Feed Length"]
                    delegate: Row {
                        width: rightPanel.width - 44
                        spacing: 12
                        Text {
                            text: modelData
                            width: 150
                            font.pixelSize: 31 * 0.45
                            color: "#111"
                        }
                        TextField {
                            width: 52
                            height: 24
                            readOnly: true
                            text: {
                                if (modelData === "Patch Width") return patchWidthValue.text
                                if (modelData === "Patch Length") return patchLengthValue.text
                                if (modelData === "Substrate Width") return substrateWidthValue.text
                                if (modelData === "Substrate Length") return substrateLengthValue.text
                                if (modelData === "Feed Width") return feedWidthValue.text
                                return feedLengthValue.text
                            }
                            background: Rectangle { color: fieldBg }
                        }
                    }
                }

                Rectangle { width: rightPanel.width - 44; height: 1; color: "#c7c0c0" }

                Repeater {
                    model: ["Actual Frequency", "Actual Bandwidth", "Farfield", "Gain (db)", "VSWR"]
                    delegate: Row {
                        width: rightPanel.width - 44
                        spacing: 12
                        Text {
                            text: modelData
                            width: 150
                            font.pixelSize: 31 * 0.45
                            color: "#111"
                        }
                        TextField {
                            width: 52
                            height: 24
                            readOnly: true
                            text: {
                                if (modelData === "Actual Frequency") return actualFrequencyValue.text
                                if (modelData === "Actual Bandwidth") return actualBandwidthValue.text
                                if (modelData === "Farfield") return farfieldValue.text
                                if (modelData === "Gain (db)") return gainValue.text
                                return vswrValue.text
                            }
                            background: Rectangle { color: fieldBg }
                        }
                    }
                }

                Rectangle {
                    width: rightPanel.width - 44
                    height: 40
                    color: btnBg
                    anchors.horizontalCenter: parent.horizontalCenter
                    Text {
                        anchors.centerIn: parent
                        text: "Feedback"
                        font.pixelSize: 36 * 0.45
                        color: "#111"
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: designController.submitFeedback(root.feedbackPayload())
                    }
                }

                Rectangle {
                    width: rightPanel.width - 44
                    height: 40
                    color: btnBg
                    anchors.horizontalCenter: parent.horizontalCenter
                    Text {
                        anchors.centerIn: parent
                        text: "Done"
                        font.pixelSize: 36 * 0.45
                        color: "#111"
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: designController.markDone(root.feedbackPayload())
                    }
                }
            }
        }

        // Main left area width up to right panel
        Item {
            id: leftArea
            x: 34
            y: 56
            width: rightPanel.x - 56
            height: parent.height - 90

            Flickable {
                id: leftPaneScroller
                anchors.fill: parent
                clip: true
                contentWidth: width
                contentHeight: manualPage.y + manualPage.height + 16

                ScrollBar.vertical: ScrollBar {
                    policy: ScrollBar.AsNeeded
                }

                Item {
                    width: leftPaneScroller.width
                    height: leftPaneScroller.contentHeight

                    Item {
                        id: chatPage
                        x: 0
                        y: 0
                        width: parent.width
                        height: leftArea.height

                        Rectangle {
                            id: chatHistory
                            x: 0
                            y: 0
                            width: parent.width
                            height: chatPage.height - 116
                            color: chatBg

                            ListView {
                                id: chatList
                                anchors.fill: parent
                                anchors.margins: 8
                                anchors.rightMargin: 16
                                model: chatModel
                                clip: true
                                spacing: 8
                                delegate: Item {
                                    width: chatList.width
                                    height: messageCard.height + 8

                                    property bool isUserMessage: sender === "You"
                                    property bool isSystemMessage: sender === "System"
                                    property bool isAssistantMessage: sender === "Assistant"

                                    Rectangle {
                                        id: messageCard
                                        width: Math.min(chatList.width * 0.75, chatList.width - 20)
                                        height: messageColumn.implicitHeight + 24
                                        y: 0
                                        x: isUserMessage ? (chatList.width - width - 8) : 0
                                        radius: 12
                                        color: isUserMessage ? "#d4e1ff" : (isSystemMessage ? "#ffe0e0" : "#e0f7e0")
                                        border.width: 1
                                        border.color: isUserMessage ? "#a8c8ff" : (isSystemMessage ? "#ffb0b0" : "#90ee90")

                                        Column {
                                            id: messageColumn
                                            x: 12
                                            y: 12
                                            width: parent.width - 24
                                            spacing: 6

                                            Text {
                                                width: parent.width
                                                text: sender
                                                font.bold: true
                                                font.pixelSize: 28 * 0.45
                                                color: isUserMessage ? "#1b3f8b" : (isSystemMessage ? "#8c1d18" : "#145a32")
                                            }

                                            Text {
                                                width: parent.width
                                                wrapMode: Text.WordWrap
                                                text: message
                                                font.pixelSize: 30 * 0.45
                                                color: isUserMessage ? "#102a5c" : (isSystemMessage ? "#7a1813" : "#103d22")
                                            }
                                        }
                                    }
                                }

                                ScrollBar.vertical: ScrollBar {
                                    policy: ScrollBar.AsNeeded
                                }
                            }
                        }

                        Rectangle {
                            id: chatInput
                            x: 0
                            y: chatHistory.height + 8
                            width: parent.width - 110
                            height: 48
                            color: "#bea1a1"

                            TextField {
                                id: chatInputField
                                anchors.fill: parent
                                anchors.margins: 6
                                placeholderText: "Type a message..."
                                font.pixelSize: 32 * 0.45
                                color: "#111111"
                                placeholderTextColor: "#6a5454"
                                onAccepted: root.sendMessage()
                                background: Rectangle { color: "transparent" }
                            }
                        }

                        Rectangle {
                            id: sendBtn
                            x: parent.width - 90
                            y: chatHistory.height + 8
                            width: 90
                            height: 48
                            color: "#6da8f4"
                            Text {
                                anchors.centerIn: parent
                                text: "Send"
                                font.pixelSize: 38 * 0.45
                                color: "#111"
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: root.sendMessage()
                            }
                        }

                        Row {
                            id: statusRow
                            y: chatInput.y + chatInput.height + 10
                            anchors.horizontalCenter: chatInput.horizontalCenter
                            spacing: 28

                            function dotColor(name) {
                                if (name === "ANN") return root.annConnected ? "#18d818" : "#f00"
                                if (name === "LLM") return root.llmConnected ? "#18d818" : "#f00"
                                if (name === "CST") return root.cstConnected ? "#18d818" : "#f00"
                                return root.commConnected ? "#18d818" : "#f00"
                            }

                            Repeater {
                                model: ["ANN", "LLM", "CST", "COM"]
                                delegate: Row {
                                    spacing: 8
                                    Text {
                                        text: modelData
                                        font.pixelSize: 38 * 0.45
                                        color: "#111"
                                    }
                                    Rectangle {
                                        width: 15
                                        height: 15
                                        radius: 7.5
                                        color: statusRow.dotColor(modelData)
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }
                            }
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            y: statusRow.y + 30
                            text: "Scroll down for manual inputs"
                            font.pixelSize: 16 * 0.45
                            color: "#333"
                        }
                    }

                    Rectangle {
                        id: manualPage
                        x: 0
                        y: chatPage.height + 16
                        width: parent.width
                        height: 340
                        color: panelBg

                        Text {
                            x: 20
                            y: 12
                            text: "Manual Inputs"
                            font.pixelSize: 34 * 0.45
                            color: "#111"
                        }

                        Text { x: 20; y: 48; text: "Substrate Material"; font.pixelSize: 35 * 0.45; color: "#111" }
                        TextField {
                            id: substrateField
                            x: 210
                            y: 44
                            width: 170
                            height: 24
                            text: "FR4"
                            background: Rectangle { color: fieldBg }
                        }

                        Text { x: 20; y: 90; text: "Conductor Material"; font.pixelSize: 35 * 0.45; color: "#111" }
                        TextField {
                            id: conductorField
                            x: 210
                            y: 86
                            width: 170
                            height: 24
                            text: "Copper"
                            background: Rectangle { color: fieldBg }
                        }

                        Text { x: 410; y: 48; text: "Resonant Frequency (GHz)"; font.pixelSize: 35 * 0.45; color: "#111" }
                        TextField {
                            id: frequencyField
                            x: 650
                            y: 44
                            width: 130
                            height: 24
                            text: "2.45"
                            background: Rectangle { color: fieldBg }
                        }

                        Text { x: 410; y: 90; text: "Resonant Bandwidth (MHz)"; font.pixelSize: 35 * 0.45; color: "#111" }
                        TextField {
                            id: bandwidthField
                            x: 650
                            y: 86
                            width: 130
                            height: 24
                            text: "450"
                            background: Rectangle { color: fieldBg }
                        }

                        Text { x: 20; y: 130; text: "Antenna Family"; font.pixelSize: 35 * 0.45; color: "#111" }
                        ComboBox {
                            id: antennaFamilyCombo
                            x: 210
                            y: 126
                            width: 170
                            height: 24
                            model: ["amc_patch", "microstrip_patch", "wban_patch"]
                            onCurrentTextChanged: applyFamilyDefaults(currentText)
                        }

                        Text { x: 410; y: 130; text: "Patch Shape"; font.pixelSize: 35 * 0.45; color: "#111" }
                        ComboBox {
                            id: patchShapeCombo
                            x: 650
                            y: 126
                            width: 130
                            height: 24
                            model: ["auto", "rectangular", "circular"]
                        }

                        Text { x: 20; y: 172; text: "Feed Type"; font.pixelSize: 35 * 0.45; color: "#111" }
                        ComboBox {
                            id: feedTypeCombo
                            x: 210
                            y: 168
                            width: 170
                            height: 24
                            model: ["auto", "edge", "inset", "coaxial"]
                        }

                        Text { x: 410; y: 172; text: "Polarization"; font.pixelSize: 35 * 0.45; color: "#111" }
                        ComboBox {
                            id: polarizationCombo
                            x: 650
                            y: 168
                            width: 130
                            height: 24
                            model: ["linear", "circular", "dual", "unspecified"]
                        }

                        Rectangle {
                            x: 150
                            y: 230
                            width: 180
                            height: 38
                            color: btnBg
                            Text { anchors.centerIn: parent; text: "Start"; font.pixelSize: 38 * 0.45; color: "#111" }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    var payload = {
                                        "substrate_material": substrateField.text,
                                        "conductor_material": conductorField.text,
                                        "frequency_ghz": Number(frequencyField.text),
                                        "bandwidth_mhz": Number(bandwidthField.text),
                                        "antenna_family": antennaFamilyCombo.currentText,
                                        "patch_shape": patchShapeCombo.currentText,
                                        "feed_type": feedTypeCombo.currentText,
                                        "polarization": polarizationCombo.currentText
                                    }
                                    designController.updateDesignParameter(JSON.stringify(payload))
                                    designController.startDesign()
                                }
                            }
                        }

                        Rectangle {
                            x: 460
                            y: 230
                            width: 180
                            height: 38
                            color: btnBg
                            Text { anchors.centerIn: parent; text: "Clear"; font.pixelSize: 38 * 0.45; color: "#111" }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    substrateField.text = ""
                                    conductorField.text = ""
                                    frequencyField.text = ""
                                    bandwidthField.text = ""
                                    setComboValue(antennaFamilyCombo, "amc_patch")
                                    applyFamilyDefaults(antennaFamilyCombo.currentText)
                                    chatInputField.text = ""
                                    chatModel.clear()
                                    patchWidthValue.text = ""
                                    patchLengthValue.text = ""
                                    substrateWidthValue.text = ""
                                    substrateLengthValue.text = ""
                                    feedWidthValue.text = ""
                                    feedLengthValue.text = ""
                                    actualFrequencyValue.text = ""
                                    actualBandwidthValue.text = ""
                                    farfieldValue.text = ""
                                    gainValue.text = ""
                                    vswrValue.text = ""
                                    designController.clearDesign()
                                }
                            }
                        }

                        Text {
                            x: 20
                            y: 294
                            text: root.statusText
                            font.pixelSize: 18 * 0.45
                            color: "#333"
                        }
                    }
                }
            }
        }

        Rectangle {
            id: historyOverlay
            anchors.fill: parent
            visible: false
            color: "#88000000"
            z: 20

            Rectangle {
                anchors.centerIn: parent
                width: parent.width - 120
                height: parent.height - 80
                color: "#f2f2f2"

                Text {
                    x: 18
                    y: 12
                    text: "Session History (" + historyModel.count + ")"
                    font.pixelSize: 18
                    color: "#111"
                }

                Row {
                    x: 18
                    y: 44
                    width: parent.width - 124
                    spacing: 12

                    TextField {
                        id: historySearchField
                        width: parent.width - 170
                        height: 30
                        placeholderText: "Search by session ID, antenna family, or request text"
                        text: root.historySearchText
                        onTextChanged: {
                            root.historySearchText = text
                            root.applyHistoryFilter()
                        }
                    }

                    CheckBox {
                        id: showArchivedCheck
                        text: "Show archived"
                        checked: root.showArchivedHistory
                        onToggled: {
                            root.showArchivedHistory = checked
                            root.applyHistoryFilter()
                        }
                    }
                }

                Button {
                    x: parent.width - 88
                    y: 10
                    width: 70
                    height: 28
                    text: "Close"
                    onClicked: historyOverlay.visible = false
                }

                Text {
                    anchors.centerIn: parent
                    visible: historyModel.count === 0
                    text: historyLoadError
                    font.pixelSize: 15
                    color: "#444"
                }

                ListView {
                    id: historyList
                    x: 18
                    y: 84
                    width: parent.width - 36
                    height: parent.height - 102

                    visible: historyModel.count > 0
                    clip: true
                    spacing: 10
                    model: historyModel

                    delegate: Item {
                        id: historyCard
                        width: historyList.width
                        height: historyContent.implicitHeight
                        property bool expanded: false

                        Column {
                            id: historyContent
                            width: parent.width
                            spacing: 8

                            Rectangle {
                                width: parent.width
                                implicitHeight: headerRow.implicitHeight + 20
                                color: is_active ? "#dbeac3" : (is_archived ? "#ece8e3" : "#e7eaef")
                                border.width: 1
                                border.color: is_active ? "#89a85a" : (is_archived ? "#c1b5a3" : "#adb4be")
                                radius: 4

                                Row {
                                    id: headerRow
                                    x: 12
                                    y: 10
                                    width: parent.width - 24
                                    spacing: 10

                                    Item {
                                        id: summaryArea
                                        width: headerRow.width - restoreHistoryButton.width - archiveHistoryButton.width - deleteHistoryButton.width - (headerRow.spacing * 3)
                                        height: summaryColumn.implicitHeight

                                        Column {
                                            id: summaryColumn
                                            width: parent.width
                                            spacing: 4

                                            Text {
                                                width: parent.width
                                                text: heading
                                                font.pixelSize: 16
                                                font.bold: true
                                                color: "#111"
                                                wrapMode: Text.WordWrap
                                            }

                                            Text {
                                                width: parent.width
                                                text: request_preview
                                                font.pixelSize: 13
                                                color: "#333"
                                                wrapMode: Text.WordWrap
                                            }

                                            Text {
                                                width: parent.width
                                                text: (is_active ? "Active  |  " : "") + (is_archived ? "Archived  |  " : "") + session_short_id + "  |  " + status_label + "  |  Updated " + updated_label + "  |  " + (historyCard.expanded ? "Hide details" : "Show details")
                                                font.pixelSize: 12
                                                color: is_active ? "#425b1f" : "#555"
                                                wrapMode: Text.WordWrap
                                            }
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: historyCard.expanded = !historyCard.expanded
                                        }
                                    }

                                    Button {
                                        id: restoreHistoryButton
                                        width: 86
                                        height: 32
                                        text: "Restore"
                                        onClicked: {
                                            designController.restoreSessionFromHistory(session_id)
                                            historyOverlay.visible = false
                                        }
                                    }

                                    Button {
                                        id: archiveHistoryButton
                                        width: 82
                                        height: 32
                                        text: is_archived ? "Unarchive" : "Archive"
                                        onClicked: root.openHistoryAction(is_archived ? "unarchive" : "archive", session_id, heading)
                                    }

                                    Button {
                                        id: deleteHistoryButton
                                        width: 74
                                        height: 32
                                        text: "Delete"
                                        onClicked: root.openHistoryAction("delete", session_id, heading)
                                    }
                                }
                            }

                            Rectangle {
                                width: parent.width
                                visible: historyCard.expanded
                                height: historyCard.expanded ? detailsColumn.implicitHeight + 20 : 0
                                color: is_active ? "#f2f8e8" : "#f7f7f8"
                                border.width: 1
                                border.color: is_active ? "#b7cc8f" : "#d0d4db"
                                radius: 4

                                Column {
                                    id: detailsColumn
                                    x: 12
                                    y: 10
                                    width: parent.width - 24
                                    spacing: 6

                                    Text {
                                        width: parent.width
                                        text: "Session ID: " + session_id
                                        font.pixelSize: 12
                                        color: "#222"
                                        wrapMode: Text.WrapAnywhere
                                    }

                                    Text {
                                        width: parent.width
                                        text: "Created: " + created_label + "  |  Stage: " + current_stage + "  |  Iteration: " + iteration_count
                                        font.pixelSize: 12
                                        color: "#333"
                                        wrapMode: Text.WordWrap
                                    }

                                    Text {
                                        width: parent.width
                                        text: "Chats: " + chat_count + "  |  Results: " + result_count + "  |  Commands: " + command_count
                                        font.pixelSize: 12
                                        color: "#333"
                                        wrapMode: Text.WordWrap
                                    }

                                    Text {
                                        width: parent.width
                                        visible: trace_id.length > 0 || design_id.length > 0
                                        text: "Trace ID: " + (trace_id.length > 0 ? trace_id : "-") + "  |  Design ID: " + (design_id.length > 0 ? design_id : "-")
                                        font.pixelSize: 12
                                        color: "#333"
                                        wrapMode: Text.WrapAnywhere
                                    }

                                    Text {
                                        width: parent.width
                                        visible: actual_frequency.length > 0 || actual_bandwidth.length > 0 || actual_gain.length > 0 || actual_vswr.length > 0
                                        text: "Latest result: "
                                              + (actual_frequency.length > 0 ? ("Freq " + actual_frequency + "  ") : "")
                                              + (actual_bandwidth.length > 0 ? ("BW " + actual_bandwidth + "  ") : "")
                                              + (actual_gain.length > 0 ? ("Gain " + actual_gain + "  ") : "")
                                              + (actual_vswr.length > 0 ? ("VSWR " + actual_vswr) : "")
                                        font.pixelSize: 12
                                        color: "#333"
                                        wrapMode: Text.WordWrap
                                    }

                                    Text {
                                        width: parent.width
                                        visible: user_request.length > 0
                                        text: "Request: " + user_request
                                        font.pixelSize: 12
                                        color: "#222"
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }
                    }
                }

                Popup {
                    id: historyActionPopup
                    anchors.centerIn: Overlay.overlay
                    width: 420
                    height: 170
                    modal: true
                    focus: true
                    padding: 12
                    background: Rectangle {
                        color: "#efefef"
                        border.width: 1
                        border.color: "#777"
                    }

                    Column {
                        anchors.fill: parent
                        spacing: 12

                        Text {
                            width: parent.width
                            text: pendingHistoryAction === "delete"
                                  ? "Delete session from history?"
                                  : (pendingHistoryAction === "unarchive" ? "Unarchive session?" : "Archive session in history?")
                            font.pixelSize: 16
                            color: "#111"
                            wrapMode: Text.WordWrap
                        }

                        Text {
                            width: parent.width
                            text: pendingHistoryHeading
                            font.pixelSize: 13
                            color: "#333"
                            wrapMode: Text.WordWrap
                        }

                        Text {
                            width: parent.width
                            text: pendingHistoryAction === "delete"
                                ? "This removes the saved session from local history."
                                : (pendingHistoryAction === "unarchive"
                                 ? "This makes the session visible in the default history list again."
                                 : "This keeps the session but hides it from the default history list.")
                            font.pixelSize: 12
                            color: "#444"
                            wrapMode: Text.WordWrap
                        }

                        Row {
                            spacing: 8

                            Button {
                                text: pendingHistoryAction === "delete" ? "Delete" : (pendingHistoryAction === "unarchive" ? "Unarchive" : "Archive")
                                onClicked: root.confirmHistoryAction()
                            }

                            Button {
                                text: "Cancel"
                                onClicked: historyActionPopup.close()
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            id: configOverlay
            anchors.fill: parent
            visible: false
            color: "#88000000"
            z: 21

            Rectangle {
                anchors.centerIn: parent
                width: parent.width - 120
                height: parent.height - 80
                color: "#f2f2f2"

                Text {
                    x: 18
                    y: 12
                    text: "Config Editor (config.json)"
                    font.pixelSize: 18
                    color: "#111"
                }

                Row {
                    x: parent.width - 244
                    y: 10
                    spacing: 8

                    Button {
                        width: 70
                        height: 28
                        text: "Reload"
                        onClicked: {
                            root.loadConfigSections()
                        }
                    }

                    Button {
                        width: 70
                        height: 28
                        text: "Save"
                        onClicked: {
                            root.saveConfigSections()
                        }
                    }

                    Button {
                        width: 70
                        height: 28
                        text: "Close"
                        onClicked: configOverlay.visible = false
                    }
                }

                Text {
                    x: 18
                    y: 48
                    width: parent.width - 36
                    visible: configLoadError.length > 0
                    text: configLoadError
                    font.pixelSize: 12
                    color: "#b00020"
                    wrapMode: Text.WordWrap
                }

                ScrollView {
                    x: 18
                    y: configLoadError.length > 0 ? 72 : 48
                    width: parent.width - 36
                    height: parent.height - (configLoadError.length > 0 ? 90 : 66)

                    Column {
                        width: configOverlay.width - 180
                        spacing: 12

                        Repeater {
                            model: configSections

                            delegate: Rectangle {
                                width: parent.width
                                color: "#f7f7f8"
                                border.width: 1
                                border.color: "#d0d4db"
                                radius: 4
                                property int sectionIndex: index
                                implicitHeight: configSectionColumn.implicitHeight + 20

                                Column {
                                    id: configSectionColumn
                                    x: 12
                                    y: 10
                                    width: parent.width - 24
                                    spacing: 8

                                    Text {
                                        width: parent.width
                                        text: modelData.title
                                        font.pixelSize: 15
                                        font.bold: true
                                        color: "#111"
                                    }

                                    Repeater {
                                        model: modelData.fields

                                        delegate: Row {
                                            width: parent.width
                                            spacing: 12
                                            property int fieldIndex: index

                                            Text {
                                                width: 210
                                                text: modelData.label
                                                font.pixelSize: 12
                                                color: "#444"
                                                wrapMode: Text.WordWrap
                                            }

                                            TextField {
                                                width: parent.width - 222
                                                visible: modelData.type !== "bool" && modelData.type !== "enum"
                                                text: String(modelData.value)
                                                placeholderText: modelData.type === "array" ? "Comma separated values" : ""
                                                background: Rectangle {
                                                    color: "#ececec"
                                                    border.width: 1
                                                    border.color: "#b8bec8"
                                                }
                                                onTextEdited: root.updateConfigField(sectionIndex, fieldIndex, text)
                                            }

                                            ComboBox {
                                                id: configEnumEditor
                                                width: parent.width - 222
                                                visible: modelData.type === "enum"
                                                model: modelData.options
                                                currentIndex: root.optionIndex(modelData.options, modelData.value)

                                                contentItem: Text {
                                                    leftPadding: 10
                                                    rightPadding: 28
                                                    text: configEnumEditor.displayText
                                                    font.pixelSize: 12
                                                    color: "#111111"
                                                    verticalAlignment: Text.AlignVCenter
                                                    elide: Text.ElideRight
                                                }

                                                background: Rectangle {
                                                    color: "#ececec"
                                                    border.width: 1
                                                    border.color: "#b8bec8"
                                                }

                                                delegate: ItemDelegate {
                                                    width: configEnumEditor.width
                                                    highlighted: configEnumEditor.highlightedIndex === index
                                                    background: Rectangle {
                                                        color: highlighted ? "#6da8f4" : "#ffffff"
                                                    }
                                                    contentItem: Text {
                                                        text: modelData
                                                        font.pixelSize: 12
                                                        color: highlighted ? "#ffffff" : "#111111"
                                                        verticalAlignment: Text.AlignVCenter
                                                    }
                                                }

                                                popup: Popup {
                                                    y: configEnumEditor.height - 1
                                                    width: configEnumEditor.width
                                                    padding: 1
                                                    implicitHeight: Math.min(contentItem.implicitHeight + 2, 180)

                                                    contentItem: ListView {
                                                        clip: true
                                                        implicitHeight: contentHeight
                                                        model: configEnumEditor.popup.visible ? configEnumEditor.delegateModel : null
                                                        currentIndex: configEnumEditor.highlightedIndex
                                                        ScrollIndicator.vertical: ScrollIndicator {}
                                                    }

                                                    background: Rectangle {
                                                        color: "#ffffff"
                                                        border.width: 1
                                                        border.color: "#9ba5b4"
                                                    }
                                                }

                                                onActivated: root.updateConfigField(sectionIndex, fieldIndex, currentText)
                                            }

                                            CheckBox {
                                                width: parent.width - 222
                                                visible: modelData.type === "bool"
                                                checked: !!modelData.value
                                                text: checked ? "Enabled" : "Disabled"
                                                onToggled: root.updateConfigField(sectionIndex, fieldIndex, checked)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Text {
        id: patchWidthValue
        visible: false
        text: ""
    }
    Text {
        id: patchLengthValue
        visible: false
        text: ""
    }
    Text {
        id: substrateWidthValue
        visible: false
        text: ""
    }
    Text {
        id: substrateLengthValue
        visible: false
        text: ""
    }
    Text {
        id: feedWidthValue
        visible: false
        text: ""
    }
    Text {
        id: feedLengthValue
        visible: false
        text: ""
    }
    Text {
        id: actualFrequencyValue
        visible: false
        text: ""
    }
    Text {
        id: actualBandwidthValue
        visible: false
        text: ""
    }
    Text {
        id: farfieldValue
        visible: false
        text: ""
    }
    Text {
        id: gainValue
        visible: false
        text: ""
    }
    Text {
        id: vswrValue
        visible: false
        text: ""
    }
}
