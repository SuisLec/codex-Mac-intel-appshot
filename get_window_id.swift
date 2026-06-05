import Cocoa
import Quartz

let arguments = CommandLine.arguments
guard arguments.count > 1 else {
    print("Error: Missing bundle identifier")
    exit(1)
}

let bundleId = arguments[1]

let apps = NSRunningApplication.runningApplications(withBundleIdentifier: bundleId)
guard !apps.isEmpty else {
    print("Error: Application \(bundleId) not running")
    exit(1)
}

let pids = Set(apps.map { $0.processIdentifier })

guard let windowList = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] else {
    print("Error: Failed to copy window list")
    exit(1)
}

var targetWindowId: CGWindowID? = nil
for window in windowList {
    guard let ownerPID = window[kCGWindowOwnerPID as String] as? Int32,
          let windowId = window[kCGWindowNumber as String] as? CGWindowID,
          let layer = window[kCGWindowLayer as String] as? Int,
          layer == 0 else {
        continue
    }
    
    if pids.contains(ownerPID) {
        targetWindowId = windowId
        break
    }
}

if let windowId = targetWindowId {
    print(windowId)
} else {
    print("Error: No window found for bundle identifier \(bundleId)")
    exit(1)
}
