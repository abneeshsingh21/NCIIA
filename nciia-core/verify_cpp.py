
import sys
import os
sys.path.append(os.path.abspath("src"))

from nciia.behavioral.fingerprint import FingerprintGenerator

def test_loading():
    print("Initializing Generator...")
    gen = FingerprintGenerator()
    
    if gen._cpp_available:
        print("SUCCESS: C++ Module Loaded!")
        
        # Test extraction
        text = "This is a sample text to test the high-performance C++ engine."
        features = gen.extract_features(text)
        print(f"Features Extracted: Word Len={features.avg_word_length:.2f}, Vocab={features.vocabulary_richness:.2f}")
        
        if features.avg_word_length > 0:
            print("VERIFICATION PASSED: Logic works.")
        else:
            print("VERIFICATION FAILED: Features are zero.")
    else:
        print("FAILURE: C++ Module NOT Loaded. Running in Python mode.")

if __name__ == "__main__":
    test_loading()
