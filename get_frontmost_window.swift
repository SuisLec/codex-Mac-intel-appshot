import Cocoa
import Quartz

func getFrontmostWindowInfo() -> [String: Any]? {
    guard let frontmostApp = NSWorkspace.shared.frontmostApplication else {
        return nil
    }
    
    let bundleId = frontmostApp.bundleIdentifier ?? ""
    let appName = frontmostApp.localizedName ?? ""
    let pid = frontmostApp.processIdentifier
    
    var iconBase64 = ""
    if let icon = frontmostApp.icon {
        let smallSize = NSSize(width: 32, height: 32)
        let smallIcon = NSImage(size: smallSize)
        smallIcon.lockFocus()
        icon.draw(in: NSRect(origin: .zero, size: smallSize),
                  from: NSRect(origin: .zero, size: icon.size),
                  operation: .copy,
                  fraction: 1.0)
        smallIcon.unlockFocus()
        
        if let tiffData = smallIcon.tiffRepresentation,
           let bitmap = NSBitmapImageRep(data: tiffData),
           let pngData = bitmap.representation(using: .png, properties: [:]) {
            iconBase64 = "data:image/png;base64," + pngData.base64EncodedString()
        }
    }
    
    var windowTitle = ""
    if let windowList = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] {
        for window in windowList {
            guard let ownerPID = window[kCGWindowOwnerPID as String] as? Int32,
                  ownerPID == pid,
                  let layer = window[kCGWindowLayer as String] as? Int,
                  layer == 0 else {
                continue
            }
            if let title = window[kCGWindowName as String] as? String, !title.isEmpty {
                windowTitle = title
                break
            }
        }
    }
    
    var dict: [String: Any] = [
        "bundleIdentifier": bundleId,
        "name": appName,
        "iconSmallDataURL": iconBase64
    ]
    if !windowTitle.isEmpty {
        dict["windowTitle"] = windowTitle
    }
    return dict
}

if let info = getFrontmostWindowInfo() {
    if let jsonData = try? JSONSerialization.data(withJSONObject: info, options: []),
       let jsonString = String(data: jsonData, encoding: .utf8) {
        print(jsonString)
        exit(0)
    }
}

print("{}")
exit(0)
