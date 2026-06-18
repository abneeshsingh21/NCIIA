/**
 * N-CIIA Performance Library
 * Stylometry Analyzer - Writing style analysis for behavioral fingerprinting
 */

#ifndef NCIIA_STYLOMETRY_ANALYZER_H
#define NCIIA_STYLOMETRY_ANALYZER_H

#include <string>
#include <vector>
#include <unordered_map>
#include <cmath>

namespace nciia {
namespace stylometry {

/**
 * Feature vector representing a text's stylometric signature
 */
struct StyleFeatures {
    // Vocabulary features
    double avg_word_length = 0.0;
    double vocabulary_richness = 0.0;
    double hapax_legomena_ratio = 0.0;  // Words appearing only once
    
    // Sentence features
    double avg_sentence_length = 0.0;
    double sentence_length_stddev = 0.0;
    
    // Punctuation features
    std::unordered_map<char, double> punctuation_freq;
    
    // Function word frequencies
    std::vector<double> function_word_freqs;
    
    // Character n-gram features
    std::vector<double> char_trigram_freqs;
    
    // Confidence
    int sample_count = 0;
    double confidence = 0.0;
};

/**
 * Stylometry analyzer for writing style fingerprinting
 */
class Analyzer {
public:
    Analyzer();
    ~Analyzer() = default;
    
    /**
     * Extract stylometric features from text
     */
    StyleFeatures extract_features(const std::string& text);
    
    /**
     * Compute similarity between two feature sets
     * @return Similarity score 0.0-1.0
     */
    double compute_similarity(const StyleFeatures& a, const StyleFeatures& b);
    
    /**
     * Update fingerprint with new sample
     */
    void update_fingerprint(StyleFeatures& fingerprint, 
                           const StyleFeatures& new_sample);

private:
    std::vector<std::string> tokenize(const std::string& text);
    std::vector<std::string> split_sentences(const std::string& text);
    double calculate_stddev(const std::vector<double>& values, double mean);
    
    // Function words for analysis
    std::vector<std::string> function_words_;
};

}  // namespace stylometry
}  // namespace nciia

#endif  // NCIIA_STYLOMETRY_ANALYZER_H
