/**
 * Fast hashing utilities for content fingerprinting
 *
 * Enterprise fixes:
 *  - Added missing #include <vector> (caused MSVC C2039 errors)
 *  - Fixed RollingHash: replaced std::vector::erase(begin()) [O(N)] with
 *    std::deque::pop_front() [O(1)] to eliminate the memory-shift bottleneck
 */

#include <string>
#include <cstdint>
#include <vector>
#include <deque>   // NEW: for O(1) pop_front in RollingHash

namespace nciia {
namespace hashing {

/**
 * Fast xxHash-style non-cryptographic hash.
 * Uses two large primes to achieve good avalanche on typical strings.
 */
uint64_t fast_hash(const std::string& data) {
    const uint64_t PRIME1 = 11400714785074694791ULL;
    const uint64_t PRIME2 = 14029467366897019727ULL;

    uint64_t hash = 0xcbf29ce484222325ULL;  // FNV offset basis for better initialisation
    for (unsigned char c : data) {
        hash ^= static_cast<uint64_t>(c);
        hash = hash * PRIME1 + static_cast<uint64_t>(c) * PRIME2;
    }
    return hash;
}

/**
 * Rolling (Rabin-Karp style) hash for incremental content-change detection.
 *
 * FIX: The previous implementation stored the sliding window in a std::vector
 * and called vector::erase(begin()), which is O(N) due to memory shifting.
 * This version uses std::deque, making add() O(1) amortized.
 */
class RollingHash {
public:
    explicit RollingHash(size_t window_size = 16)
        : window_size_(window_size), hash_(0), pow_(1) {
        for (size_t i = 0; i < window_size_; ++i) {
            pow_ *= BASE;
        }
    }

    /**
     * Feed one character into the rolling window.
     * Evicts the oldest character when window is full.
     */
    void add(char c) {
        if (window_.size() >= window_size_) {
            char old = window_.front();
            window_.pop_front();                              // O(1) — was O(N)
            hash_ -= static_cast<uint64_t>(static_cast<unsigned char>(old)) * pow_;
        }
        window_.push_back(c);
        hash_ = hash_ * BASE + static_cast<uint64_t>(static_cast<unsigned char>(c));
    }

    uint64_t get_hash() const noexcept { return hash_; }
    size_t   window_size() const noexcept { return window_size_; }
    bool     full() const noexcept { return window_.size() == window_size_; }

    void reset() noexcept {
        window_.clear();
        hash_ = 0;
    }

private:
    static constexpr uint64_t BASE = 31ULL;
    size_t              window_size_;
    std::deque<char>    window_;   // Changed from std::vector<char>
    uint64_t            hash_;
    uint64_t            pow_;
};

}  // namespace hashing
}  // namespace nciia
