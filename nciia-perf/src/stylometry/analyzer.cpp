/**
 * N-CIIA - Stylometry Analyzer Implementation
 */

#include "stylometry/analyzer.h"
#include <algorithm>
#include <cctype>
#include <numeric>
#include <sstream>
#include <unordered_set>

namespace nciia {
namespace stylometry {

Analyzer::Analyzer() {
    // Common English function words for stylometric analysis
    function_words_ = {
        "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
        "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
        "this", "but", "his", "by", "from", "they", "we", "say", "her", "she",
        "or", "an", "will", "my", "one", "all", "would", "there", "their", "what",
        "so", "up", "out", "if", "about", "who", "get", "which", "go", "me"
    };
}

std::vector<std::string> Analyzer::tokenize(const std::string& text) {
    std::vector<std::string> tokens;
    std::string current;
    
    for (char c : text) {
        if (std::isalnum(c) || c == '\'') {
            current += std::tolower(c);
        } else if (!current.empty()) {
            tokens.push_back(current);
            current.clear();
        }
    }
    if (!current.empty()) {
        tokens.push_back(current);
    }
    return tokens;
}

std::vector<std::string> Analyzer::split_sentences(const std::string& text) {
    std::vector<std::string> sentences;
    std::string current;
    
    for (size_t i = 0; i < text.size(); ++i) {
        current += text[i];
        if (text[i] == '.' || text[i] == '!' || text[i] == '?') {
            if (!current.empty() && current.size() > 2) {
                sentences.push_back(current);
            }
            current.clear();
        }
    }
    if (!current.empty() && current.size() > 5) {
        sentences.push_back(current);
    }
    return sentences;
}

double Analyzer::calculate_stddev(const std::vector<double>& values, double mean) {
    if (values.empty()) return 0.0;
    double sq_sum = 0.0;
    for (double v : values) {
        sq_sum += (v - mean) * (v - mean);
    }
    return std::sqrt(sq_sum / values.size());
}

StyleFeatures Analyzer::extract_features(const std::string& text) {
    StyleFeatures features;
    
    if (text.empty()) return features;
    
    // Tokenize
    auto tokens = tokenize(text);
    if (tokens.empty()) return features;
    
    // Word count map for vocabulary analysis
    std::unordered_map<std::string, int> word_counts;
    double total_word_length = 0.0;
    
    for (const auto& token : tokens) {
        word_counts[token]++;
        total_word_length += token.size();
    }
    
    // Average word length
    features.avg_word_length = total_word_length / tokens.size();
    
    // Vocabulary richness (type-token ratio)
    features.vocabulary_richness = static_cast<double>(word_counts.size()) / tokens.size();
    
    // Hapax legomena ratio
    int hapax_count = 0;
    for (const auto& [word, count] : word_counts) {
        if (count == 1) hapax_count++;
    }
    features.hapax_legomena_ratio = static_cast<double>(hapax_count) / word_counts.size();
    
    // Sentence analysis
    auto sentences = split_sentences(text);
    if (!sentences.empty()) {
        std::vector<double> sentence_lengths;
        for (const auto& sent : sentences) {
            auto sent_tokens = tokenize(sent);
            sentence_lengths.push_back(static_cast<double>(sent_tokens.size()));
        }
        
        double sum = std::accumulate(sentence_lengths.begin(), sentence_lengths.end(), 0.0);
        features.avg_sentence_length = sum / sentence_lengths.size();
        features.sentence_length_stddev = calculate_stddev(sentence_lengths, features.avg_sentence_length);
    }
    
    // Punctuation frequency
    std::vector<char> punctuations = {'.', ',', '!', '?', ';', ':', '-', '\'', '"'};
    for (char p : punctuations) {
        int count = std::count(text.begin(), text.end(), p);
        features.punctuation_freq[p] = static_cast<double>(count) / text.size();
    }
    
    // Function word frequencies
    features.function_word_freqs.reserve(function_words_.size());
    for (const auto& fw : function_words_) {
        auto it = word_counts.find(fw);
        double freq = (it != word_counts.end()) ? 
            static_cast<double>(it->second) / tokens.size() : 0.0;
        features.function_word_freqs.push_back(freq);
    }
    
    features.sample_count = 1;
    features.confidence = std::min(1.0, static_cast<double>(tokens.size()) / 500.0);
    
    return features;
}

double Analyzer::compute_similarity(const StyleFeatures& a, const StyleFeatures& b) {
    double similarity = 0.0;
    double weight_sum = 0.0;
    
    // Word length similarity
    double word_len_sim = 1.0 - std::abs(a.avg_word_length - b.avg_word_length) / 
                          std::max(a.avg_word_length, b.avg_word_length);
    similarity += word_len_sim * 0.1;
    weight_sum += 0.1;
    
    // Vocabulary richness similarity
    double vocab_sim = 1.0 - std::abs(a.vocabulary_richness - b.vocabulary_richness);
    similarity += vocab_sim * 0.15;
    weight_sum += 0.15;
    
    // Sentence length similarity
    if (a.avg_sentence_length > 0 && b.avg_sentence_length > 0) {
        double sent_sim = 1.0 - std::abs(a.avg_sentence_length - b.avg_sentence_length) /
                          std::max(a.avg_sentence_length, b.avg_sentence_length);
        similarity += sent_sim * 0.15;
        weight_sum += 0.15;
    }
    
    // Function word cosine similarity
    if (!a.function_word_freqs.empty() && !b.function_word_freqs.empty()) {
        double dot = 0.0, mag_a = 0.0, mag_b = 0.0;
        for (size_t i = 0; i < std::min(a.function_word_freqs.size(), b.function_word_freqs.size()); ++i) {
            dot += a.function_word_freqs[i] * b.function_word_freqs[i];
            mag_a += a.function_word_freqs[i] * a.function_word_freqs[i];
            mag_b += b.function_word_freqs[i] * b.function_word_freqs[i];
        }
        if (mag_a > 0 && mag_b > 0) {
            double func_sim = dot / (std::sqrt(mag_a) * std::sqrt(mag_b));
            similarity += func_sim * 0.4;
            weight_sum += 0.4;
        }
    }
    
    // Punctuation similarity
    double punct_sim = 0.0;
    int punct_count = 0;
    for (char p : {'.', ',', '!', '?', ';'}) {
        auto it_a = a.punctuation_freq.find(p);
        auto it_b = b.punctuation_freq.find(p);
        double fa = (it_a != a.punctuation_freq.end()) ? it_a->second : 0.0;
        double fb = (it_b != b.punctuation_freq.end()) ? it_b->second : 0.0;
        if (fa > 0 || fb > 0) {
            punct_sim += 1.0 - std::abs(fa - fb) / std::max(fa + 0.001, fb + 0.001);
            punct_count++;
        }
    }
    if (punct_count > 0) {
        similarity += (punct_sim / punct_count) * 0.2;
        weight_sum += 0.2;
    }
    
    return weight_sum > 0 ? similarity / weight_sum : 0.0;
}

void Analyzer::update_fingerprint(StyleFeatures& fingerprint, 
                                  const StyleFeatures& new_sample) {
    int n = fingerprint.sample_count;
    int m = new_sample.sample_count;
    double total = n + m;
    
    // Weighted average update
    fingerprint.avg_word_length = 
        (fingerprint.avg_word_length * n + new_sample.avg_word_length * m) / total;
    fingerprint.vocabulary_richness = 
        (fingerprint.vocabulary_richness * n + new_sample.vocabulary_richness * m) / total;
    fingerprint.avg_sentence_length = 
        (fingerprint.avg_sentence_length * n + new_sample.avg_sentence_length * m) / total;
    
    // Update function word frequencies
    for (size_t i = 0; i < fingerprint.function_word_freqs.size() && 
         i < new_sample.function_word_freqs.size(); ++i) {
        fingerprint.function_word_freqs[i] = 
            (fingerprint.function_word_freqs[i] * n + new_sample.function_word_freqs[i] * m) / total;
    }
    
    fingerprint.sample_count = static_cast<int>(total);
    fingerprint.confidence = std::min(1.0, fingerprint.confidence + 0.1);
}

}  // namespace stylometry
}  // namespace nciia
