/**
 * C-ABI Bindings for nciia-perf
 *
 * Enterprise fixes:
 *  - Added try/catch around all FFI entry points: C++ exceptions must NEVER
 *    cross the FFI boundary; doing so causes undefined behaviour in the
 *    Python host process (instant crash with no traceback).
 *  - Added null-pointer guards for all pointer arguments.
 *  - Added out_size bounds checking so Python can safely request any number
 *    of features without buffer overflow.
 *  - Exposed nciia_perf_version() for runtime ABI version negotiation.
 */

#include "stylometry/analyzer.h"
#include <cmath>
#include <cstring>
#include <cstdint>

// ============================================================================
// Version negotiation
// ============================================================================
#define NCIIA_PERF_VERSION_MAJOR 1
#define NCIIA_PERF_VERSION_MINOR 0
#define NCIIA_PERF_VERSION_PATCH 0

extern "C" {

/**
 * Returns the library version as a packed 32-bit integer:
 *   bits 31-24: major, bits 23-16: minor, bits 15-8: patch, bits 7-0: 0
 */
__declspec(dllexport) uint32_t nciia_perf_version() noexcept {
    return (NCIIA_PERF_VERSION_MAJOR << 24) |
           (NCIIA_PERF_VERSION_MINOR << 16) |
           (NCIIA_PERF_VERSION_PATCH << 8);
}

// ============================================================================
// Analyzer lifecycle
// ============================================================================

/**
 * Create a new Analyzer instance on the heap.
 * Returns nullptr if allocation or construction fails.
 */
__declspec(dllexport) nciia::stylometry::Analyzer* Analyzer_Create() noexcept {
    try {
        return new nciia::stylometry::Analyzer();
    } catch (...) {
        return nullptr;
    }
}

/**
 * Destroy an Analyzer instance previously created with Analyzer_Create.
 * Safe to call with nullptr.
 */
__declspec(dllexport) void Analyzer_Destroy(nciia::stylometry::Analyzer* analyzer) noexcept {
    try {
        delete analyzer;
    } catch (...) {
        // Swallow: destructor exceptions must never escape FFI boundary
    }
}

// ============================================================================
// Feature extraction
// ============================================================================

/**
 * Extract stylometric features from a UTF-8 text string.
 *
 * @param analyzer     Pointer to an Analyzer created by Analyzer_Create.
 * @param text         Null-terminated UTF-8 input text.
 * @param out_features Output buffer for feature doubles.
 * @param out_size     Number of elements in out_features (max capacity).
 * @return             Number of features written, or -1 on error.
 *
 * Feature layout (index → meaning):
 *   [0] avg_word_length
 *   [1] avg_sentence_length
 *   [2] vocabulary_richness
 *   [3] hapax_legomena_ratio
 *   [4] confidence
 */
__declspec(dllexport) int32_t Analyzer_ExtractFeatures(
    nciia::stylometry::Analyzer* analyzer,
    const char*                  text,
    double*                      out_features,
    int32_t                      out_size
) noexcept {
    // Null / bounds guard
    if (!analyzer || !text || !out_features || out_size <= 0) {
        return -1;
    }

    try {
        auto features = analyzer->extract_features(std::string(text));

        // Number of features we can write = min(5, out_size)
        const int32_t NUM_FEATURES = 5;
        int32_t to_write = (out_size < NUM_FEATURES) ? out_size : NUM_FEATURES;

        // Zero-initialise the entire output buffer first (enterprise safety)
        std::memset(out_features, 0, static_cast<size_t>(out_size) * sizeof(double));

        if (to_write > 0) out_features[0] = features.avg_word_length;
        if (to_write > 1) out_features[1] = features.avg_sentence_length;
        if (to_write > 2) out_features[2] = features.vocabulary_richness;
        if (to_write > 3) out_features[3] = features.hapax_legomena_ratio;
        if (to_write > 4) out_features[4] = features.confidence;

        return to_write;

    } catch (...) {
        // Any C++ exception is swallowed here; Python caller sees -1 return
        return -1;
    }
}

/**
 * Compute similarity between two feature arrays (cosine similarity).
 *
 * @param features_a  First feature vector (length = size).
 * @param features_b  Second feature vector (length = size).
 * @param size        Number of elements in each vector.
 * @return            Similarity score [0.0, 1.0], or -1.0 on error.
 */
__declspec(dllexport) double Analyzer_ComputeSimilarity(
    const double* features_a,
    const double* features_b,
    int32_t       size
) noexcept {
    if (!features_a || !features_b || size <= 0) return -1.0;

    try {
        double dot = 0.0, mag_a = 0.0, mag_b = 0.0;
        for (int32_t i = 0; i < size; ++i) {
            dot   += features_a[i] * features_b[i];
            mag_a += features_a[i] * features_a[i];
            mag_b += features_b[i] * features_b[i];
        }
        if (mag_a == 0.0 || mag_b == 0.0) return 0.0;
        double result = dot / (std::sqrt(mag_a) * std::sqrt(mag_b));
        return (result < 0.0) ? 0.0 : (result > 1.0 ? 1.0 : result);
    } catch (...) {
        return -1.0;
    }
}

}  // extern "C"
