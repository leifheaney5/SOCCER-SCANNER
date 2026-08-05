import Foundation
import Security

/// Secure-credential abstraction.
///
/// No credentials exist today — the product is in deliberate guest mode. This
/// exists so that when accounts land, refresh credentials go to the Keychain
/// and never to `UserDefaults`, which is unencrypted and included in backups.
public protocol SecureStore: Sendable {
    func set(_ data: Data, for key: String) throws
    func data(for key: String) throws -> Data?
    func remove(_ key: String) throws
}

public enum SecureStoreError: Error, Equatable {
    case unexpectedStatus(OSStatus)
}

public struct KeychainStore: SecureStore {
    private let service: String

    public init(service: String = "pro.soccerscanner.credentials") {
        self.service = service
    }

    private func query(for key: String) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
        ]
    }

    public func set(_ data: Data, for key: String) throws {
        var attributes = query(for: key)
        SecItemDelete(attributes as CFDictionary)
        attributes[kSecValueData as String] = data
        // Never synchronised to iCloud and unavailable before first unlock.
        attributes[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let status = SecItemAdd(attributes as CFDictionary, nil)
        guard status == errSecSuccess else { throw SecureStoreError.unexpectedStatus(status) }
    }

    public func data(for key: String) throws -> Data? {
        var attributes = query(for: key)
        attributes[kSecReturnData as String] = true
        attributes[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: AnyObject?
        let status = SecItemCopyMatching(attributes as CFDictionary, &result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess else { throw SecureStoreError.unexpectedStatus(status) }
        return result as? Data
    }

    public func remove(_ key: String) throws {
        let status = SecItemDelete(query(for: key) as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw SecureStoreError.unexpectedStatus(status)
        }
    }
}

/// Test double.
public final class InMemorySecureStore: SecureStore, @unchecked Sendable {
    private var storage: [String: Data] = [:]
    private let lock = NSLock()

    public init() {}

    public func set(_ data: Data, for key: String) throws {
        lock.lock(); defer { lock.unlock() }
        storage[key] = data
    }

    public func data(for key: String) throws -> Data? {
        lock.lock(); defer { lock.unlock() }
        return storage[key]
    }

    public func remove(_ key: String) throws {
        lock.lock(); defer { lock.unlock() }
        storage.removeValue(forKey: key)
    }
}
