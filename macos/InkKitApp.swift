import AppKit
import Foundation
import SwiftUI

// A developer preview for explicit current-card sessions and synthetic workspaces.
enum SettingValue: Codable, Equatable, Hashable {
    case flag(Bool)
    case number(Int)
    case text(String)

    init(from decoder: Decoder) throws {
        let value = try decoder.singleValueContainer()
        if let flag = try? value.decode(Bool.self) { self = .flag(flag) }
        else if let integer = try? value.decode(Int.self) { self = .number(integer) }
        else { self = .text(try value.decode(String.self)) }
    }

    func encode(to encoder: Encoder) throws {
        var value = encoder.singleValueContainer()
        switch self {
        case .flag(let boolean): try value.encode(boolean)
        case .number(let integer): try value.encode(integer)
        case .text(let string): try value.encode(string)
        }
    }

    var display: String {
        switch self {
        case .flag(let value): return value ? "On" : "Off"
        case .number(let value): return String(value)
        case .text(let value): return value.isEmpty ? "Empty" : value
        }
    }
    var integer: Int { if case .number(let value) = self { return value }; return 0 }
    var string: String { if case .text(let value) = self { return value }; return "" }
}

struct FieldDescriptor: Decodable, Identifiable {
    let key: String
    let label: String
    let group: String
    let kind: String
    let minimum: Int
    let maximum: Int
    let choices: [[SettingValue]]
    let readonly: String
    let section: String
    let step: Int
    var id: String { key }
}

struct SnapshotToken: Codable, Equatable {
    let root: [UInt64]
    let directory: [UInt64]
    let file: [UInt64]?
    let sha256: String?
    let mtime_ns: Int64?
    let size: Int
    let store: String
    enum CodingKeys: String, CodingKey { case root, directory, file, sha256, mtime_ns, size, store }
    func encode(to encoder: Encoder) throws {
        var values = encoder.container(keyedBy: CodingKeys.self)
        try values.encode(root, forKey: .root)
        try values.encode(directory, forKey: .directory)
        try values.encode(file, forKey: .file)
        try values.encode(sha256, forKey: .sha256)
        try values.encode(mtime_ns, forKey: .mtime_ns)
        try values.encode(size, forKey: .size)
        try values.encode(store, forKey: .store)
    }
}

struct StoreInfo: Decodable, Identifiable { let id: String; let label: String }

struct ReaderProfile: Decodable, Identifiable {
    let id: String
    let label: String
    let capabilities: [String]
}
struct FirmwareProfile: Decodable, Identifiable {
    let id: String
    let firmware: String
    let upstream_commit: String
    let sdk_commit: String
    let models: [ReaderProfile]
}
struct ProfileCatalog: Decodable {
    let profiles: [FirmwareProfile]
    let unknown_policy: String
}

func isConfigurationGroupVisible(_ group: String, capabilities: [String]) -> Bool {
    group != "frontlight" || capabilities.contains("frontlight")
}

struct Snapshot: Decodable {
    let model: String
    let capabilities: [String]
    let store: String
    let stores: [StoreInfo]
    let label: String
    let firmware: String
    let has_plaintext: Bool
    let profile: String
    let synthetic: Bool
    let fields: [FieldDescriptor]
    let values: [String: SettingValue]
    let token: SnapshotToken
}

struct Difference: Decodable, Identifiable {
    let key: String
    let label: String
    let before: SettingValue
    let after: SettingValue
    var id: String { key }

    func formatted(_ value: SettingValue, fields: [FieldDescriptor]) -> String {
        if case .text(let text) = value, text.isEmpty {
            if key == "deviceName" { return "Hardware default" }
            if key == "serverUrl" { return "Firmware default" }
            if key == "sdFontFamilyName" || key == "dictionaryFont" { return "Built-in / reader default" }
            return "Empty"
        }
        if key == "sleepTimeoutMinutes", value.integer == 31 { return "Never" }
        if let field = fields.first(where: { $0.key == key }) {
            if field.kind == "enum", let label = field.choices.first(where: { $0.first == value })?.last { return label.display }
            if field.kind == "toggle", case .number(let number) = value { return number == 1 ? "On" : "Off" }
            if field.kind == "time" { return value.integer == 65535 ? "Unset" : String(format: "%02d:%02d", value.integer / 60, value.integer % 60) }
            if field.kind == "timezone" {
                let offset = (value.integer - 48) * 15
                return String(format: "UTC%@%02d:%02d", offset < 0 ? "−" : "+", abs(offset) / 60, abs(offset) % 60)
            }
        }
        if key == "lineHeightPercent" { return value.display + "%" }
        return value.display
    }
}

struct BackupEntry: Decodable, Identifiable {
    let id: String
    let created: TimeInterval
    let state: String
    let kind: String
    let model: String
    let firmware: String?
    let reason: String
    let store: String?
    let scope: String?
    let can_restore: Bool
    let can_delete: Bool
    let checksum: String
    var date: Date { Date(timeIntervalSince1970: created) }
    var scopeLabel: String { kind == "complete" ? "All configurations" : "Legacy single file · \(scope ?? "Configuration")" }
    var reasonLabel: String {
        switch reason {
        case "before_apply": return "Before applying changes"
        case "before_restore": return "Before restoring configurations"
        case "legacy": return "Older single-file backup"
        default: return "Manual backup"
        }
    }
}
struct SnapshotMutation: Decodable {
    let changed: Bool?
    let created: Bool?
    let deleted: Bool?
    let backup_id: String?
}

struct HelperRequest: Encodable {
    var protocolVersion = 2
    let action: String
    var root: String? = nil
    var expected: SnapshotToken? = nil
    var changes: [String: SettingValue]? = nil
    var backup_id: String? = nil
    var store: String? = nil
    var model: String? = nil
    var firmware: String? = nil
    var confirmed: Bool? = nil
    var allow_plaintext: Bool? = nil
    var expected_stores: [String: SnapshotToken]? = nil
    var backup_sha256: String? = nil
    var checksum: String? = nil
    enum CodingKeys: String, CodingKey {
        case protocolVersion = "protocol"
        case action, root, expected, changes, backup_id, store, model, firmware, confirmed, allow_plaintext, expected_stores, backup_sha256, checksum
    }
}

struct HelperFailure: Decodable, LocalizedError {
    let code: String
    let message: String
    var errorDescription: String? { message }
}

struct Envelope<T: Decodable>: Decodable {
    let protocolVersion: Int
    let ok: Bool
    let data: T?
    let error: HelperFailure?
    enum CodingKeys: String, CodingKey {
        case protocolVersion = "protocol"
        case ok, data, error
    }
}

struct PlanResult: Decodable {
    let differences: [Difference]
    let requires_plaintext: Bool
    let fields: [FieldDescriptor]?
    let expectedStores: [String: SnapshotToken]?
    let backup_sha256: String?
    enum CodingKeys: String, CodingKey {
        case differences, requires_plaintext, fields, backup_sha256
        case expectedStores = "expected"
    }
}
struct EjectResult: Decodable { let ejected: Bool }
struct LocationResult: Decodable { let path: String }

struct DemoResult: Decodable { let root: String; let snapshot: Snapshot }
struct WriteResult: Decodable { let changed: Bool; let backup_id: String?; let snapshot: Snapshot }
struct RuntimeCheck: Decodable {
    let complete_plan: PlanResult
    let complete_created: SnapshotMutation
    let complete_restored: SnapshotMutation
    let complete_deleted: SnapshotMutation
    let complete_roundtrip: Bool
    let complete_backups: [BackupEntry]
    let catalog: ProfileCatalog
    let synthetic_roundtrip: Bool
    let isolated_site: Bool
    let runtime_paths_contained: Bool
    let prefix: String
    let snapshot: Snapshot
    let differences: [Difference]
    let store_snapshots: [Snapshot]
    let identity_tokens: [SnapshotToken]
}

enum Backend {
    static var resources: URL { Bundle.main.resourceURL! }
    static var runtime: URL { resources.appendingPathComponent("runtime", isDirectory: true) }

    static var version: String {
        guard let value = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String
        else { return "Unknown" }
        return value
    }

    static func execute(_ input: Data, selfTest: Bool = false) throws -> Data {
        guard input.count <= 65536 else {
            throw HelperFailure(code: "request_size", message: "Too many changes. Apply a smaller group of settings.")
        }
        let process = Process()
        let stdin = Pipe()
        let stdout = Pipe()
        process.executableURL = runtime.appendingPathComponent("bin/python3")
        process.arguments = ["-s", "-S", "-B", "-X", "utf8",
                             resources.appendingPathComponent("core/inkkit_helper.py").path]
        if selfTest { process.arguments!.append("--self-test") }
        process.currentDirectoryURL = resources.appendingPathComponent("core", isDirectory: true)
        // Do not inherit PYTHONPATH, DYLD overrides, user site packages or shell config.
        process.environment = ["PYTHONHOME": runtime.path, "TMPDIR": NSTemporaryDirectory(),
                               "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"]
        process.standardInput = stdin
        process.standardOutput = stdout
        process.standardError = FileHandle.nullDevice
        do { try process.run() }
        catch { throw HelperFailure(code: "helper_launch", message: "The bundled helper could not start. Rebuild the preview app.") }
        let timeout = DispatchWorkItem { if process.isRunning { process.terminate() } }
        DispatchQueue.global().asyncAfter(deadline: .now() + 120, execute: timeout)
        defer { timeout.cancel() }
        do {
            try stdin.fileHandleForWriting.write(contentsOf: input)
            try stdin.fileHandleForWriting.close()
            var output = Data()
            while let chunk = try stdout.fileHandleForReading.read(upToCount: 8192), !chunk.isEmpty {
                output.append(chunk)
                if output.count > 1048576 {
                    throw HelperFailure(code: "helper_output", message: "The helper response exceeded its limit.")
                }
            }
            process.waitUntilExit()
            guard process.terminationReason == .exit, [0, 1].contains(process.terminationStatus), !output.isEmpty else {
                throw HelperFailure(code: "helper_exit", message: "The helper stopped. Reload and review the workspace backups.")
            }
            return output
        } catch {
            if process.isRunning { process.terminate() }
            process.waitUntilExit()
            throw error
        }
    }
}

@MainActor
final class PreviewModel: ObservableObject {
    @Published var snapshot: Snapshot?
    @Published var draft: [String: SettingValue] = [:]
    @Published var backups: [BackupEntry] = []
    @Published var busy = false
    @Published var errorMessage: String?
    @Published var status = "Open your SD card or explore an example reader."
    @Published var differences: [Difference] = []
    @Published var reviewFields: [FieldDescriptor] = []
    @Published var showingReview = false
    @Published var requiresPlaintext = false
    @Published var plaintextConsent = false
    @Published var catalog: ProfileCatalog?
    @Published var chosenProfile = ""
    @Published var chosenModel = ""
    var currentProfile: FirmwareProfile? { catalog?.profiles.first { $0.id == chosenProfile } }
    var availableModels: [ReaderProfile] { currentProfile?.models ?? [] }
    var selectedFirmware: String { currentProfile?.firmware ?? "" }
    @Published var sessionGeneration = 0
    private var root: String?
    private var reviewedChanges: [String: SettingValue] = [:]
    private var reviewedBackup: String?
    private var reviewedComplete: BackupEntry?
    private var reviewedExpected: [String: SnapshotToken]?
    private var reviewedChecksum: String?
    var store: String { snapshot?.store ?? "settings" }
    var isCard: Bool { snapshot?.synthetic == false }
    var dirty: [String: SettingValue] { draft.filter { snapshot?.values[$0.key] != $0.value } }
    var isRestoring: Bool { reviewedBackup != nil || reviewedComplete != nil }
    var validDraft: Bool {
        for field in snapshot?.fields ?? [] where dirty[field.key] != nil {
            if field.kind == "text" || field.kind == "secret" {
                let value = draft[field.key]?.string ?? ""
                if value.utf8.count > field.maximum || value.contains("\0") { return false }
                if field.key == "deviceName" && value.utf8.count == 1 { return false }
            }
        }
        return true
    }

    private func request<T: Decodable>(_ request: HelperRequest) async throws -> T {
        let input = try JSONEncoder().encode(request)
        let output = try await Task.detached(priority: .userInitiated) { try Backend.execute(input) }.value
        let response = try JSONDecoder().decode(Envelope<T>.self, from: output)
        guard response.protocolVersion == 2 else {
            throw HelperFailure(code: "protocol", message: "The app and helper versions do not match. Rebuild the app.")
        }
        guard response.ok, let data = response.data else {
            throw response.error ?? HelperFailure(code: "helper", message: "The helper could not complete the operation.")
        }
        return data
    }
    private func report(_ error: Error) {
        if error is DecodingError {
            errorMessage = "The app could not read the helper response. Reopen the card and review its backups. If this repeats, rebuild InkKit."
        } else {
            errorMessage = (error as? HelperFailure)?.message ?? "The operation stopped. Reload and review the retained backups before retrying."
        }
    }
    private func install(_ snapshot: Snapshot) {
        self.snapshot = snapshot
        self.draft = snapshot.values
        chosenModel = snapshot.model
    }
    func loadProfiles() async {
        guard catalog == nil, !busy else { return }
        busy = true
        defer { busy = false }
        do {
            let fresh: ProfileCatalog = try await request(HelperRequest(action: "profiles.describe"))
            guard let first = fresh.profiles.first, let reader = first.models.first else {
                throw HelperFailure(code: "profile", message: "No reviewed configuration profile is bundled. Rebuild InkKit.")
            }
            catalog = fresh
            chosenProfile = first.id
            chosenModel = reader.id
        } catch { report(error) }
    }
    func createDemo() async {
        guard !busy, dirty.isEmpty else { return }
        busy = true
        defer { busy = false }
        do {
            let result: DemoResult = try await request(HelperRequest(action: "demo.create", model: chosenModel))
            sessionGeneration += 1
            root = result.root
            install(result.snapshot)
            backups = []
            status = "Synthetic demo ready. Changes affect only invented data."
        } catch { report(error) }
    }
    func openCard(path: String, model: String, firmware: String, confirmed: Bool) async {
        guard !busy, dirty.isEmpty else { return }
        busy = true
        status = "Confirming the selected card and firmware profile…"
        defer { busy = false }
        do {
            let result: DemoResult = try await request(HelperRequest(action: "volume.open", root: path,
                model: model, firmware: firmware, confirmed: confirmed))
            sessionGeneration += 1
            root = result.root
            install(result.snapshot)
            try await fetchBackups()
            status = "Card opened. Model and firmware are user-confirmed; no settings have been written."
        } catch { report(error) }
    }
    func discard() { if let snapshot { draft = snapshot.values }; status = "Draft changes discarded." }
    func loadStore(_ store: String) async {
        guard !busy, dirty.isEmpty, let root else { return }
        busy = true
        defer { busy = false }
        do {
            let fresh: Snapshot = try await request(HelperRequest(action: "config.read", root: root, store: store))
            install(fresh)
            try await fetchBackups()
            status = "Configuration loaded. Edits stay in a draft until reviewed and applied."
        } catch { report(error) }
    }
    func reload() async { await loadStore(store) }
    private func fetchBackups() async throws {
        backups = try await request(HelperRequest(action: "snapshots.list", root: root))
    }
    func loadBackups() async {
        guard !busy, dirty.isEmpty else { return }
        busy = true
        defer { busy = false }
        do {
            try await fetchBackups()
            status = "Local backups, newest first. Complete backups cover all six global configuration stores."
        } catch { report(error) }
    }
    func backupNow() async {
        guard !busy, dirty.isEmpty, let root else { return }
        busy = true
        defer { busy = false }
        do {
            let result: SnapshotMutation = try await request(HelperRequest(action: "snapshots.create", root: root))
            guard result.created == true else { throw HelperFailure(code: "snapshot", message: "The complete backup was not confirmed.") }
            try await fetchBackups()
            status = "All configurations backed up and checksums verified on this Mac. The card was not changed."
        } catch { report(error) }
    }
    func deleteBackup(_ backup: BackupEntry) async {
        guard !busy, dirty.isEmpty, backup.can_delete else { return }
        busy = true
        defer { busy = false }
        do {
            let action = backup.kind == "complete" ? "snapshots.delete" : "snapshots.delete_legacy"
            let result: SnapshotMutation = try await request(HelperRequest(action: action, root: root,
                backup_id: backup.id, store: backup.store, checksum: backup.checksum))
            guard result.deleted == true else { throw HelperFailure(code: "snapshot", message: "Backup deletion was not confirmed.") }
            try await fetchBackups()
            status = "The selected local backup was deleted."
        } catch { report(error) }
    }
    func review(backup: BackupEntry? = nil) async {
        guard !busy, dirty.isEmpty || backup == nil, let root, snapshot != nil else { return }
        busy = true
        defer { busy = false }
        do {
            reviewedComplete = nil
            reviewedExpected = nil
            reviewedChecksum = nil
            reviewedBackup = nil
            reviewFields = []
            reviewedChanges = dirty
            plaintextConsent = false
            let plan: PlanResult
            if let backup, backup.kind == "complete" {
                plan = try await request(HelperRequest(action: "snapshots.preview_restore", root: root, backup_id: backup.id))
                reviewedComplete = backup
                reviewedExpected = plan.expectedStores
                reviewedChecksum = plan.backup_sha256
                reviewFields = plan.fields ?? []
            } else if let backup {
                let category = backup.store ?? "settings"
                let fresh: Snapshot = try await request(HelperRequest(action: "config.read", root: root, store: category))
                install(fresh)
                reviewedBackup = backup.id
                plan = try await request(HelperRequest(action: "config.restore_preview", root: root,
                    expected: fresh.token, backup_id: backup.id, store: category))
            } else {
                plan = try await request(HelperRequest(action: "config.preview", root: root,
                    expected: snapshot!.token, changes: reviewedChanges, store: store))
            }
            differences = plan.differences
            requiresPlaintext = plan.requires_plaintext
            if differences.isEmpty { status = "Configurations already match. No files were changed." }
            else { showingReview = true }
        } catch { report(error) }
    }
    func confirmReview() async {
        guard !busy, !requiresPlaintext || plaintextConsent, let root, let snapshot else { return }
        busy = true
        status = "Backing up, applying and verifying the configuration…"
        defer { busy = false; showingReview = false; plaintextConsent = false; reviewedChanges = [:]; reviewedComplete = nil; reviewedExpected = nil; reviewedChecksum = nil }
        do {
            if let backup = reviewedComplete {
                guard let expected = reviewedExpected, let checksum = reviewedChecksum else {
                    throw HelperFailure(code: "snapshot", message: "Review the complete backup again before restoring.")
                }
                let result: SnapshotMutation = try await request(HelperRequest(action: "snapshots.restore", root: root,
                    backup_id: backup.id, allow_plaintext: plaintextConsent, expected_stores: expected, backup_sha256: checksum))
                let fresh: Snapshot = try await request(HelperRequest(action: "config.read", root: root, store: "settings"))
                install(fresh)
                try await fetchBackups()
                status = result.changed == true ? "All configurations restored and read back. The previous complete state is retained in Backups." : "All configurations already match the backup."
                return
            }
            let result: WriteResult
            if let backup = reviewedBackup {
                result = try await request(HelperRequest(action: "config.restore", root: root,
                    expected: snapshot.token, backup_id: backup, store: store, allow_plaintext: plaintextConsent))
            } else {
                result = try await request(HelperRequest(action: "config.apply", root: root,
                    expected: snapshot.token, changes: reviewedChanges, store: store, allow_plaintext: plaintextConsent))
            }
            install(result.snapshot)
            try await fetchBackups()
            status = reviewedBackup != nil ? "Original configuration restored and read back successfully." :
                "Configuration backed up, applied and verified. Eject before removing your card."
            if result.snapshot.has_plaintext { status += " Plaintext credentials remain until CrossInk loads and successfully resaves them." }
        } catch { report(error) }
    }
    func eject() async {
        guard !busy, dirty.isEmpty, isCard, let root else { return }
        busy = true
        defer { busy = false }
        do {
            let result: EjectResult = try await request(HelperRequest(action: "volume.eject", root: root))
            if result.ejected {
                self.root = nil; snapshot = nil; draft = [:]; backups = []
                status = "Card safely ejected. You may remove it and check the settings in your reader."
            }
        } catch { report(error) }
    }
    func revealBackups() async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        do {
            let result: LocationResult = try await request(HelperRequest(action: "snapshots.location", root: root))
            NSWorkspace.shared.selectFile(nil, inFileViewerRootedAtPath: result.path)
        } catch { report(error) }
    }
    func addEntry() {
        guard let field = snapshot?.fields.first(where: { $0.key.hasSuffix(".enabled") && draft[$0.key]?.integer == 0 }) else { return }
        draft[field.key] = .number(1)
    }
    func removeEntry(_ section: String) {
        for field in snapshot?.fields.filter({ $0.section == section }) ?? [] {
            draft[field.key] = snapshot?.values[field.key]
            if field.key.hasSuffix(".enabled") { draft[field.key] = .number(0) }
        }
    }
}

enum PreviewSection: String, CaseIterable, Identifiable {
    case overview = "Overview", display = "Display", reading = "Reading", library = "Library"
    case controls = "Controls", frontlight = "Frontlight", status = "Status bars", device = "Device"
    case wifi = "Wi-Fi", opds = "OPDS", koreader = "Reading sync", ttf = "Font rendering", dictionary = "Dictionary", backups = "Backups"
    var id: String { rawValue }
    var store: String {
        switch self {
        case .wifi: return "wifi"
        case .opds: return "opds"
        case .koreader: return "koreader"
        case .ttf: return "ttf"
        case .dictionary: return "dictionary"
        default: return "settings"
        }
    }
    var group: String {
        switch self {
        case .display: return "display"
        case .reading: return "reading"
        case .library: return "library"
        case .controls: return "controls"
        case .frontlight: return "frontlight"
        case .status: return "status"
        default: return "device"
        }
    }
    var icon: String {
        switch self {
        case .overview: return "externaldrive"
        case .display: return "circle.lefthalf.filled"
        case .reading: return "textformat.size"
        case .library: return "books.vertical"
        case .controls: return "button.programmable"
        case .frontlight: return "light.max"
        case .status: return "rectangle.topthird.inset.filled"
        case .device: return "slider.horizontal.3"
        case .wifi: return "wifi"
        case .opds: return "network"
        case .koreader: return "arrow.triangle.2.circlepath"
        case .ttf: return "textformat"
        case .dictionary: return "character.book.closed"
        case .backups: return "clock.arrow.circlepath"
        }
    }
}

struct FieldRow: View {
    let field: FieldDescriptor
    @ObservedObject var model: PreviewModel
    var integer: Binding<Int> {
        Binding(get: { model.draft[field.key]?.integer ?? field.minimum }, set: { model.draft[field.key] = .number($0) })
    }
    var text: Binding<String> {
        Binding(get: { model.draft[field.key]?.string ?? "" }, set: { model.draft[field.key] = .text($0) })
    }
    var body: some View {
        Group {
            if field.kind == "toggle" || field.kind == "bool" {
                Toggle(field.label, isOn: Binding(get: {
                    if case .flag(let value) = model.draft[field.key] { return value }
                    return integer.wrappedValue == 1
                }, set: { model.draft[field.key] = field.kind == "bool" ? .flag($0) : .number($0 ? 1 : 0) }))
            } else if field.kind == "secret" {
                SecureField(field.label, text: text)
                    .help("Leave blank to keep the saved password. New passwords require plaintext-handoff consent at Apply.")
            } else if field.kind == "text" {
                TextField(field.label, text: text)
                    .help("Maximum \(field.maximum) UTF-8 bytes. Paths refer to the SD card, not this Mac.")
            } else if field.kind == "enum" {
                Picker(field.label, selection: Binding(get: { model.draft[field.key] ?? .number(0) }, set: { model.draft[field.key] = $0 })) {
                    if let current = model.draft[field.key], !field.choices.contains(where: { $0.first == current }) {
                        Text("Current: \(current.display) (not offered for this profile)").tag(current)
                    }
                    ForEach(Array(field.choices.enumerated()), id: \.offset) { _, option in
                        if option.count == 2 { Text(option[1].display).tag(option[0]) }
                    }
                }
            } else if field.kind == "flags" {
                VStack(alignment: .leading, spacing: 8) {
                    Text(field.label).font(.headline)
                    ForEach(Array(field.choices.enumerated()), id: \.offset) { _, option in
                        if option.count == 2 {
                            Toggle(option[1].display, isOn: Binding(get: { integer.wrappedValue & option[0].integer != 0 }, set: { enabled in
                                integer.wrappedValue = enabled ? integer.wrappedValue | option[0].integer : integer.wrappedValue & ~option[0].integer
                            }))
                        }
                    }
                    Button("Use language default") { integer.wrappedValue = 0 }
                }
            } else if field.kind == "time" {
                VStack(alignment: .leading, spacing: 8) {
                    Toggle(field.label + " — set time", isOn: Binding(get: { integer.wrappedValue < 1440 }, set: { integer.wrappedValue = $0 ? 720 : 65535 }))
                    if integer.wrappedValue < 1440 {
                        DatePicker("Local reader time", selection: Binding(get: {
                            Date(timeIntervalSince1970: Double(integer.wrappedValue) * 60)
                        }, set: { date in
                            let seconds = Int(date.timeIntervalSince1970)
                            integer.wrappedValue = ((seconds / 60) % 1440 + 1440) % 1440
                        }), displayedComponents: .hourAndMinute)
                        .environment(\.timeZone, TimeZone(secondsFromGMT: 0)!)
                    }
                }
            } else if field.kind == "timezone" {
                Picker(field.label, selection: integer) {
                    ForEach(0...104, id: \.self) { raw in
                        let offset = (raw - 48) * 15
                        Text(String(format: "UTC%@%02d:%02d", offset < 0 ? "−" : "+", abs(offset) / 60, abs(offset) % 60)).tag(raw)
                    }
                }.help("Fixed reader UTC offset; daylight-saving changes are not automatic.")
            } else if field.key == "sleepTimeoutMinutes" {
                Picker(field.label, selection: integer) {
                    ForEach(1..<31, id: \.self) { Text("\($0) minutes").tag($0) }
                    Text("Never").tag(31)
                }
            } else {
                Stepper(value: integer, in: field.minimum...field.maximum, step: field.step) {
                    LabeledContent(field.label) {
                        Text(integer.wrappedValue.formatted() + (field.key == "lineHeightPercent" ? "%" : "")).monospacedDigit()
                    }
                }.accessibilityValue(String(integer.wrappedValue))
            }
        }
        .disabled(!field.readonly.isEmpty)
        .help(field.readonly.isEmpty ? field.label : field.readonly)
    }
}

struct ReviewSheet: View {
    @ObservedObject var model: PreviewModel
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(model.isRestoring ? "Review restore" : "Review changes").font(.title2.bold())
            Text(model.isRestoring ? "Restore the reviewed backup. All reviewed files are rechecked before writing, and the current complete state is retained." :
                "The original settings will be backed up before these changes are applied.")
                .foregroundStyle(.secondary)
            Table(model.differences) {
                TableColumn("Setting", value: \.label)
                TableColumn("Current") { Text($0.formatted($0.before, fields: model.reviewFields.isEmpty ? (model.snapshot?.fields ?? []) : model.reviewFields)) }
                TableColumn(model.isRestoring ? "Restored" : "New") { Text($0.formatted($0.after, fields: model.reviewFields.isEmpty ? (model.snapshot?.fields ?? []) : model.reviewFields)) }
            }
            .frame(minHeight: 150, maxHeight: 280)
            if model.requiresPlaintext {
                Toggle("I agree that this write stores plaintext credentials until CrossInk loads and successfully resaves them.", isOn: $model.plaintextConsent)
                Text("Passwords are hidden from this review. Eject, put the card back in the reader and use the relevant Wi-Fi or sync feature. Boot alone does not guarantee the password is resaved. Backups can retain credentials.")
                    .font(.callout).foregroundStyle(.secondary)
            }
            HStack {
                Text(model.isCard ? "Selected card only" : "Synthetic data only").font(.callout).foregroundStyle(.secondary)
                Spacer()
                Button("Cancel") { model.showingReview = false }.keyboardShortcut(.cancelAction)
                Button(model.isRestoring ? "Restore settings" : "Back up & apply") {
                    Task { await model.confirmReview() }
                }
                .buttonStyle(.borderedProminent)
                .keyboardShortcut(.defaultAction)
                .disabled(model.requiresPlaintext && !model.plaintextConsent)
            }
        }
        .padding(24)
        .frame(width: 650)
        .disabled(model.busy)
        .interactiveDismissDisabled(model.busy)
    }
}


struct BackupsPage: View {
    @ObservedObject var model: PreviewModel
    @State private var deletion: BackupEntry?
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Your complete reader configurations.").font(.title2.bold())
            Text("Back up all six global configuration stores together. Books, font/dictionary assets and per-book data are separate. Backups stay on this Mac and may contain credentials.")
                .foregroundStyle(.secondary)
            HStack {
                Button("Backup now", systemImage: "externaldrive.badge.plus") { Task { await model.backupNow() } }
                    .buttonStyle(.borderedProminent).disabled(model.snapshot == nil || model.busy || !model.dirty.isEmpty)
                Button("Refresh", systemImage: "arrow.clockwise") { Task { await model.loadBackups() } }.disabled(model.busy)
                Spacer()
                Button("Show in Finder", systemImage: "folder") { Task { await model.revealBackups() } }
                    .disabled(model.busy || model.backups.isEmpty)
            }
            if model.snapshot == nil {
                Text("Open a compatible card to create or restore a backup. Local backups can be viewed and deleted without a card.")
                    .font(.callout).foregroundStyle(.secondary)
            }
            if model.backups.isEmpty {
                ContentUnavailableView("No local configuration backups", systemImage: "clock.arrow.circlepath",
                    description: Text("Open your card and choose Backup now. Applying a change also saves a complete backup first."))
            } else {
                List(model.backups) { backup in
                    HStack(spacing: 16) {
                        VStack(alignment: .leading, spacing: 5) {
                            if backup.state == "unavailable" { Text("Incomplete or invalid backup") }
                            else { Text(backup.date, format: .dateTime.year().month().day().hour().minute().second()).fontWeight(.medium) }
                            Text("\(backup.scopeLabel) · \(backup.model) · \(backup.reasonLabel)")
                                .font(.callout).foregroundStyle(.secondary)
                            if !backup.can_delete && backup.state != "unavailable" {
                                Text("Protected recovery backup").font(.caption).foregroundStyle(.secondary)
                            }
                        }
                        Spacer()
                        Button("Restore") { Task { await model.review(backup: backup) } }
                            .disabled(model.busy || !model.dirty.isEmpty || !backup.can_restore)
                        Button("Delete", role: .destructive) { deletion = backup }
                            .disabled(model.busy || !model.dirty.isEmpty || !backup.can_delete)
                    }.padding(.vertical, 8)
                }
            }
        }.padding(24)
        .alert("Delete local backup?", isPresented: Binding(get: { deletion != nil }, set: { if !$0 { deletion = nil } })) {
            Button("Cancel", role: .cancel) { deletion = nil }
            Button("Delete backup", role: .destructive) {
                if let backup = deletion { deletion = nil; Task { await model.deleteBackup(backup) } }
            }
        } message: {
            Text("This permanently removes the selected local backup. Your SD card is not changed. Recovery backups stay protected until recovery is completed.")
        }
    }
}

struct CardProfileSheet: View {
    @ObservedObject var model: PreviewModel
    let path: String
    let dismiss: () -> Void
    @State private var confirmed = false
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Confirm your reader").font(.title2.bold())
            Text("Card files cannot reliably identify the model or installed firmware. Choose the reader this card belongs to.")
                .foregroundStyle(.secondary)
            Picker("Reviewed firmware", selection: $model.chosenProfile) {
                ForEach(model.catalog?.profiles ?? []) { Text("CrossInk v\($0.firmware)").tag($0.id) }
            }.onChange(of: model.chosenProfile) {
                confirmed = false
                model.chosenModel = model.availableModels.first?.id ?? ""
            }
            Picker("XTEINK model", selection: $model.chosenModel) {
                ForEach(model.availableModels) { Text($0.label).tag($0.id) }
            }
            Toggle("I confirm this reader is running CrossInk v\(model.selectedFirmware).", isOn: $confirmed)
            Text("Unlisted version or device? Settings editing stays blocked. The separate migration CLI can back up or diagnose a layout-compatible card.")
                .font(.callout).foregroundStyle(.secondary)
            Text("Selected X3 settings have owner-reported acceptance; other settings and models still need validation. Opening reads configuration only. Applying changes first backs up all six global configurations on this Mac.")
                .font(.callout).foregroundStyle(.secondary)
            HStack {
                Spacer()
                Button("Cancel", action: dismiss).keyboardShortcut(.cancelAction)
                Button("Open card") {
                    let selected = model.chosenModel
                    let firmware = model.selectedFirmware
                    let agreed = confirmed
                    dismiss()
                    Task { await model.openCard(path: path, model: selected, firmware: firmware, confirmed: agreed) }
                }.buttonStyle(.borderedProminent).disabled(!confirmed).keyboardShortcut(.defaultAction)
            }
        }.padding(24).frame(width: 520)
    }
}

struct CardSelection: Identifiable {
    let url: URL
    let id = UUID()
}

struct PreviewWindow: View {
    @ObservedObject var model: PreviewModel
    @State private var selection: PreviewSection? = .overview
    @State private var pendingSelection: PreviewSection?
    @State private var discardToNavigate = false
    @State private var resetDemo = false
    @State private var cardSelection: CardSelection?
    @State private var search = ""

    func chooseCard() {
        guard !model.busy, model.currentProfile != nil else { return }
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true; panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        panel.directoryURL = URL(fileURLWithPath: "/Volumes", isDirectory: true)
        panel.prompt = "Choose SD card"
        panel.message = "Choose the mounted SD card itself. No settings will be changed by opening it."
        if panel.runModal() == .OK, let url = panel.url {
            cardSelection = CardSelection(url: url)
        }
    }
    func navigate(_ next: PreviewSection?) {
        if !model.dirty.isEmpty { pendingSelection = next; discardToNavigate = true; return }
        selection = next
        search = ""
        if next == .backups { Task { await model.loadBackups() } }
        if let next, next != .overview, next != .backups, model.snapshot != nil, model.store != next.store {
            Task { await model.loadStore(next.store) }
        }
    }
    var body: some View {
        NavigationSplitView {
            List(PreviewSection.allCases.filter { isConfigurationGroupVisible($0.group, capabilities: model.snapshot?.capabilities ?? []) }, selection: Binding(get: { selection }, set: { navigate($0) })) { section in
                Label(section.rawValue, systemImage: section.icon).tag(section)
            }
            .disabled(model.busy)
            .navigationSplitViewColumnWidth(min: 175, ideal: 195, max: 245)
            .safeAreaInset(edge: .bottom) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("InkKit \(Backend.version)").fontWeight(.medium)
                    Text("Development build").foregroundStyle(.secondary)
                }.font(.caption).padding(16).frame(maxWidth: .infinity, alignment: .leading)
            }
        } detail: {
            VStack(spacing: 0) {
                HStack(spacing: 10) {
                    Image(systemName: model.isCard ? "sdcard" : "testtube.2")
                    Text(model.snapshot?.label ?? "No card selected").fontWeight(.semibold)
                    if let snapshot = model.snapshot {
                        Text("\(snapshot.model) · CrossInk \(snapshot.firmware)\(snapshot.synthetic ? " · synthetic" : " · user-confirmed")")
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                }.font(.callout).padding(.horizontal, 24).padding(.vertical, 12).background(.quaternary.opacity(0.45))
                Divider()
                content
                Divider()
                HStack(spacing: 12) {
                    if model.busy { ProgressView().controlSize(.small) }
                    Text(model.status).font(.callout).foregroundStyle(.secondary).lineLimit(4)
                    Spacer(minLength: 0)
                }.padding(.horizontal, 24).padding(.vertical, 14)
            }
            .navigationTitle(selection?.rawValue ?? "Overview")
            .toolbar {
                ToolbarItemGroup {
                    Button("Open SD card", systemImage: "sdcard") { chooseCard() }.disabled(model.busy || !model.dirty.isEmpty)
                    if model.snapshot != nil {
                        Button("Reload", systemImage: "arrow.clockwise") { Task { await model.reload() } }.disabled(model.busy || !model.dirty.isEmpty)
                        Button("Discard") { model.discard() }.disabled(model.busy || model.dirty.isEmpty)
                        Button(model.dirty.isEmpty ? "Review changes" : "Review \(model.dirty.count) changes") { Task { await model.review() } }
                            .keyboardShortcut("s", modifiers: .command).disabled(model.busy || model.dirty.isEmpty || !model.validDraft)
                        if model.isCard {
                            Button("Eject", systemImage: "eject") { Task { await model.eject() } }.disabled(model.busy || !model.dirty.isEmpty)
                        }
                    }
                }
            }
        }
        .frame(minWidth: 980, minHeight: 660)
        .task { await model.loadProfiles() }
        .onChange(of: model.sessionGeneration) { selection = .overview; search = "" }
        .sheet(isPresented: $model.showingReview) { ReviewSheet(model: model) }
        .sheet(item: $cardSelection) { selection in
            CardProfileSheet(model: model, path: selection.url.path, dismiss: { cardSelection = nil })
        }
        .alert("Operation stopped", isPresented: Binding(get: { model.errorMessage != nil }, set: { if !$0 { model.errorMessage = nil } })) {
            Button("OK", role: .cancel) { model.errorMessage = nil }
        } message: { Text(model.errorMessage ?? "") }
        .confirmationDialog("Discard draft changes?", isPresented: $discardToNavigate) {
            Button("Discard and continue", role: .destructive) { model.discard(); navigate(pendingSelection) }
        } message: { Text("The card has not been changed. Your unapplied draft will be discarded.") }
        .confirmationDialog("Create a new synthetic demo?", isPresented: $resetDemo) {
            Button("Create new demo") { Task { await model.createDemo() }; selection = .overview }
        } message: { Text("Previous synthetic demos remain in the temporary directory until macOS cleans them up.") }
    }

    var fields: [FieldDescriptor] {
        (model.snapshot?.fields ?? []).filter { field in
            let matches = search.isEmpty || field.label.localizedCaseInsensitiveContains(search) || field.key.localizedCaseInsensitiveContains(search)
            return isConfigurationGroupVisible(field.group, capabilities: model.snapshot?.capabilities ?? []) && matches && (model.store != "settings" || !search.isEmpty || field.group == (selection?.group ?? "device"))
        }
    }
    @ViewBuilder var content: some View {
        if selection == .backups {
            BackupsPage(model: model)
        } else if model.snapshot == nil || selection == .overview {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    Image(systemName: "externaldrive.badge.checkmark").font(.system(size: 38)).foregroundStyle(.tint).accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: 10) {
                        Text("A safer place to adjust your reader.").font(.title.bold())
                        Text("Manage CrossInk settings on your current SD card. Review each change, keep the original file and verify the result.")
                            .foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                    }
                    HStack {
                        Button("Open SD card", action: chooseCard).buttonStyle(.borderedProminent).disabled(model.busy || !model.dirty.isEmpty)
                        Button(model.snapshot == nil ? "Create synthetic demo" : "New synthetic demo") {
                            if model.snapshot == nil { Task { await model.createDemo() } } else { resetDemo = true }
                        }.disabled(model.busy || !model.dirty.isEmpty)
                    }
                    Picker("Demo model", selection: $model.chosenModel) {
                        ForEach(model.availableModels) { Text($0.label).tag($0.id) }
                    }.frame(maxWidth: 350).disabled(model.busy)
                    Divider()
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Settings available").font(.headline)
                        Label("Display, reading, library, controls, status bars and device", systemImage: "slider.horizontal.3")
                        Label("Wi-Fi, OPDS, reading sync, dictionary and font rendering", systemImage: "network")
                        Label("Original-file backups, verified apply and guarded restore", systemImage: "clock.arrow.circlepath")
                    }
                    Text("Reviewed CrossInk versions and reader models come from the bundled compatibility catalogue. Controls follow the selected model's capabilities; Frontlight appears only for a model with that hardware. Selected X3 settings have owner-reported acceptance; other settings and models remain unvalidated.")
                        .font(.callout).foregroundStyle(.secondary)
                    Text("Card editing never formats a disk. Backups stay on this Mac. New passwords require explicit plaintext-handoff consent; stored passwords are kept hidden.")
                        .font(.callout).foregroundStyle(.secondary)
                }.padding(32).frame(maxWidth: 740, alignment: .leading).frame(maxWidth: .infinity, alignment: .leading)
            }
        } else if model.store != selection?.store {
            ContentUnavailableView("Configuration not loaded", systemImage: "externaldrive.badge.questionmark", description: Text("Reconnect the card and select this category again."))
        } else {
            configurationForm
        }
    }
    var sections: [String] {
        fields.reduce(into: [String]()) { if !$0.contains($1.section) { $0.append($1.section) } }
    }
    var configurationForm: some View {
        Form {
            if model.store == "wifi" || model.store == "opds" || model.store == "koreader" {
                Section {
                    Text("Existing passwords stay hidden and are preserved. Leave a new password blank to keep it, or explicitly choose Clear password. New passwords require consent before plaintext is written.")
                        .foregroundStyle(.secondary)
                    if model.snapshot?.has_plaintext == true { Text("This file currently contains plaintext credentials. Protect the card and its backups.").foregroundStyle(.orange) }
                }
            }
            ForEach(sections, id: \.self) { section in
                let rows = fields.filter { $0.section == section }
                let enabled = rows.first { $0.key.hasSuffix(".enabled") }
                if enabled == nil || model.draft[enabled!.key]?.integer == 1 {
                    Section(section) {
                        ForEach(rows.filter { !$0.key.hasSuffix(".enabled") }) { field in FieldRow(field: field, model: model) }
                        if enabled != nil { Button("Remove entry", role: .destructive) { model.removeEntry(section) } }
                    }
                }
            }
            if let next = model.snapshot?.fields.first(where: { $0.key.hasSuffix(".enabled") && model.draft[$0.key]?.integer == 0 }) {
                Section { Button("Add " + (next.section.hasPrefix("Network") ? "network" : next.section.hasPrefix("Server") ? "server" : "font profile")) { model.addEntry() } }
            }
            if model.store == "koreader" {
                Section { Text("An empty server URL keeps the firmware's version-dependent default. InkKit preserves cfgVersion; editing this file does not execute a sync.").foregroundStyle(.secondary) }
            }
            if model.store == "dictionary" {
                Section { Text("Enter the dictionary's SD-card base path, without .idx/.dict/.ifo. This changes only the global selection, not per-book dictionaries or dictionary files.").foregroundStyle(.secondary) }
            }
        }
        .formStyle(.grouped).disabled(model.busy).id(model.store)
        .searchable(text: $search, prompt: "Find a setting")
    }
}

@MainActor
final class InkKitAppDelegate: NSObject, NSApplicationDelegate {
    static weak var model: PreviewModel?
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if Self.model?.busy == true {
            let alert = NSAlert(); alert.messageText = "Wait for the operation to finish"
            alert.informativeText = "InkKit is reading, writing or verifying configuration."
            alert.runModal(); return .terminateCancel
        }
        if Self.model?.dirty.isEmpty == false {
            let alert = NSAlert(); alert.messageText = "Discard unapplied changes and quit?"
            alert.addButton(withTitle: "Keep editing"); alert.addButton(withTitle: "Discard and quit")
            return alert.runModal() == .alertSecondButtonReturn ? .terminateNow : .terminateCancel
        }
        return .terminateNow
    }
}

struct InkKitPreviewApp: App {
    @NSApplicationDelegateAdaptor(InkKitAppDelegate.self) var delegate
    @StateObject private var model = PreviewModel()
    var body: some Scene {
        Window("InkKit", id: "main") {
            PreviewWindow(model: model).onAppear { InkKitAppDelegate.model = model }
        }.defaultSize(width: 1100, height: 780)
    }
}

@main
struct InkKitLauncher {
    static func main() {
        if CommandLine.arguments.dropFirst().elementsEqual(["--self-test"]) {
            do {
                let data = try Backend.execute(Data(), selfTest: true)
                let envelope = try JSONDecoder().decode(Envelope<RuntimeCheck>.self, from: data)
                guard envelope.protocolVersion == 2, envelope.ok, let result = envelope.data,
                      result.synthetic_roundtrip, result.complete_roundtrip,
                      result.complete_backups.contains(where: { $0.kind == "complete" }),
                      result.complete_plan.expectedStores?.count == 6,
                      result.complete_plan.fields?.isEmpty == false,
                      result.complete_created.created == true,
                      result.complete_restored.changed == true,
                      result.complete_deleted.deleted == true, result.isolated_site, result.runtime_paths_contained,
                      result.snapshot.synthetic, result.snapshot.fields.count >= 148,
                      result.store_snapshots.count == 5,
                      result.identity_tokens.count == 4,
                      result.identity_tokens.last?.file?.last == UInt64.max,
                      result.store_snapshots.first(where: { $0.store == "ttf" })?.values["profiles.0.stemDarkening"] == .flag(true),
                      result.store_snapshots.first(where: { $0.store == "wifi" })?.values["credentials.0.password"] == .text(""),
                      result.differences.count == 1,
                      result.differences.first?.after == .number(115),
                      URL(fileURLWithPath: result.prefix).resolvingSymlinksInPath().path == Backend.runtime.resolvingSymlinksInPath().path else {
                    throw HelperFailure(code: "runtime", message: "The self-contained runtime check failed.")
                }
                for profile in result.catalog.profiles {
                    for reader in profile.models {
                        guard isConfigurationGroupVisible("frontlight", capabilities: reader.capabilities) == (reader.id == "X4 Pro") else {
                            throw HelperFailure(code: "profile", message: "The model visibility check failed.")
                        }
                    }
                }
                guard result.snapshot.capabilities == result.catalog.profiles.first?.models.first(where: { $0.id == result.snapshot.model })?.capabilities,
                      result.store_snapshots.allSatisfy({ $0.capabilities == result.snapshot.capabilities }) else {
                    throw HelperFailure(code: "profile", message: "The snapshot capability check failed.")
                }
                for token in result.identity_tokens {
                    let encoded = try JSONEncoder().encode(token)
                    guard try JSONDecoder().decode(SnapshotToken.self, from: encoded) == token else {
                        throw HelperFailure(code: "identity", message: "The full-width file identity roundtrip failed.")
                    }
                }
                FileHandle.standardOutput.write(data)
            } catch {
                print("InkKit preview self-test failed. Rebuild and inspect the local development setup.")
                exit(1)
            }
        } else {
            InkKitPreviewApp.main()
        }
    }
}
