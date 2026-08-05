import Foundation

/// Timezone-aware formatting — the native counterpart to `static/js/time-zone.js`.
///
/// Every date and time in the app goes through here with an explicit zone.
/// Using `TimeZone.current` implicitly is the native equivalent of a bare
/// `toLocaleTimeString()`: it silently disagrees with the selected zone and
/// puts fixtures on the wrong calendar day.
public enum FixtureTime {
    private static func calendar(in timeZone: TimeZone) -> Calendar {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        return calendar
    }

    /// The `YYYY-MM-DD` day an instant belongs to in the given zone.
    public static func calendarDate(for instant: Date, in timeZone: TimeZone) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = timeZone
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: instant)
    }

    public static func today(in timeZone: TimeZone, now: Date = Date()) -> String {
        calendarDate(for: now, in: timeZone)
    }

    /// Kick-off clock time in the selected zone.
    public static func kickoff(_ instant: Date?, in timeZone: TimeZone) -> String {
        guard let instant else { return String(localized: "Time TBC") }
        let formatter = DateFormatter()
        formatter.locale = Locale.current
        formatter.timeZone = timeZone
        formatter.dateStyle = .none
        formatter.timeStyle = .short
        return formatter.string(from: instant)
    }

    /// Long day heading for a `YYYY-MM-DD` string.
    public static func dayHeading(for isoDay: String, in timeZone: TimeZone) -> String {
        let parser = DateFormatter()
        parser.locale = Locale(identifier: "en_US_POSIX")
        parser.timeZone = TimeZone(identifier: "UTC")
        parser.dateFormat = "yyyy-MM-dd"
        guard let date = parser.date(from: isoDay) else { return isoDay }

        let formatter = DateFormatter()
        formatter.locale = Locale.current
        // A bare calendar day carries no instant, so render it in UTC to stop
        // it drifting a day in zones behind UTC.
        formatter.timeZone = TimeZone(identifier: "UTC")
        formatter.dateFormat = "EEEE, MMMM d, yyyy"
        return formatter.string(from: date)
    }

    public static func shiftDay(_ isoDay: String, by days: Int) -> String {
        let parser = DateFormatter()
        parser.locale = Locale(identifier: "en_US_POSIX")
        parser.timeZone = TimeZone(identifier: "UTC")
        parser.dateFormat = "yyyy-MM-dd"
        guard let date = parser.date(from: isoDay) else { return isoDay }
        var utcCalendar = Calendar(identifier: .gregorian)
        utcCalendar.timeZone = TimeZone(identifier: "UTC")!
        guard let shifted = utcCalendar.date(byAdding: .day, value: days, to: date) else {
            return isoDay
        }
        return parser.string(from: shifted)
    }

    /// Abbreviation and offset for the header control, e.g. "EDT · UTC-04:00".
    public static func zoneLabel(_ timeZone: TimeZone, at instant: Date = Date()) -> String {
        let abbreviation = timeZone.abbreviation(for: instant) ?? timeZone.identifier
        let offset = timeZone.secondsFromGMT(for: instant)
        let sign = offset < 0 ? "-" : "+"
        let total = abs(offset) / 60
        let hours = String(format: "%02d", total / 60)
        let minutes = String(format: "%02d", total % 60)
        return "\(abbreviation) · UTC\(sign)\(hours):\(minutes)"
    }

    public static func accessibleZoneName(_ timeZone: TimeZone, at instant: Date = Date()) -> String {
        String(localized: "Timezone \(timeZone.identifier), \(zoneLabel(timeZone, at: instant))")
    }

    /// Honour an explicit valid zone, else the supplied fallback, else UTC.
    public static func resolve(_ identifier: String?, fallback: TimeZone = .current) -> TimeZone {
        if let identifier, let zone = TimeZone(identifier: identifier) { return zone }
        return fallback
    }
}
