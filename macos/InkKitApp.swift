import AppKit
import Foundation
import SwiftUI

// A developer preview, deliberately limited to helper-created synthetic workspaces.
enum SettingValue: Codable, Equatable {
    case number(Int)
    case text(String)

    init(from decoder: Decoder) throws {
        let value = try decoder.singleValueContainer()
        if let integer = try? value.decode(Int.self) { self = .number(integer) }
        else { self = .text(try value.decode(String.self)) }
    }

    func encode(to encoder: Encoder) throws {
        var value = encoder.singleValueContainer()
        switch self {
        case .number(let integer): try value.encode(integer)
        case .text(let string): try value.encode(string)
        }
    }

    var display: String {
        switch self {
        case .number(let value): return String(value)
        case .text(let value): return value.isEmpty ? "Hardware default" : value
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
    var id: String { key }
}

struct SnapshotToken: Codable {
    let root: [Int64]
    let directory: [Int64]
    let file: [Int64]
    let sha256: String
    let mtime_ns: Int64
    let size: Int
}

struct Snapshot: Decodable {
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

    func formatted(_ value: SettingValue) -> String {
        if key == "sleepTimeoutMinutes", value.integer == 31 { return "Never" }
        if ["embeddedStyle", "hyphenationEnabled", "screenInverted", "showHiddenFiles",
            "hideFileExtension", "trackReadingStats"].contains(key) {
            return value.integer == 1 ? "On" : "Off"
        }
        if key == "lineHeightPercent" { return value.display + "%" }
        return value.display
    }
}

struct BackupEntry: Decodable, Identifiable {
    let id: String
    let created: TimeInterval
    let state: String
    var date: Date { Date(timeIntervalSince1970: created) }
}

struct HelperRequest: Encodable {
    var protocolVersion = 1
    let action: String
    var root: String? = nil
    var expected: SnapshotToken? = nil
    var changes: [String: SettingValue]? = nil
    var backup_id: String? = nil
    enum CodingKeys: String, CodingKey {
        case protocolVersion = "protocol"
        case action, root, expected, changes, backup_id
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

struct DemoResult: Decodable { let root: String; let snapshot: Snapshot }
struct WriteResult: Decodable { let changed: Bool; let backup_id: String?; let snapshot: Snapshot }
struct RuntimeCheck: Decodable {
    let synthetic_roundtrip: Bool
    let isolated_site: Bool
    let runtime_paths_contained: Bool
    let prefix: String
    let snapshot: Snapshot
    let differences: [Difference]
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
        DispatchQueue.global().asyncAfter(deadline: .now() + 30, execute: timeout)
        defer { timeout.cancel() }
        do {
            try stdin.fileHandleForWriting.write(contentsOf: input)
            try stdin.fileHandleForWriting.close()
            var output = Data()
            while let chunk = try stdout.fileHandleForReading.read(upToCount: 8192), !chunk.isEmpty {
                output.append(chunk)
                if output.count > 131072 {
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
    @Published var status = "Create a demo to explore settings without connecting a card."
    @Published var differences: [Difference] = []
    @Published var showingReview = false
    private var root: String?
    private var reviewedChanges: [String: SettingValue] = [:]
    private var reviewedBackup: String?

    var dirty: [String: SettingValue] {
        draft.filter { snapshot?.values[$0.key] != $0.value }
    }
    var isRestoring: Bool { reviewedBackup != nil }
    var validDraft: Bool {
        let name = draft["deviceName"]?.string ?? ""
        return (name.isEmpty || (2...20).contains(name.utf8.count)) &&
            !name.unicodeScalars.contains { $0.value < 32 || $0.value == 127 }
    }

    private func request<T: Decodable>(_ request: HelperRequest) async throws -> T {
        let input = try JSONEncoder().encode(request)
        let output = try await Task.detached(priority: .userInitiated) { try Backend.execute(input) }.value
        let response = try JSONDecoder().decode(Envelope<T>.self, from: output)
        guard response.protocolVersion == 1 else {
            throw HelperFailure(code: "protocol", message: "The app and helper versions do not match. Rebuild the preview.")
        }
        guard response.ok, let data = response.data else {
            throw response.error ?? HelperFailure(code: "helper", message: "The helper could not complete the operation.")
        }
        return data
    }

    private func report(_ error: Error) {
        if let failure = error as? HelperFailure { errorMessage = failure.message }
        else { errorMessage = "The preview could not complete the operation. Reload and review the workspace backups." }
    }

    private func install(_ snapshot: Snapshot) {
        self.snapshot = snapshot
        draft = snapshot.values
    }

    func createDemo() async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        do {
            let result: DemoResult = try await request(HelperRequest(action: "demo.create"))
            root = result.root
            install(result.snapshot)
            backups = []
            status = "Synthetic demo ready. No SD card is connected to this preview."
        } catch { report(error) }
    }

    func discard() { if let snapshot { draft = snapshot.values }; status = "Draft changes discarded." }

    func reload() async {
        guard !busy, let root else { return }
        busy = true
        defer { busy = false }
        do {
            let fresh: Snapshot = try await request(HelperRequest(action: "config.read", root: root))
            install(fresh)
            backups = try await request(HelperRequest(action: "backups.list", root: root))
            status = "Workspace reloaded. Review backups if an operation was interrupted."
        } catch { report(error) }
    }

    func review(backup: BackupEntry? = nil) async {
        guard !busy, let root, let snapshot else { return }
        busy = true
        defer { busy = false }
        do {
            reviewedBackup = backup?.id
            reviewedChanges = dirty
            if let backup {
                differences = try await request(HelperRequest(action: "config.restore_preview", root: root,
                                                               expected: snapshot.token, backup_id: backup.id))
            } else {
                differences = try await request(HelperRequest(action: "config.preview", root: root,
                                                               expected: snapshot.token, changes: reviewedChanges))
            }
            if differences.isEmpty { status = "Settings already match. No files were changed." }
            else { showingReview = true }
        } catch { report(error) }
    }

    func confirmReview() async {
        guard !busy, let root, let snapshot else { return }
        busy = true
        defer { busy = false; showingReview = false }
        do {
            let result: WriteResult
            if let backup = reviewedBackup {
                result = try await request(HelperRequest(action: "config.restore", root: root,
                                                         expected: snapshot.token, backup_id: backup))
            } else {
                result = try await request(HelperRequest(action: "config.apply", root: root,
                                                         expected: snapshot.token, changes: reviewedChanges))
            }
            install(result.snapshot)
            backups = try await request(HelperRequest(action: "backups.list", root: root))
            status = reviewedBackup != nil ? "Original settings restored and read back successfully." :
                "Settings backed up, applied and read back successfully."
        } catch { report(error) }
    }

    func revealWorkspace() {
        if let root { NSWorkspace.shared.selectFile(nil, inFileViewerRootedAtPath: root) }
    }
}

enum PreviewSection: String, CaseIterable, Identifiable {
    case overview = "Overview", reading = "Reading", device = "Device", backups = "Backups"
    var id: String { rawValue }
    var icon: String {
        switch self {
        case .overview: return "externaldrive"
        case .reading: return "textformat.size"
        case .device: return "slider.horizontal.3"
        case .backups: return "clock.arrow.circlepath"
        }
    }
}

struct FieldRow: View {
    let field: FieldDescriptor
    @ObservedObject var model: PreviewModel

    var integer: Binding<Int> {
        Binding(get: { model.draft[field.key]?.integer ?? field.minimum },
                set: { model.draft[field.key] = .number($0) })
    }

    var body: some View {
        if field.kind == "toggle" {
            Toggle(field.label, isOn: Binding(get: { integer.wrappedValue == 1 },
                                             set: { integer.wrappedValue = $0 ? 1 : 0 }))
        } else if field.kind == "text" {
            TextField(field.label, text: Binding(get: { model.draft[field.key]?.string ?? "" },
                                                set: { model.draft[field.key] = .text($0) }))
                .help("Empty uses the hardware name. Otherwise enter 2–20 UTF-8 bytes.")
            if !model.validDraft { Text("Use 2–20 UTF-8 bytes, or leave the name empty.").foregroundStyle(.red) }
        } else if field.key == "sleepTimeoutMinutes" {
            Picker(field.label, selection: integer) {
                ForEach(1..<31, id: \.self) { Text("\($0) minutes").tag($0) }
                Text("Never").tag(31)
            }
        } else {
            Stepper(value: integer, in: field.minimum...field.maximum) {
                LabeledContent(field.label) {
                    Text(integer.wrappedValue.formatted() + (field.key == "lineHeightPercent" ? "%" : ""))
                        .monospacedDigit()
                }
            }
            .accessibilityValue(String(integer.wrappedValue))
        }
    }
}

struct ReviewSheet: View {
    @ObservedObject var model: PreviewModel
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(model.isRestoring ? "Review restore" : "Review changes").font(.title2.bold())
            Text(model.isRestoring ? "Restore the original settings file in this synthetic workspace." :
                "The original settings will be backed up before these changes are applied.")
                .foregroundStyle(.secondary)
            Table(model.differences) {
                TableColumn("Setting", value: \.label)
                TableColumn("Current") { Text($0.formatted($0.before)) }
                TableColumn(model.isRestoring ? "Restored" : "New") { Text($0.formatted($0.after)) }
            }
            .frame(minHeight: 150, maxHeight: 280)
            HStack {
                Text("Synthetic data only").font(.callout).foregroundStyle(.secondary)
                Spacer()
                Button("Cancel") { model.showingReview = false }.keyboardShortcut(.cancelAction)
                Button(model.isRestoring ? "Restore settings" : "Back up & apply") {
                    Task { await model.confirmReview() }
                }
                .buttonStyle(.borderedProminent)
                .keyboardShortcut(.defaultAction)
            }
        }
        .padding(24)
        .frame(width: 650)
        .disabled(model.busy)
        .interactiveDismissDisabled(model.busy)
    }
}

struct PreviewWindow: View {
    @StateObject private var model = PreviewModel()
    @State private var selection: PreviewSection? = .overview
    @State private var resetDemo = false

    var body: some View {
        NavigationSplitView {
            List(PreviewSection.allCases, selection: $selection) { section in
                Label(section.rawValue, systemImage: section.icon).tag(section)
            }
            .navigationSplitViewColumnWidth(min: 170, ideal: 190, max: 240)
            .safeAreaInset(edge: .bottom) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("InkKit \(Backend.version)").fontWeight(.medium)
                    Text("Developer Preview").foregroundStyle(.secondary)
                }
                .font(.caption).padding(16).frame(maxWidth: .infinity, alignment: .leading)
            }
        } detail: {
            VStack(spacing: 0) {
                HStack(spacing: 10) {
                    Image(systemName: "testtube.2")
                    Text("Synthetic workspace").fontWeight(.semibold)
                    Text("Real SD card access is disabled.").foregroundStyle(.secondary)
                    Spacer()
                }
                .font(.callout).padding(.horizontal, 24).padding(.vertical, 12)
                .background(.quaternary.opacity(0.45))
                Divider()
                content
                Divider()
                HStack(spacing: 12) {
                    if model.busy { ProgressView().controlSize(.small) }
                    Text(model.status).font(.callout).foregroundStyle(.secondary).lineLimit(3)
                    Spacer(minLength: 0)
                }
                .padding(.horizontal, 24).padding(.vertical, 14)
            }
            .navigationTitle(selection?.rawValue ?? "Overview")
            .toolbar {
                ToolbarItemGroup {
                    if model.snapshot != nil {
                        Button("Reload", systemImage: "arrow.clockwise") { Task { await model.reload() } }
                            .disabled(model.busy || !model.dirty.isEmpty)
                        Button("Discard") { model.discard() }.disabled(model.busy || model.dirty.isEmpty)
                        Button(model.dirty.isEmpty ? "Review changes" : "Review \(model.dirty.count) changes") {
                            Task { await model.review() }
                        }
                        .keyboardShortcut("s", modifiers: .command)
                        .disabled(model.busy || model.dirty.isEmpty || !model.validDraft)
                    }
                }
            }
        }
        .frame(minWidth: 880, minHeight: 620)
        .sheet(isPresented: $model.showingReview) { ReviewSheet(model: model) }
        .alert("Operation stopped", isPresented: Binding(get: { model.errorMessage != nil },
                                                         set: { if !$0 { model.errorMessage = nil } })) {
            Button("OK", role: .cancel) { model.errorMessage = nil }
        } message: { Text(model.errorMessage ?? "") }
        .confirmationDialog("Create a new synthetic demo?", isPresented: $resetDemo) {
            Button("Create new demo") { Task { await model.createDemo() } }
        } message: { Text("This resets the app's draft. Earlier demos and their backups remain in the temporary directory until cleaned up by macOS.") }
    }

    @ViewBuilder var content: some View {
        if model.snapshot == nil || selection == .overview {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    Image(systemName: "externaldrive.badge.checkmark")
                        .font(.system(size: 38, weight: .regular)).foregroundStyle(.tint).accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: 10) {
                        Text("A safer place to adjust your reader.").font(.title.bold())
                        Text("Explore CrossInk settings with an example reader. Review every change, keep the original file and verify the result.")
                            .foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                    }
                    Button(model.snapshot == nil ? "Create synthetic demo" : "Create new demo") {
                        if model.snapshot == nil { Task { await model.createDemo() } } else { resetDemo = true }
                    }
                    .buttonStyle(.borderedProminent).disabled(model.busy)
                    Divider()
                    VStack(alignment: .leading, spacing: 12) {
                        Text("In this preview").font(.headline)
                        Label("Reading layout and device preferences", systemImage: "slider.horizontal.3")
                        Label("Change previews, verified backups and restore", systemImage: "clock.arrow.circlepath")
                        Text("CrossInk v1.6.1 profile · X3, X4, X4 Classic and X4 Pro are the intended device scope. Settings writes have not been validated on hardware.")
                            .font(.callout).foregroundStyle(.secondary)
                    }
                    Text("Wi-Fi passwords, real-card editing and migration are not part of this preview. The existing migration CLI remains available separately.")
                        .font(.callout).foregroundStyle(.secondary)
                }
                .padding(32).frame(maxWidth: 690, alignment: .leading).frame(maxWidth: .infinity, alignment: .leading)
            }
        } else if selection == .backups {
            VStack(alignment: .leading, spacing: 18) {
                Text("Original settings, kept before every apply.").font(.title2.bold())
                Text("Restore is available only while settings match the selected backup. Discard draft changes before restoring.")
                    .foregroundStyle(.secondary)
                if model.backups.isEmpty {
                    ContentUnavailableView("No backups yet", systemImage: "clock.arrow.circlepath",
                                           description: Text("Apply a setting change to create a verified backup."))
                } else {
                    List(model.backups) { backup in
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                if backup.state == "unavailable" { Text("Incomplete or invalid backup") }
                                else { Text(backup.date, format: .dateTime.month().day().hour().minute().second()) }
                                Text(backup.state.capitalized).font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            Button("Review restore") { Task { await model.review(backup: backup) } }
                                .disabled(model.busy || !model.dirty.isEmpty || backup.state == "unavailable")
                        }.padding(.vertical, 5)
                    }
                }
                Button("Show workspace in Finder", systemImage: "folder") { model.revealWorkspace() }
            }.padding(24)
        } else {
            Form {
                Section {
                    ForEach(model.snapshot?.fields.filter { $0.group == (selection == .reading ? "reading" : "device") } ?? []) { field in
                        FieldRow(field: field, model: model)
                    }
                } header: { Text(selection == .reading ? "Reading layout" : "Device preferences") }
                footer: {
                    Text(selection == .reading ? "Changes use raw SD setting values. Font selection needs a verified font catalog and comes later." :
                        "An empty name uses the hardware default. Sleep ‘Never’ is stored as 31, following CrossInk's format.")
                }
            }
            .formStyle(.grouped).disabled(model.busy)
        }
    }
}

struct InkKitPreviewApp: App {
    var body: some Scene {
        WindowGroup("InkKit Preview") { PreviewWindow() }
            .defaultSize(width: 960, height: 700)
    }
}

@main
struct InkKitLauncher {
    static func main() {
        if CommandLine.arguments.dropFirst().elementsEqual(["--self-test"]) {
            do {
                let data = try Backend.execute(Data(), selfTest: true)
                let envelope = try JSONDecoder().decode(Envelope<RuntimeCheck>.self, from: data)
                guard envelope.protocolVersion == 1, envelope.ok, let result = envelope.data,
                      result.synthetic_roundtrip, result.isolated_site, result.runtime_paths_contained,
                      result.snapshot.synthetic, result.snapshot.fields.count == 12,
                      result.differences.count == 1,
                      result.differences.first?.after == .number(115),
                      URL(fileURLWithPath: result.prefix).resolvingSymlinksInPath().path == Backend.runtime.resolvingSymlinksInPath().path else {
                    throw HelperFailure(code: "runtime", message: "The self-contained runtime check failed.")
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
