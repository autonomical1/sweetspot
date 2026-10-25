import SwiftUI

extension Color {
    init(hex: UInt32) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xff) / 255,
            green: Double((hex >> 8) & 0xff) / 255,
            blue: Double(hex & 0xff) / 255,
            opacity: 1
        )
    }
}

enum Theme {
    static let background = Color(hex: 0x10151b)
    static let surface = Color(hex: 0x141a21)
    static let card = Color(hex: 0x161d25)
    static let raised = Color(hex: 0x1d252e)
    static let input = Color(hex: 0x1c252e)
    static let border = Color(hex: 0x2a333d)
    static let strongBorder = Color(hex: 0x313b46)
    static let primaryText = Color(hex: 0xe9edf0)
    static let secondaryText = Color(hex: 0x89959f)
    static let tertiaryText = Color(hex: 0x75818c)
    static let accent = Color(hex: 0x5cddc5)
    static let accentInk = Color(hex: 0x10231f)
    static let accentLink = Color(hex: 0x6cddc8)
    static let accentDim = Color(hex: 0x4b746e)
    static let warning = Color(hex: 0xf4bd61)
    static let error = Color(hex: 0xf28b82)
    static let success = Color(hex: 0x77d79a)
}

struct SweetspotPrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 15, weight: .semibold))
            .foregroundStyle(Theme.accentInk)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .background(Theme.accent, in: RoundedRectangle(cornerRadius: 7))
            .opacity(configuration.isPressed ? 0.8 : 1)
    }
}

struct SweetspotQuietButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 15, weight: .medium))
            .foregroundStyle(Theme.primaryText)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .background(Theme.raised, in: RoundedRectangle(cornerRadius: 7))
            .overlay(RoundedRectangle(cornerRadius: 7).stroke(Theme.strongBorder, lineWidth: 1))
            .opacity(configuration.isPressed ? 0.8 : 1)
    }
}

struct SweetspotCard: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding(16)
            .background(Theme.card, in: RoundedRectangle(cornerRadius: 9))
            .overlay(RoundedRectangle(cornerRadius: 9).stroke(Theme.border, lineWidth: 1))
    }
}

struct SweetspotScreen: ViewModifier {
    func body(content: Content) -> some View {
        content
            .scrollContentBackground(.hidden)
            .background(Theme.background.ignoresSafeArea())
            .foregroundStyle(Theme.primaryText)
            .tint(Theme.accent)
            .toolbarBackground(Theme.surface, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
    }
}

extension View {
    func sweetspotCard() -> some View { modifier(SweetspotCard()) }
    func sweetspotScreen() -> some View { modifier(SweetspotScreen()) }
}

struct EyebrowText: View {
    let text: String

    var body: some View {
        Text(text.uppercased())
            .font(.system(size: 10, weight: .medium, design: .monospaced))
            .tracking(1.2)
            .foregroundStyle(Theme.tertiaryText)
    }
}

struct SweetspotBrandMark: View {
    var body: some View {
        Text("S")
            .font(.system(size: 20, weight: .bold, design: .rounded))
            .tracking(-0.4)
            .foregroundStyle(Theme.accentLink)
            .frame(width: 31, height: 31)
            .overlay(RoundedRectangle(cornerRadius: 9).stroke(Theme.accent, lineWidth: 1))
            .accessibilityLabel("Sweetspot")
    }
}
