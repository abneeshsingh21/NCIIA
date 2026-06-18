/**
 * Basic stylometry tests
 */

#include <iostream>
#include <cassert>
#include "stylometry/analyzer.h"

using namespace nciia::stylometry;

int main() {
    Analyzer analyzer;
    
    // Test 1: Basic feature extraction
    std::string text1 = "The quick brown fox jumps over the lazy dog. "
                       "This is a simple test sentence with common words.";
    
    auto features1 = analyzer.extract_features(text1);
    
    assert(features1.avg_word_length > 0);
    assert(features1.vocabulary_richness > 0 && features1.vocabulary_richness <= 1);
    assert(features1.sample_count == 1);
    
    std::cout << "Test 1 passed: Basic feature extraction" << std::endl;
    
    // Test 2: Similar texts should have high similarity
    std::string text2 = "The quick red fox jumped over the sleepy dog. "
                       "This is another simple test sentence with common words.";
    
    auto features2 = analyzer.extract_features(text2);
    double similarity = analyzer.compute_similarity(features1, features2);
    
    assert(similarity > 0.5);  // Similar texts should score > 0.5
    
    std::cout << "Test 2 passed: Similar text similarity = " << similarity << std::endl;
    
    // Test 3: Very different texts should have lower similarity
    std::string text3 = "Mathematical formulations! Quantum mechanics? "
                       "The eigenvalues of Hermitian operators are real; "
                       "wavefunctions collapse upon measurement...";
    
    auto features3 = analyzer.extract_features(text3);
    double dissimilarity = analyzer.compute_similarity(features1, features3);
    
    assert(dissimilarity < similarity);  // Different texts should score lower
    
    std::cout << "Test 3 passed: Different text similarity = " << dissimilarity << std::endl;
    
    // Test 4: Fingerprint update
    StyleFeatures fingerprint = features1;
    analyzer.update_fingerprint(fingerprint, features2);
    
    assert(fingerprint.sample_count == 2);
    
    std::cout << "Test 4 passed: Fingerprint update" << std::endl;
    
    std::cout << "\nAll tests passed!" << std::endl;
    return 0;
}
