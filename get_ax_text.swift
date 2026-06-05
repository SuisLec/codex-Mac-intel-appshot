import Cocoa
import ApplicationServices

extension AXUIElement: Hashable {
    public static func == (lhs: AXUIElement, rhs: AXUIElement) -> Bool {
        return CFEqual(lhs, rhs)
    }
    
    public func hash(into hasher: inout Hasher) {
        hasher.combine(CFHash(self))
    }
}

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

if !AXIsProcessTrusted() {
    print("Warning: Accessibility API is not trusted/enabled for this process.")
}

var allText = ""
var visitedElements = Set<AXUIElement>()
var elementCount = 0
let maxElements = 1000

func extractText(element: AXUIElement, depth: Int) {
    if visitedElements.contains(element) { return }
    visitedElements.insert(element)
    
    elementCount += 1
    if elementCount > maxElements { return }
    
    var roleVal: AnyObject?
    var role = ""
    if AXUIElementCopyAttributeValue(element, kAXRoleAttribute as CFString, &roleVal) == .success,
       CFGetTypeID(roleVal) == CFStringGetTypeID() {
        role = roleVal as! String
    }
    
    var title = ""
    var titleVal: AnyObject?
    if AXUIElementCopyAttributeValue(element, kAXTitleAttribute as CFString, &titleVal) == .success,
       CFGetTypeID(titleVal) == CFStringGetTypeID() {
        title = (titleVal as! String).trimmingCharacters(in: .whitespacesAndNewlines)
    }
    
    var valueStr = ""
    var valueVal: AnyObject?
    if AXUIElementCopyAttributeValue(element, kAXValueAttribute as CFString, &valueVal) == .success {
        if CFGetTypeID(valueVal) == CFStringGetTypeID() {
            valueStr = (valueVal as! String).trimmingCharacters(in: .whitespacesAndNewlines)
        } else if let v = valueVal as? NSAttributedString {
            valueStr = v.string.trimmingCharacters(in: .whitespacesAndNewlines)
        } else if let num = valueVal as? NSNumber {
            valueStr = num.stringValue
        }
    }
    
    var desc = ""
    var descVal: AnyObject?
    if AXUIElementCopyAttributeValue(element, kAXDescriptionAttribute as CFString, &descVal) == .success,
       CFGetTypeID(descVal) == CFStringGetTypeID() {
        desc = (descVal as! String).trimmingCharacters(in: .whitespacesAndNewlines)
    }
    
    var placeholder = ""
    var placeholderVal: AnyObject?
    if AXUIElementCopyAttributeValue(element, "AXPlaceholderValue" as CFString, &placeholderVal) == .success,
       CFGetTypeID(placeholderVal) == CFStringGetTypeID() {
        placeholder = (placeholderVal as! String).trimmingCharacters(in: .whitespacesAndNewlines)
    }
    
    var help = ""
    var helpVal: AnyObject?
    if AXUIElementCopyAttributeValue(element, kAXHelpAttribute as CFString, &helpVal) == .success,
       CFGetTypeID(helpVal) == CFStringGetTypeID() {
        help = (helpVal as! String).trimmingCharacters(in: .whitespacesAndNewlines)
    }
    
    var line = ""
    if !title.isEmpty {
        line += "Title: \(title) "
    }
    if !valueStr.isEmpty {
        line += "Value: \(valueStr) "
    }
    if !desc.isEmpty {
        line += "Desc: \(desc) "
    }
    if !placeholder.isEmpty {
        line += "Placeholder: \(placeholder) "
    }
    if !help.isEmpty {
        line += "Help: \(help) "
    }
    
    if !line.isEmpty {
        allText += String(repeating: "  ", count: depth) + "[\(role)] \(line)\n"
    }
    
    var childrenVal: AnyObject?
    if AXUIElementCopyAttributeValue(element, kAXChildrenAttribute as CFString, &childrenVal) == .success,
       CFGetTypeID(childrenVal) == CFArrayGetTypeID() {
        let children = childrenVal as! [AXUIElement]
        for child in children {
            extractText(element: child, depth: depth + 1)
        }
    }
}

for app in apps {
    let pid = app.processIdentifier
    let appElement = AXUIElementCreateApplication(pid)
    
    var windowVal: AnyObject?
    if AXUIElementCopyAttributeValue(appElement, kAXFocusedWindowAttribute as CFString, &windowVal) == .success,
       CFGetTypeID(windowVal) == AXUIElementGetTypeID() {
        let window = windowVal as! AXUIElement
        extractText(element: window, depth: 0)
    } else {
        var windowsVal: AnyObject?
        if AXUIElementCopyAttributeValue(appElement, kAXWindowsAttribute as CFString, &windowsVal) == .success,
           CFGetTypeID(windowsVal) == CFArrayGetTypeID(),
           let windows = windowsVal as? [AXUIElement],
           !windows.isEmpty {
            extractText(element: windows[0], depth: 0)
        } else {
            extractText(element: appElement, depth: 0)
        }
    }
}

if allText.isEmpty {
    print("No accessibility text found.")
} else {
    print(allText)
}
