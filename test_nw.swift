import Foundation
import Network

// Test 1: URLSession (uses Network.framework/CFNetwork)
let semaphore = DispatchSemaphore(value: 0)
let url = URL(string: "https://www.apple.com")!
var request = URLRequest(url: url)
request.httpMethod = "HEAD"
request.timeoutInterval = 10

let task = URLSession.shared.dataTask(with: request) { data, response, error in
    if let error = error {
        print("URLSession FAILED: \(error.localizedDescription)")
        let nsError = error as NSError
        print("Error domain: \(nsError.domain), code: \(nsError.code)")
        print("Underlying: \(nsError.userInfo)")
    } else if let http = response as? HTTPURLResponse {
        print("URLSession SUCCESS: HTTP \(http.statusCode)")
    }
    semaphore.signal()
}
task.resume()
print("Testing URLSession (Network.framework)...")
if semaphore.wait(timeout: .now() + 15) == .timedOut {
    print("URLSession TIMEOUT")
    task.cancel()
}

// Test 2: NWConnection (raw Network.framework TCP)
let nwSemaphore = DispatchSemaphore(value: 0)
let connection = NWConnection(host: "www.apple.com", port: 443, using: .tcp)
var lastState = ""
connection.stateUpdateHandler = { state in
    let stateDesc: String
    switch state {
    case .setup: stateDesc = "setup"
    case .waiting(let error): stateDesc = "waiting: \(error)"
    case .preparing: stateDesc = "preparing"
    case .ready:
        print("NWConnection READY (TCP connect succeeded)")
        connection.cancel()
        nwSemaphore.signal()
        return
    case .failed(let error):
        stateDesc = "failed: \(error)"
        print("NWConnection FAILED: \(error)")
        nwSemaphore.signal()
        return
    case .cancelled: stateDesc = "cancelled"
    @unknown default: stateDesc = "unknown"
    }
    print("NWConnection state: \(stateDesc)")
}
let nwQueue = DispatchQueue(label: "nw.test")
connection.start(queue: nwQueue)
print("Testing NWConnection (TCP)...")
if nwSemaphore.wait(timeout: .now() + 20) == .timedOut {
    print("NWConnection TIMEOUT (last state seen above)")
    connection.cancel()
}
