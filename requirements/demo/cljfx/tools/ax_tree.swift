import ApplicationServices
import Foundation
let pid = pid_t(CommandLine.arguments[1])!
let app = AXUIElementCreateApplication(pid)
func attr(_ e: AXUIElement, _ name: String) -> AnyObject? {
    var v: AnyObject?
    return AXUIElementCopyAttributeValue(e, name as CFString, &v) == .success ? v : nil
}
func walk(_ e: AXUIElement, _ depth: Int) {
    let role = attr(e, "AXRole") as? String ?? "?"
    if ["AXButton", "AXCheckBox", "AXStaticText", "AXTabGroup", "AXRadioButton", "AXGroup", "AXSlider", "AXTextField", "AXScrollArea", "AXScrollBar"].contains(role) && depth > 1 {
        var names: CFArray?
        AXUIElementCopyActionNames(e, &names)
        let title = attr(e, "AXTitle") as? String ?? ""
        let desc = attr(e, "AXDescription") as? String ?? ""
        let help = attr(e, "AXHelp") as? String ?? ""
        // A field is named by its label: what that label says stands in for a title.
        let label = attr(e, "AXTitleUIElement").flatMap { attr($0 as! AXUIElement, "AXValue") as? String } ?? ""
        let kind = attr(e, "AXRoleDescription") as? String ?? ""
        let value = attr(e, "AXValue").map { "\($0)" } ?? ""
        let enabled = attr(e, "AXEnabled") as? Bool
        if !(title.isEmpty && desc.isEmpty && value.isEmpty && help.isEmpty) {
            print("\(role)\(label.isEmpty ? "" : " label=\"\(label)\" kind=\"\(kind)\"") title=\"\(title)\" desc=\"\(desc)\" help=\"\(help)\" value=\"\(value)\" enabled=\(enabled.map { "\($0)" } ?? "?") actions=\((names as? [String]) ?? [])")
        }
    }
    if depth < 12, let kids = attr(e, "AXChildren") as? [AXUIElement] { for k in kids { walk(k, depth + 1) } }
}
print("trusted:", AXIsProcessTrusted())
if let windows = attr(app, "AXWindows") as? [AXUIElement] { for w in windows { walk(w, 1) } } else { print("no windows readable") }
