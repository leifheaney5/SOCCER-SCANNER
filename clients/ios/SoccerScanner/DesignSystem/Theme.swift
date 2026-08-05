import SwiftUI

/// Shared visual language. Colours are semantic so Dark Mode and Increased
/// Contrast are handled by the system rather than hard-coded per view.
public enum Theme {
    public enum Spacing {
        public static let xs: CGFloat = 4
        public static let sm: CGFloat = 8
        public static let md: CGFloat = 12
        public static let lg: CGFloat = 16
        public static let xl: CGFloat = 24
    }

    public enum Radius {
        public static let card: CGFloat = 12
        public static let badge: CGFloat = 6
    }

    /// Minimum comfortable hit target per Apple's HIG.
    public static let minimumTapTarget: CGFloat = 44
}

public extension MatchStatus {
    /// Semantic tint. Live states share one colour so HT/ET/PEN read as a
    /// family while remaining textually distinct.
    var tint: Color {
        switch self {
        case .inProgress, .halfTime, .extraTime, .penalties:
            return .green
        case .delayed, .postponed, .cancelled, .suspended, .abandoned:
            return .orange
        case .finished:
            return .secondary
        case .scheduled, .unknown:
            return .accentColor
        }
    }
}

public struct StatusBadge: View {
    private let status: MatchStatus

    public init(status: MatchStatus) {
        self.status = status
    }

    public var body: some View {
        HStack(spacing: Theme.Spacing.xs) {
            if status.isActive {
                Circle()
                    .fill(status.tint)
                    .frame(width: 6, height: 6)
            }
            Text(status.shortLabel)
                .font(.caption.weight(.semibold))
                .monospacedDigit()
        }
        .padding(.horizontal, Theme.Spacing.sm)
        .padding(.vertical, Theme.Spacing.xs)
        .background(status.tint.opacity(0.15), in: RoundedRectangle(cornerRadius: Theme.Radius.badge))
        .foregroundStyle(status.tint)
        // The badge is an abbreviation; announce the full meaning instead.
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(status.label)
        .accessibilityHint(status.accessibilityDescription)
    }
}
