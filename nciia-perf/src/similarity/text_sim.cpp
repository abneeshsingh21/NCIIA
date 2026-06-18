/**
 * Text similarity computation
 *
 * Enterprise fixes:
 *  - Added #include <iterator> for std::back_inserter (caused MSVC C3861 errors)
 *  - Added #include <numeric> for future use
 *  - jaccard_similarity now uses unordered_set counting instead of full vector
 *    copies + set_intersection, eliminating unnecessary memory allocations
 */

#include <string>
#include <vector>
#include <algorithm>
#include <iterator>       // FIX: std::back_inserter was missing this header on MSVC
#include <cmath>
#include <unordered_set>  // NEW: for O(N) Jaccard without sorted copies

namespace nciia {
namespace similarity {

/**
 * Compute Jaccard similarity between two token sets.
 *
 * FIX: The previous implementation sorted full vector copies then used
 * set_intersection/set_union with back_inserter — creating 4 additional
 * heap-allocated vectors. This version counts intersection size in a single
 * hash-set pass: O(N+M) time, O(min(N,M)) space.
 */
double jaccard_similarity(const std::vector<std::string>& a,
                          const std::vector<std::string>& b) {
    if (a.empty() && b.empty()) return 1.0;
    if (a.empty() || b.empty()) return 0.0;

    // Build hash set from the smaller vector
    const auto* smaller = (a.size() <= b.size()) ? &a : &b;
    const auto* larger  = (a.size() <= b.size()) ? &b : &a;

    std::unordered_set<std::string> set_small(smaller->begin(), smaller->end());

    size_t intersection_size = 0;
    std::unordered_set<std::string> counted;
    for (const auto& token : *larger) {
        if (set_small.count(token) && !counted.count(token)) {
            ++intersection_size;
            counted.insert(token);
        }
    }

    // |union| = |A| + |B| - |intersection|  (using unique counts)
    size_t union_size = set_small.size() + larger->size() - intersection_size;
    if (union_size == 0) return 1.0;

    return static_cast<double>(intersection_size) / static_cast<double>(union_size);
}

/**
 * Cosine similarity between two equal-length numerical vectors.
 * Returns 0.0 if either vector is zero-magnitude.
 */
double cosine_similarity(const std::vector<double>& a,
                         const std::vector<double>& b) {
    if (a.size() != b.size() || a.empty()) return 0.0;

    double dot = 0.0, mag_a = 0.0, mag_b = 0.0;
    for (size_t i = 0; i < a.size(); ++i) {
        dot   += a[i] * b[i];
        mag_a += a[i] * a[i];
        mag_b += b[i] * b[i];
    }

    if (mag_a == 0.0 || mag_b == 0.0) return 0.0;
    return dot / (std::sqrt(mag_a) * std::sqrt(mag_b));
}

}  // namespace similarity
}  // namespace nciia
